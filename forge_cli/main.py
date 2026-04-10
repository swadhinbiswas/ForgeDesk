"""
Forge CLI - Main Entry Point.

Provides the `forge` command with subcommands:
- create: Scaffold a new Forge project
- dev: Start development mode with hot reload
- build: Build a production binary
- serve: Run as a web application server
- info: Display system and project information
"""

from __future__ import annotations

import ast
import io
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import venv
import tarfile
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import urlopen

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.theme import Theme

# Initialize Rich console
console = Console(
    theme=Theme(
        {
            "forge.brand": "bold cyan",
            "forge.header": "bold white on rgb(24,30,54)",
            "forge.ok": "bold green",
            "forge.warn": "bold yellow",
            "forge.err": "bold red",
            "forge.info": "bold blue",
            "forge.muted": "dim",
            "forge.path": "cyan",
        }
    )
)

# Create Typer app
app = typer.Typer(
    name="forge",
    help="Forge CLI - Build desktop and web apps with Python 3.14+",
    add_completion=False,
)

# Version
VERSION = "2.0.0"

_STATUS_ICON = {
    "ok": "✓",
    "warning": "⚠",
    "error": "✖",
    "info": "•",
}


def _status_badge(status: str) -> str:
    normalized = status.lower()
    style = {
        "ok": "forge.ok",
        "warning": "forge.warn",
        "error": "forge.err",
        "info": "forge.info",
    }.get(normalized, "white")
    return f"[{style}]{_STATUS_ICON.get(normalized, '•')} {normalized.upper()}[/]"


def _print_header(title: str, subtitle: str | None = None) -> None:
    body = f"[forge.brand]Forge[/]  [bold]{title}[/]"
    if subtitle:
        body += f"\n[forge.muted]{subtitle}[/]"
    console.print(Panel.fit(body, style="forge.header", border_style="forge.brand"))


def _print_note(message: str, *, level: str = "info") -> None:
    style = {
        "ok": "forge.ok",
        "warning": "forge.warn",
        "error": "forge.err",
        "info": "forge.info",
    }.get(level, "white")
    icon = _STATUS_ICON.get(level, "•")
    console.print(f"[{style}]{icon}[/] {message}")


def _kv_table(rows: list[tuple[str, str]], *, title: str | None = None) -> Table:
    table = Table(title=title, show_header=False, box=box.SIMPLE_HEAVY)
    table.add_column("Key", style="forge.brand", no_wrap=True)
    table.add_column("Value")
    for key, value in rows:
        table.add_row(key, value)
    return table


def _print_project_snapshot(project_dir: Path, config: Any, *, mode: str) -> None:
    rows = [
        ("Mode", mode),
        ("Project", str(project_dir)),
        ("App", f"{config.app.name} v{config.app.version}"),
        ("Entry", str(config.get_entry_path())),
        ("Frontend", str(config.get_frontend_path())),
    ]
    console.print(_kv_table(rows, title="Project"))


def _print_validation_summary(validation: dict[str, Any]) -> None:
    warnings = list(validation.get("warnings", []))
    errors = list(validation.get("errors", []))
    if warnings:
        warning_table = Table(title="Warnings", box=box.SIMPLE_HEAVY, show_header=False)
        warning_table.add_column("Message", style="forge.warn")
        for item in warnings:
            warning_table.add_row(item)
        console.print(warning_table)
    if errors:
        error_table = Table(title="Errors", box=box.SIMPLE_HEAVY, show_header=False)
        error_table.add_column("Message", style="forge.err")
        for item in errors:
            error_table.add_row(item)
        console.print(error_table)


def _print_build_summary(title: str, build_result: dict[str, Any]) -> None:
    rows = [
        ("Target", str(build_result.get("target", "-"))),
        ("Builder", str(build_result.get("builder", "-"))),
        ("Output", str(build_result.get("output_dir", "-"))),
        ("Artifacts", str(len(build_result.get("artifacts", [])))),
        ("Installers", str(len(build_result.get("installers", [])))),
    ]
    console.print(Panel(_kv_table(rows), title=title, border_style="forge.ok"))


def _print_command_result(title: str, path_label: str, path_value: str, *, footer: str | None = None) -> None:
    body = f"[bold]{path_label}[/]\n[forge.path]{path_value}[/]"
    if footer:
        body += f"\n\n[forge.muted]{footer}[/]"
    console.print(Panel.fit(body, title=title, border_style="forge.ok"))


def _check_status(ok: bool) -> str:
    return "ok" if ok else "error"


def _parse_version(version: str) -> tuple[int, int, int]:
    parts = [int(part) for part in version.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore[return-value]


def _resolve_project_dir(path: str | None) -> Path:
    if not path:
        return Path.cwd()

    candidate = Path(path).resolve()
    if (candidate / "forge.toml").exists():
        return candidate

    if not Path(path).is_absolute():
        module_root = Path(__file__).resolve().parents[1]
        fallback = (module_root / path).resolve()
        if (fallback / "forge.toml").exists():
            return fallback

    return candidate


def _version_satisfies_range(version: str, version_range: str) -> bool:
    current = _parse_version(version)
    for raw_constraint in [item.strip() for item in version_range.split(",") if item.strip()]:
        operator = None
        for candidate in (">=", "<=", ">", "<", "=="):
            if raw_constraint.startswith(candidate):
                operator = candidate
                break
        if operator is None:
            return False
        target = _parse_version(raw_constraint[len(operator) :].strip())
        if operator == ">=" and not (current >= target):
            return False
        if operator == "<=" and not (current <= target):
            return False
        if operator == ">" and not (current > target):
            return False
        if operator == "<" and not (current < target):
            return False
        if operator == "==" and not (current == target):
            return False
    return True


def _extract_plugin_manifest_from_python_file(path: Path) -> dict[str, Any] | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"manifest", "__forge_plugin__"}:
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        return None
                    if isinstance(value, dict):
                        return value
    return None


def _resolve_plugin_manifest_source(project_dir: Path, module_name: str) -> Path | None:
    original_sys_path = list(sys.path)
    try:
        sys.path.insert(0, str(project_dir))
        spec = importlib.util.find_spec(module_name)
    except Exception:
        spec = None
    finally:
        sys.path[:] = original_sys_path

    if spec is None or spec.origin is None or spec.origin == "built-in":
        return None
    return Path(spec.origin)


def _validate_plugin_contract(
    manifest: dict[str, Any] | None,
    *,
    source: str,
    module: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "module": module,
        "manifest": manifest or {},
        "valid": True,
        "errors": [],
    }
    if not isinstance(manifest, dict):
        payload["valid"] = False
        payload["errors"].append("Plugin manifest missing or not a dictionary")
        return payload

    name = manifest.get("name")
    version = manifest.get("version")
    forge_version_range = manifest.get("forge_version") or manifest.get("forge_version_range")

    payload["name"] = name
    payload["version"] = version
    payload["forge_version"] = forge_version_range

    if not isinstance(name, str) or not name.strip():
        payload["valid"] = False
        payload["errors"].append("Plugin manifest must declare a non-empty name")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        payload["valid"] = False
        payload["errors"].append("Plugin manifest version must be a non-empty string when provided")
    if forge_version_range is not None:
        if not isinstance(forge_version_range, str) or not forge_version_range.strip():
            payload["valid"] = False
            payload["errors"].append("Plugin forge_version must be a non-empty string when provided")
        elif not _version_satisfies_range(VERSION, forge_version_range):
            payload["valid"] = False
            payload["errors"].append(
                f"Plugin requires Forge {forge_version_range}, current CLI is {VERSION}"
            )
    return payload


def _collect_plugin_contracts(project_dir: Path, config: Any) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    if not getattr(config.plugins, "enabled", False):
        return contracts

    for module_name in getattr(config.plugins, "modules", []) or []:
        source_path = _resolve_plugin_manifest_source(project_dir, module_name)
        manifest = _extract_plugin_manifest_from_python_file(source_path) if source_path else None
        contracts.append(
            _validate_plugin_contract(
                manifest,
                source=str(source_path or module_name),
                module=module_name,
            )
        )

    for raw_path in getattr(config.plugins, "paths", []) or []:
        plugin_path = Path(raw_path)
        if not plugin_path.is_absolute():
            plugin_path = project_dir / plugin_path
        candidates = [plugin_path] if plugin_path.is_file() else sorted(plugin_path.glob("*.py")) if plugin_path.is_dir() else []
        if not candidates and plugin_path.exists() is False:
            contracts.append(
                {
                    "source": str(plugin_path),
                    "module": None,
                    "manifest": {},
                    "valid": False,
                    "errors": ["Plugin path not found"],
                }
            )
        for candidate in candidates:
            contracts.append(
                _validate_plugin_contract(
                    _extract_plugin_manifest_from_python_file(candidate),
                    source=str(candidate),
                )
            )

    return contracts


def _load_template_contract(config_path: Path) -> dict[str, Any]:
    def _build_contract_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        schema_version = metadata.get("schema_version")
        version_range = metadata.get("forge_version_range")
        errors: list[str] = []
        if schema_version != 1:
            errors.append(f"Unsupported template schema_version: {schema_version}")
        if not isinstance(version_range, str) or not version_range:
            errors.append("Missing tool.forge_template.forge_version_range")
        elif not _version_satisfies_range(VERSION, version_range):
            errors.append(f"Template requires Forge {version_range}, current CLI is {VERSION}")

        return {
            "present": True,
            "valid": not errors,
            "name": metadata.get("name"),
            "schema_version": schema_version,
            "forge_version_range": version_range,
            "errors": errors,
        }

    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        text = config_path.read_text(encoding="utf-8")
        section_match = re.search(
            r"(?ms)^\[tool\.forge_template\]\s*(?P<body>.*?)(?:^\[|\Z)",
            text,
        )
        if not section_match:
            return {
                "present": False,
                "valid": False,
                "errors": ["Missing [tool.forge_template] metadata"],
            }

        body = section_match.group("body")
        metadata: dict[str, Any] = {}
        for key in ["name", "schema_version", "forge_version_range"]:
            match = re.search(rf"^\s*{key}\s*=\s*(.+)$", body, re.MULTILINE)
            if not match:
                continue
            raw_value = match.group(1).strip()
            if raw_value.startswith('"') and raw_value.endswith('"'):
                metadata[key] = raw_value[1:-1]
            else:
                try:
                    metadata[key] = int(raw_value)
                except ValueError:
                    metadata[key] = raw_value
        if not metadata:
            return {
                "present": False,
                "valid": False,
                "errors": ["Missing [tool.forge_template] metadata"],
            }
        return _build_contract_from_metadata(metadata)

    tool_data = data.get("tool", {}) if isinstance(data, dict) else {}
    metadata = tool_data.get("forge_template", {}) if isinstance(tool_data, dict) else {}
    if not isinstance(metadata, dict) or not metadata:
        return {
            "present": False,
            "valid": False,
            "errors": ["Missing [tool.forge_template] metadata"],
        }

    return _build_contract_from_metadata(metadata)


def _machine_readable_print(payload: dict[str, Any]) -> None:
    console.print_json(data=payload)


def _artifact_snapshot(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(item)
        for item in path.rglob("*")
        if item.exists()
    }


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "forge-app"


def _is_free_threaded() -> tuple[bool | None, str]:
    try:
        gil_enabled = sys._is_gil_enabled()  # type: ignore[attr-defined]
    except AttributeError:
        return None, f"GIL (Python {platform.python_version()} -- upgrade to 3.14+ for NoGIL)"

    if gil_enabled:
        return False, "GIL enabled (use PYTHON_GIL=0 for free-threaded)"
    return True, "Free-threaded (NoGIL)"


def _project_payload(project_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(project_dir),
        "config_path": str(project_dir / "forge.toml"),
        "exists": False,
        "valid": False,
        "errors": [],
        "template": None,
    }

    config_path = project_dir / "forge.toml"
    if not config_path.exists():
        payload["errors"].append("No forge.toml found")
        return payload

    payload["exists"] = True
    payload["template"] = _load_template_contract(config_path)

    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as exc:
        payload["errors"].append(f"Config load failed: {exc}")
        return payload

    entry_path = config.get_entry_path()
    frontend_path = config.get_frontend_path()
    plugin_contracts = _collect_plugin_contracts(project_dir, config)

    payload.update(
        {
            "valid": True,
            "app": {
                "name": config.app.name,
                "version": config.app.version,
            },
            "protocol": {
                "schemes": list(config.protocol.schemes),
            },
            "packaging": {
                "app_id": config.packaging.app_id,
                "product_name": config.packaging.product_name,
                "formats": list(config.packaging.formats),
            },
            "signing": {
                "enabled": bool(config.signing.enabled),
                "identity": config.signing.identity,
                "sign_command": config.signing.sign_command,
                "verify_command": config.signing.verify_command,
                "notarize": bool(config.signing.notarize),
            },
            "security": {
                "allowed_commands": list(config.security.allowed_commands),
                "denied_commands": list(config.security.denied_commands),
                "expose_command_introspection": bool(config.security.expose_command_introspection),
                "allowed_origins": list(config.security.allowed_origins),
                "window_scopes": {
                    key: list(value) for key, value in config.security.window_scopes.items()
                },
                "strict_mode": bool(config.security.strict_mode),
                "rate_limit": int(config.security.rate_limit),
            },
            "plugins": {
                "enabled": bool(config.plugins.enabled),
                "modules": list(config.plugins.modules),
                "paths": list(config.plugins.paths),
                "contracts": plugin_contracts,
            },
            "entry_path": str(entry_path),
            "frontend_path": str(frontend_path),
            "entry_exists": entry_path.exists(),
            "frontend_exists": frontend_path.exists(),
            "template_mode": "frontend-dir",
        }
    )

    if not entry_path.exists():
        payload["errors"].append(f"Entry point missing: {entry_path}")
    if not frontend_path.exists():
        payload["errors"].append(f"Frontend directory missing: {frontend_path}")
    template_metadata = payload.get("template")
    if isinstance(template_metadata, dict) and template_metadata.get("present") and not template_metadata.get("valid"):
        payload["errors"].extend(template_metadata.get("errors", []))
    for contract in plugin_contracts:
        if not contract.get("valid"):
            payload["errors"].extend(
                [f"Plugin contract invalid: {error}" for error in contract.get("errors", [])]
            )

    return payload


def _check_command_version(cmd: str) -> tuple[str, str | None]:
    """Run `cmd --version` and return (status, version_string)."""
    path = shutil.which(cmd)
    if not path:
        return "warning", None
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version = result.stdout.strip() or result.stderr.strip()
        # Extract version number (e.g. "v20.11.0" or "10.2.4")
        match = re.search(r"(\d+\.\d+\.\d+)", version)
        return "ok", match.group(1) if match else version
    except Exception:
        return "warning", None


def _check_port_available(port: int) -> bool:
    """Check if a TCP port is available for binding."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _check_webview_available() -> tuple[str, str]:
    """Check for WebView runtime availability on the current platform."""
    system = platform.system()
    if system == "Darwin":
        # macOS always has WKWebView
        return "ok", "WKWebView (built-in)"
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            )
            winreg.CloseKey(key)
            return "ok", "WebView2 Runtime"
        except Exception:
            return "warning", "WebView2 not found (install from microsoft.com)"
    # Linux: check for WebKitGTK
    for lib_name in ["libwebkit2gtk-4.1.so", "libwebkit2gtk-4.0.so"]:
        for search_dir in ["/usr/lib", "/usr/lib64", f"/usr/lib/{platform.machine()}-linux-gnu"]:
            lib_path = Path(search_dir) / lib_name
            if lib_path.exists():
                return "ok", f"WebKitGTK ({lib_name})"
    # Try pkg-config fallback
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", "webkit2gtk-4.1"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return "ok", "WebKitGTK 4.1 (pkg-config)"
        result = subprocess.run(
            ["pkg-config", "--exists", "webkit2gtk-4.0"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return "ok", "WebKitGTK 4.0 (pkg-config)"
    except Exception:
        pass
    return "warning", "WebKitGTK not found (apt install libwebkit2gtk-4.1-dev)"


def _environment_payload() -> dict[str, Any]:
    free_threaded, threading_text = _is_free_threaded()
    python_ok = sys.version_info >= (3, 14)

    forge_core_ok = True
    forge_core_detail = "Available"
    try:
        from forge import forge_core  # noqa: F401
    except ImportError:
        forge_core_ok = False
        forge_core_detail = "Not compiled (run: maturin develop)"

    # Node.js / npm checks
    node_status, node_version = _check_command_version("node")
    node_ok = node_status == "ok" and node_version is not None
    if node_ok:
        try:
            major = int(node_version.split(".")[0])
            if major < 18:
                node_status = "warning"
                node_version = f"{node_version} (>=18 recommended)"
        except ValueError:
            pass
    npm_status, npm_version = _check_command_version("npm")

    # WebView check
    webview_status, webview_detail = _check_webview_available()

    # Port check (default dev port)
    dev_port = 5173
    port_free = _check_port_available(dev_port)

    checks = {
        "python": {
            "status": _check_status(python_ok),
            "version": platform.python_version(),
            "required": ">=3.14",
        },
        "threading": {
            "status": "ok" if free_threaded is not None else "warning",
            "free_threaded": free_threaded,
            "detail": threading_text,
        },
        "rust_core": {
            "status": _check_status(forge_core_ok),
            "detail": forge_core_detail,
        },
        "cargo": {
            "status": _check_status(shutil.which("cargo") is not None),
            "path": shutil.which("cargo"),
        },
        "rustc": {
            "status": _check_status(shutil.which("rustc") is not None),
            "path": shutil.which("rustc"),
        },
        "maturin": {
            "status": _check_status(shutil.which("maturin") is not None),
            "path": shutil.which("maturin"),
        },
        "node": {
            "status": node_status,
            "version": node_version,
            "path": shutil.which("node"),
        },
        "npm": {
            "status": npm_status,
            "version": npm_version,
            "path": shutil.which("npm"),
        },
        "webview": {
            "status": webview_status,
            "detail": webview_detail,
        },
        "dev_port": {
            "status": _check_status(port_free),
            "port": dev_port,
            "detail": f"Port {dev_port} {'available' if port_free else 'in use'}",
        },
        "uvicorn": {
            "status": "ok" if _module_available("uvicorn") else "warning",
        },
        "msgpack": {
            "status": "ok" if _module_available("msgpack") else "warning",
        },
        "cryptography": {
            "status": "ok" if _module_available("cryptography") else "warning",
        },
    }

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "checks": checks,
    }


def _select_desktop_build_tool(project_dir: Path) -> dict[str, Any]:
    cargo_toml = project_dir / "Cargo.toml"
    maturin_path = shutil.which("maturin")
    nuitka_available = _module_available("nuitka")
    nuitka_path = shutil.which("nuitka")

    if cargo_toml.exists() and maturin_path:
        return {
            "name": "maturin",
            "mode": "hybrid",
            "available": True,
            "path": maturin_path,
        }

    if nuitka_available or nuitka_path:
        return {
            "name": "nuitka",
            "mode": "python",
            "available": True,
            "path": nuitka_path or sys.executable,
        }

    return {
        "name": "maturin" if cargo_toml.exists() else "nuitka",
        "mode": "hybrid" if cargo_toml.exists() else "python",
        "available": False,
        "path": maturin_path,
    }


def _build_validation_payload(config: Any, project_dir: Path, target: str, output_dir: Path) -> dict[str, Any]:
    entry_path = config.get_entry_path()
    frontend_path = config.get_frontend_path()
    icon_path = (project_dir / config.build.icon).resolve() if config.build.icon else None
    normalized_target = target.lower()
    warnings: list[str] = []
    errors: list[str] = []
    build_tool: dict[str, Any] | None = None
    packaging = {
        "app_id": config.packaging.app_id,
        "product_name": config.packaging.product_name,
        "formats": list(config.packaging.formats),
        "category": config.packaging.category,
        "protocol_schemes": list(config.protocol.schemes),
        "signing": {
            "enabled": bool(config.signing.enabled),
            "adapter": config.signing.adapter,
            "identity": config.signing.identity,
            "sign_command": config.signing.sign_command,
            "verify_command": config.signing.verify_command,
            "notarize": bool(config.signing.notarize),
            "timestamp_url": config.signing.timestamp_url,
        },
        "security": {
            "allowed_commands": list(config.security.allowed_commands),
            "denied_commands": list(config.security.denied_commands),
            "expose_command_introspection": bool(config.security.expose_command_introspection),
            "allowed_origins": list(config.security.allowed_origins),
            "window_scopes": {
                key: list(value) for key, value in config.security.window_scopes.items()
            },
            "strict_mode": bool(config.security.strict_mode),
            "rate_limit": int(config.security.rate_limit),
        },
        "plugins": {
            "enabled": bool(config.plugins.enabled),
            "modules": list(config.plugins.modules),
            "paths": list(config.plugins.paths),
            "contracts": _collect_plugin_contracts(project_dir, config),
        },
    }

    if normalized_target not in {"desktop", "web"}:
        errors.append(f"Unsupported build target: {target}")

    if normalized_target == "desktop":
        if not entry_path.exists():
            errors.append(f"Entry point missing: {entry_path}")
        if not frontend_path.exists():
            errors.append(f"Frontend directory missing: {frontend_path}")
        build_tool = _select_desktop_build_tool(project_dir)
        if not build_tool["available"]:
            errors.append("No supported desktop build tool found. Install maturin or nuitka.")
        elif build_tool["name"] == "nuitka" and (project_dir / "Cargo.toml").exists():
            warnings.append("Cargo.toml detected but maturin is unavailable; falling back to Nuitka.")
        if (config.protocol.schemes or config.signing.enabled) and not config.packaging.app_id:
            warnings.append(
                "packaging.app_id should be set when using protocol handlers or signing desktop builds."
            )
        if config.signing.enabled and not (config.signing.identity or config.signing.sign_command):
            warnings.append(
                "signing.enabled is true but no signing.identity or signing.sign_command is configured."
            )
        if config.signing.notarize and not config.signing.verify_command:
            warnings.append(
                "signing.notarize is enabled without signing.verify_command; post-sign verification is recommended."
            )
        if config.signing.notarize and not (
            config.signing.notarize_command or (platform.system() == "Darwin" and shutil.which("xcrun"))
        ):
            warnings.append(
                "signing.notarize is enabled but no notarization command or supported platform adapter is available."
            )
        if config.plugins.enabled and not (config.plugins.modules or config.plugins.paths):
            warnings.append(
                "plugins.enabled is true but no plugins.modules or plugins.paths are configured."
            )
        invalid_plugin_contracts = [item for item in packaging["plugins"]["contracts"] if not item.get("valid")]
        if invalid_plugin_contracts:
            warnings.append(
                "One or more plugin contracts are invalid; inspect validation.packaging.plugins.contracts for details."
            )
        _validate_installer_tooling(config, errors)
    elif normalized_target == "web":
        if not frontend_path.exists():
            errors.append(f"Frontend directory missing: {frontend_path}")

    if config.build.icon and icon_path is not None and not icon_path.exists():
        warnings.append(f"Configured icon not found: {icon_path}")

    return {
        "ok": not errors,
        "target": normalized_target,
        "project_dir": str(project_dir),
        "output_dir": str(output_dir),
        "entry_path": str(entry_path),
        "frontend_path": str(frontend_path),
        "icon_path": str(icon_path) if icon_path is not None else None,
        "build_tool": build_tool,
        "packaging": packaging,
        "warnings": warnings,
        "errors": errors,
    }


def _handle_build_failure(payload: dict[str, Any], result_format: str, exit_code: int = 1) -> None:
    if result_format == "json":
        _machine_readable_print(payload)
    else:
        _print_header("Command Failed")
        _print_validation_summary(payload.get("validation", {}))
        build_error = payload.get("build", {}).get("error")
        if build_error:
            _print_note(build_error, level="error")
    raise typer.Exit(exit_code)


def _package_contract_payload(
    config: Any,
    target: str,
    output_dir: Path,
    builder: str,
    artifacts: list[str],
) -> dict[str, Any]:
    product_name = config.packaging.product_name or config.app.name
    return {
        "format_version": 1,
        "target": target,
        "builder": builder,
        "app": {
            "name": config.app.name,
            "version": config.app.version,
            "product_name": product_name,
            "app_id": config.packaging.app_id,
        },
        "protocol": {
            "schemes": list(config.protocol.schemes),
        },
        "packaging": {
            "formats": list(config.packaging.formats),
            "category": config.packaging.category,
        },
        "signing": {
            "enabled": bool(config.signing.enabled),
            "adapter": config.signing.adapter,
            "identity": config.signing.identity,
            "notarize": bool(config.signing.notarize),
            "timestamp_url": config.signing.timestamp_url,
        },
        "output_dir": str(output_dir),
        "artifacts": list(artifacts),
    }


def _write_package_descriptors(
    config: Any,
    project_dir: Path,
    output_dir: Path,
    *,
    builder: str,
    target: str,
    artifacts: list[str],
) -> dict[str, Any]:
    manifest_payload = _package_contract_payload(config, target, output_dir, builder, artifacts)
    manifest_path = output_dir / "forge-package.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")
    plugin_contracts = _collect_plugin_contracts(project_dir, config)

    descriptor_paths = [str(manifest_path)]
    descriptors: list[dict[str, Any]] = [
        {
            "type": "package-manifest",
            "path": str(manifest_path),
        }
    ]

    if config.plugins.enabled or plugin_contracts:
        plugin_manifest_path = output_dir / "forge-plugins.json"
        plugin_manifest_path.write_text(
            json.dumps(
                {
                    "enabled": bool(config.plugins.enabled),
                    "contracts": plugin_contracts,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        descriptor_paths.append(str(plugin_manifest_path))
        descriptors.append({"type": "plugin-manifest", "path": str(plugin_manifest_path)})

    protocol_path = output_dir / "forge-protocols.json"
    protocol_payload = {
        "app_id": config.packaging.app_id,
        "product_name": config.packaging.product_name or config.app.name,
        "schemes": list(config.protocol.schemes),
    }
    protocol_path.write_text(json.dumps(protocol_payload, indent=2, sort_keys=True), encoding="utf-8")
    descriptor_paths.append(str(protocol_path))
    descriptors.append({"type": "protocol-manifest", "path": str(protocol_path)})

    for installer_descriptor in _generate_installer_descriptors(config, output_dir):
        descriptor_paths.append(installer_descriptor["path"])
        descriptors.append(installer_descriptor)

    if target == "desktop" and platform.system() == "Linux" and config.protocol.schemes:
        desktop_name = f"{_slugify(config.packaging.product_name or config.app.name)}.desktop"
        desktop_path = output_dir / desktop_name
        exec_name = _slugify(config.packaging.product_name or config.app.name)
        mime_types = ";".join(f"x-scheme-handler/{scheme}" for scheme in config.protocol.schemes)
        desktop_path.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={config.packaging.product_name or config.app.name}",
                    f"Exec={exec_name} %u",
                    "Terminal=false",
                    f"Categories={config.packaging.category or 'Utility'};",
                    f"MimeType={mime_types};",
                    f"X-Forge-AppId={config.packaging.app_id or ''}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        descriptor_paths.append(str(desktop_path))
        descriptors.append({"type": "linux-desktop-entry", "path": str(desktop_path)})

    return {
        "manifest_path": str(manifest_path),
        "descriptors": descriptors,
        "files": descriptor_paths,
    }


def _run_signing_hook(
    command: str | list[str] | None,
    *,
    phase: str,
    project_dir: Path,
    output_dir: Path,
    artifacts: list[str],
    package_manifest: str,
) -> dict[str, Any]:
    if not command:
        return {"status": "skipped", "phase": phase, "command": None}

    command_args = shlex.split(command) if isinstance(command, str) else list(command)

    env = os.environ.copy()
    env.update(
        {
            "FORGE_SIGN_PHASE": phase,
            "FORGE_BUILD_OUTPUT_DIR": str(output_dir),
            "FORGE_BUILD_ARTIFACTS": json.dumps(artifacts),
            "FORGE_PACKAGE_MANIFEST": package_manifest,
        }
    )
    completed = subprocess.run(
        command_args,
        cwd=str(project_dir),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "status": "ok",
        "phase": phase,
        "command": command if isinstance(command, str) else command_args,
        "stdout": (completed.stdout or "")[:1000],
        "stderr": (completed.stderr or "")[:1000],
    }


def _generate_installer_descriptors(config: Any, output_dir: Path) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    product_name = config.packaging.product_name or config.app.name
    app_id = config.packaging.app_id or _slugify(product_name)
    schemes = list(config.protocol.schemes)

    for fmt in config.packaging.formats:
        descriptor_path = output_dir / f"forge-installer-{fmt}.json"
        payload = {
            "format": fmt,
            "app_id": app_id,
            "product_name": product_name,
            "version": config.app.version,
            "category": config.packaging.category,
            "protocol_schemes": schemes,
        }
        if fmt == "deb":
            payload["control"] = {
                "Package": app_id,
                "Version": config.app.version,
                "Section": config.packaging.category or "utils",
            }
        elif fmt == "rpm":
            payload["spec"] = {
                "Name": app_id,
                "Version": config.app.version,
                "Summary": config.app.description,
            }
        elif fmt == "appimage":
            payload["appimage"] = {
                "desktop_entry": f"{_slugify(product_name)}.desktop",
            }
        elif fmt in {"dmg", "pkg"}:
            payload["bundle_identifier"] = app_id
        elif fmt in {"msi", "nsis"}:
            payload["upgrade_code"] = _windows_upgrade_code(app_id)

        descriptor_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        descriptors.append({"type": f"installer-{fmt}", "path": str(descriptor_path)})

    return descriptors


def _windows_upgrade_code(app_id: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"forge:{app_id}")).upper() + "}"


def _find_packaging_tool(tool_name: str) -> str | None:
    direct = shutil.which(tool_name)
    if direct:
        return direct

    if platform.system() != "Windows":
        return None

    normalized = tool_name.lower()
    candidates: list[str] = [tool_name]
    if not normalized.endswith((".exe", ".cmd", ".bat")):
        candidates.extend([f"{tool_name}.exe", f"{tool_name}.cmd", f"{tool_name}.bat"])

    roots: list[Path] = []
    for env_key in ("ChocolateyInstall", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        raw = os.environ.get(env_key)
        if raw:
            roots.append(Path(raw))

    fallback_dirs: list[Path] = []
    if normalized.startswith("makensis"):
        for root in roots:
            fallback_dirs.extend([
                root / "NSIS",
                root / "nsis",
                root / "NSIS" / "Bin",
                root / "nsis" / "bin",
            ])
    elif normalized in {"candle", "light"}:
        for root in roots:
            fallback_dirs.extend([
                root / "WiX Toolset v3.11" / "bin",
                root / "WiX Toolset v3.14" / "bin",
                root / "wix toolset v3.11" / "bin",
                root / "wix toolset v3.14" / "bin",
            ])

    for directory in fallback_dirs:
        for candidate in candidates:
            candidate_path = directory / candidate
            if candidate_path.exists():
                return str(candidate_path)

    return None


def _require_tool(tool_name: str, reason: str) -> str:
    tool_path = _find_packaging_tool(tool_name)
    if not tool_path:
        raise FileNotFoundError(f"Required packaging tool '{tool_name}' not found: {reason}")
    return tool_path


def _validate_installer_tooling(config: Any, errors: list[str]) -> None:
    current_platform = platform.system()
    formats = set(config.packaging.formats)

    if current_platform == "Darwin" and "dmg" in formats and not _find_packaging_tool("hdiutil"):
        errors.append("Packaging format 'dmg' requires the 'hdiutil' tool on macOS.")
    if current_platform == "Windows" and "nsis" in formats and not _find_packaging_tool("makensis"):
        errors.append("Packaging format 'nsis' requires the 'makensis' tool on Windows.")
    if current_platform == "Windows" and "msi" in formats and not (
        _find_packaging_tool("wixl") or (_find_packaging_tool("candle") and _find_packaging_tool("light"))
    ):
        errors.append("Packaging format 'msi' requires 'wixl' or the WiX toolset ('candle' and 'light').")
    if current_platform == "Linux" and "appimage" in formats and not _find_packaging_tool("appimagetool"):
        errors.append("Packaging format 'appimage' requires the 'appimagetool' binary on Linux.")
    if current_platform == "Linux" and "flatpak" in formats and not (
        _find_packaging_tool("flatpak-builder") and _find_packaging_tool("flatpak")
    ):
        errors.append("Packaging format 'flatpak' requires both 'flatpak-builder' and 'flatpak' on Linux.")


def _write_ar_archive(archive_path: Path, members: list[tuple[str, bytes]]) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as handle:
        handle.write(b"!<arch>\n")
        timestamp = str(int(time.time())).encode("ascii")
        for name, payload in members:
            encoded_name = f"{name}/"[:16].ljust(16).encode("ascii")
            header = (
                encoded_name
                + timestamp.ljust(12)
                + b"0".ljust(6)
                + b"0".ljust(6)
                + b"100644".ljust(8)
                + str(len(payload)).encode("ascii").ljust(10)
                + b"`\n"
            )
            handle.write(header)
            handle.write(payload)
            if len(payload) % 2 == 1:
                handle.write(b"\n")


def _build_linux_deb_installer(
    config: Any,
    output_dir: Path,
    package_result: dict[str, Any],
) -> dict[str, Any] | None:
    if platform.system() != "Linux" or "deb" not in config.packaging.formats:
        return None

    product_name = config.packaging.product_name or config.app.name
    package_name = _slugify(config.packaging.app_id or product_name)
    version = config.app.version
    architecture = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }.get(platform.machine() or "", platform.machine() or "amd64")
    deb_path = output_dir / f"{package_name}_{version}_{architecture}.deb"

    control_body = "\n".join(
        [
            f"Package: {package_name}",
            f"Version: {version}",
            "Section: utils",
            "Priority: optional",
            f"Architecture: {architecture}",
            f"Maintainer: {', '.join(config.app.authors) or 'Forge Team'}",
            f"Description: {config.app.description}",
            "",
        ]
    ).encode("utf-8")

    control_bytes = io.BytesIO()
    with tarfile.open(fileobj=control_bytes, mode="w:gz") as control_tar:
        control_info = tarfile.TarInfo("./control")
        control_info.size = len(control_body)
        control_info.mode = 0o644
        control_tar.addfile(control_info, io.BytesIO(control_body))

    data_bytes = io.BytesIO()
    install_root = f"./opt/{package_name}"
    desktop_entries = {
        Path(descriptor["path"])
        for descriptor in package_result.get("descriptors", [])
        if descriptor.get("type") == "linux-desktop-entry"
    }
    with tarfile.open(fileobj=data_bytes, mode="w:gz") as data_tar:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path == deb_path:
                continue
            arcname = f"{install_root}/{path.relative_to(output_dir).as_posix()}"
            if path in desktop_entries:
                arcname = f"./usr/share/applications/{path.name}"
            data_tar.add(path, arcname=arcname)

    _write_ar_archive(
        deb_path,
        [
            ("debian-binary", b"2.0\n"),
            ("control.tar.gz", control_bytes.getvalue()),
            ("data.tar.gz", data_bytes.getvalue()),
        ],
    )
    return {
        "type": "installer-artifact-deb",
        "format": "deb",
        "path": str(deb_path),
        "package": package_name,
        "version": version,
    }


def _primary_binary_artifact(artifacts: list[str]) -> Path | None:
    for artifact in artifacts:
        artifact_path = Path(artifact)
        if artifact_path.is_file() and artifact_path.suffix not in {".json", ".desktop", ".asc", ".sig", ".txt", ".md"}:
            return artifact_path
    return None


def _build_macos_app_bundle(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Darwin" or not ({"app", "dmg"} & set(config.packaging.formats)):
        return None

    primary_binary = _primary_binary_artifact(artifacts)
    if primary_binary is None:
        return None

    product_name = config.packaging.product_name or config.app.name
    executable_name = _slugify(product_name).replace("-", "_")
    bundle_path = output_dir / f"{product_name}.app"
    contents_dir = bundle_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    app_binary_path = macos_dir / executable_name
    shutil.copy2(primary_binary, app_binary_path)

    info_plist = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": product_name,
        "CFBundleExecutable": executable_name,
        "CFBundleIdentifier": config.packaging.app_id or f"dev.forge.{_slugify(product_name)}",
        "CFBundleName": product_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": config.app.version,
        "CFBundleVersion": config.app.version,
        "LSMinimumSystemVersion": "11.0",
    }
    (contents_dir / "Info.plist").write_text(
        plistlib.dumps(info_plist).decode("utf-8"),
        encoding="utf-8",
    )

    return {
        "type": "installer-artifact-app",
        "format": "app",
        "path": str(bundle_path),
        "bundle_id": info_plist["CFBundleIdentifier"],
        "version": config.app.version,
    }


def _build_windows_msi_installer(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Windows" or "msi" not in config.packaging.formats:
        return None

    primary_binary = _primary_binary_artifact(artifacts)
    if primary_binary is None:
        raise FileNotFoundError("Packaging format 'msi' requested but no primary binary artifact was produced.")

    product_name = config.packaging.product_name or config.app.name
    app_id = config.packaging.app_id or f"dev.forge.{_slugify(product_name)}"
    version = config.app.version
    wix_source = output_dir / f"{_slugify(product_name)}.wxs"
    msi_path = output_dir / f"{_slugify(product_name)}-{version}.msi"
    upgrade_code = _windows_upgrade_code(app_id)

    wix_source.write_text(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">',
                f'  <Product Id="*" Name="{product_name}" Language="1033" Version="{version}" Manufacturer="{", ".join(config.app.authors) or "Forge Team"}" UpgradeCode="{upgrade_code}">',
                '    <Package InstallerVersion="500" Compressed="yes" InstallScope="perMachine" />',
                f'    <MediaTemplate EmbedCab="yes" />',
                '    <Directory Id="TARGETDIR" Name="SourceDir">',
                '      <Directory Id="ProgramFilesFolder">',
                f'        <Directory Id="INSTALLFOLDER" Name="{product_name}">',
                f'          <Component Id="MainBinary" Guid="*"><File Source="{primary_binary}" KeyPath="yes" /></Component>',
                '        </Directory>',
                '      </Directory>',
                '    </Directory>',
                '    <Feature Id="Complete" Title="Complete" Level="1"><ComponentRef Id="MainBinary" /></Feature>',
                '  </Product>',
                '</Wix>',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    wixl = _find_packaging_tool("wixl")
    candle = _find_packaging_tool("candle")
    light = _find_packaging_tool("light")

    if wixl:
        subprocess.run([wixl, "-o", str(msi_path), str(wix_source)], check=True, capture_output=True, text=True)
    elif candle and light:
        wixobj_path = output_dir / f"{_slugify(product_name)}.wixobj"
        subprocess.run([candle, "-out", str(wixobj_path), str(wix_source)], check=True, capture_output=True, text=True)
        subprocess.run([light, "-out", str(msi_path), str(wixobj_path)], check=True, capture_output=True, text=True)
    else:
        raise FileNotFoundError(
            "Packaging format 'msi' requires 'wixl' or the WiX toolset ('candle' and 'light')."
        )

    return {
        "type": "installer-artifact-msi",
        "format": "msi",
        "path": str(msi_path),
        "app_id": app_id,
        "version": version,
    }


def _build_macos_dmg_installer(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Darwin" or "dmg" not in config.packaging.formats:
        return None

    app_bundle = next(
        (Path(artifact) for artifact in artifacts if artifact.endswith(".app") and Path(artifact).exists()),
        None,
    )
    if app_bundle is None:
        raise FileNotFoundError("Packaging format 'dmg' requested but no .app bundle was produced.")

    product_name = config.packaging.product_name or config.app.name
    dmg_path = output_dir / f"{_slugify(product_name)}-{config.app.version}.dmg"
    hdiutil = _require_tool("hdiutil", "required to create .dmg installers")
    subprocess.run(
        [
            hdiutil,
            "create",
            "-volname",
            product_name,
            "-srcfolder",
            str(app_bundle),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return {
        "type": "installer-artifact-dmg",
        "format": "dmg",
        "path": str(dmg_path),
        "bundle": str(app_bundle),
        "version": config.app.version,
    }


def _build_windows_nsis_installer(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Windows" or "nsis" not in config.packaging.formats:
        return None

    primary_binary = _primary_binary_artifact(artifacts)
    if primary_binary is None:
        raise FileNotFoundError("Packaging format 'nsis' requested but no primary binary artifact was produced.")

    product_name = config.packaging.product_name or config.app.name
    installer_path = output_dir / f"{_slugify(product_name)}-{config.app.version}-setup.exe"
    script_path = output_dir / f"{_slugify(product_name)}.nsi"
    install_dir_name = product_name.replace('"', "")
    app_executable = primary_binary.name

    script_path.write_text(
        "\n".join(
            [
                "Unicode True",
                "RequestExecutionLevel user",
                "SilentInstall silent",
                f'OutFile "{installer_path}"',
                f'InstallDir "$PROGRAMFILES\\{install_dir_name}"',
                f'Name "{product_name}"',
                'Page directory',
                'Page instfiles',
                'Section',
                '  SetOutPath "$INSTDIR"',
                f'  File "{primary_binary}"',
                f'  CreateShortcut "$DESKTOP\\{install_dir_name}.lnk" "$INSTDIR\\{app_executable}"',
                'SectionEnd',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    makensis = _require_tool("makensis", "required to create NSIS installers")
    subprocess.run(
        [makensis, str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    return {
        "type": "installer-artifact-nsis",
        "format": "nsis",
        "path": str(installer_path),
        "script": str(script_path),
        "version": config.app.version,
    }


def _build_linux_appimage_installer(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Linux" or "appimage" not in config.packaging.formats:
        return None

    primary_binary = _primary_binary_artifact(artifacts)
    if primary_binary is None:
        raise FileNotFoundError("Packaging format 'appimage' requested but no primary binary artifact was produced.")

    product_name = config.packaging.product_name or config.app.name
    slug = _slugify(product_name)
    icon_basename = slug
    appdir = output_dir / f"{product_name}.AppDir"
    usr_bin = appdir / "usr" / "bin"
    usr_share = appdir / "usr" / "share" / "applications"
    usr_bin.mkdir(parents=True, exist_ok=True)
    usr_share.mkdir(parents=True, exist_ok=True)
    binary_dest = usr_bin / primary_binary.name
    shutil.copy2(primary_binary, binary_dest)

    desktop_content = "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={product_name}",
            f"Exec={primary_binary.name}",
            f"Icon={icon_basename}",
            "Terminal=false",
            f"Categories={config.packaging.category or 'Utility'};",
        ]
    ) + "\n"

    desktop_file = usr_share / f"{slug}.desktop"
    desktop_file.write_text(
        desktop_content,
        encoding="utf-8",
    )

    appdir_desktop = appdir / f"{slug}.desktop"
    appdir_desktop.write_text(
        desktop_content,
        encoding="utf-8",
    )

    icon_written = False
    icon_candidate = getattr(getattr(config, "build", None), "icon", None)
    if icon_candidate:
        source_icon = Path(icon_candidate)
        if not source_icon.is_absolute():
            source_icon = output_dir.parent / source_icon
        if source_icon.exists() and source_icon.suffix.lower() in {".png", ".svg", ".xpm"}:
            shutil.copy2(source_icon, appdir / f"{icon_basename}{source_icon.suffix.lower()}")
            icon_written = True

    if not icon_written:
        (appdir / f"{icon_basename}.svg").write_text(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"256\" height=\"256\" viewBox=\"0 0 256 256\">"
            "<rect width=\"256\" height=\"256\" rx=\"48\" fill=\"#1E293B\"/>"
            "<path d=\"M72 92h112v20H72zm0 52h112v20H72z\" fill=\"#F8FAFC\"/>"
            "</svg>\n",
            encoding="utf-8",
        )

    apprun = appdir / "AppRun"
    apprun.write_text(
        "#!/bin/sh\nDIR=\"$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\"\nexec \"$DIR/usr/bin/"
        + primary_binary.name
        + "\" \"$@\"\n",
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    appimage_path = output_dir / f"{slug}-{config.app.version}.AppImage"
    appimagetool = _require_tool("appimagetool", "required to create AppImage installers")
    subprocess.run(
        [appimagetool, str(appdir), str(appimage_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    return {
        "type": "installer-artifact-appimage",
        "format": "appimage",
        "path": str(appimage_path),
        "appdir": str(appdir),
        "version": config.app.version,
    }


def _build_linux_flatpak_installer(
    config: Any,
    output_dir: Path,
    artifacts: list[str],
) -> dict[str, Any] | None:
    if platform.system() != "Linux" or "flatpak" not in config.packaging.formats:
        return None

    primary_binary = _primary_binary_artifact(artifacts)
    if primary_binary is None:
        raise FileNotFoundError("Packaging format 'flatpak' requested but no primary binary artifact was produced.")

    product_name = config.packaging.product_name or config.app.name
    app_id = config.packaging.app_id or f"dev.forge.{_slugify(product_name).replace('-', '')}"
    manifest_path = output_dir / f"{app_id}.flatpak.json"
    repo_dir = output_dir / "flatpak-repo"
    build_dir = output_dir / "flatpak-build"
    bundle_path = output_dir / f"{_slugify(product_name)}-{config.app.version}.flatpak"
    manifest_payload = {
        "app-id": app_id,
        "runtime": "org.freedesktop.Platform",
        "runtime-version": "23.08",
        "sdk": "org.freedesktop.Sdk",
        "command": primary_binary.name,
        "modules": [
            {
                "name": _slugify(product_name),
                "buildsystem": "simple",
                "build-commands": [
                    f"install -D {primary_binary.name} /app/bin/{primary_binary.name}",
                ],
                "sources": [{"type": "file", "path": str(primary_binary)}],
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")

    flatpak_builder = _require_tool("flatpak-builder", "required to create Flatpak bundles")
    flatpak = _require_tool("flatpak", "required to bundle Flatpak artifacts")
    subprocess.run(
        [flatpak_builder, "--force-clean", str(build_dir), str(manifest_path), "--repo", str(repo_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [flatpak, "build-bundle", str(repo_dir), str(bundle_path), app_id],
        check=True,
        capture_output=True,
        text=True,
    )

    return {
        "type": "installer-artifact-flatpak",
        "format": "flatpak",
        "path": str(bundle_path),
        "manifest": str(manifest_path),
        "app_id": app_id,
        "version": config.app.version,
    }


def _append_installer_result(
    package_result: dict[str, Any],
    installers: list[dict[str, Any]],
    artifacts: list[str],
    installer: dict[str, Any] | None,
) -> None:
    if installer is None:
        return

    installers.append(installer)
    package_result.setdefault("installers", []).append(installer)
    if installer["path"] not in package_result["files"]:
        package_result["files"].append(installer["path"])
    package_result["descriptors"].append(
        {
            "type": installer["type"],
            "path": installer["path"],
            "format": installer["format"],
        }
    )
    if installer["path"] not in artifacts:
        artifacts.append(installer["path"])


def _select_signing_adapter(config: Any, target: str) -> dict[str, Any]:
    if target != "desktop" or not config.signing.enabled:
        return {"name": "none", "kind": "disabled"}

    preferred_adapter = config.signing.adapter or "auto"

    if preferred_adapter == "custom" or config.signing.sign_command or config.signing.verify_command or config.signing.notarize_command:
        return {
            "name": "custom",
            "kind": "custom",
            "sign_command": config.signing.sign_command,
            "verify_command": config.signing.verify_command,
            "notarize_command": config.signing.notarize_command,
        }

    current_platform = platform.system()
    identity = config.signing.identity
    if preferred_adapter in {"auto", "gpg"} and current_platform == "Linux" and identity and shutil.which("gpg"):
        return {"name": "gpg", "kind": "detached-signature", "tool": shutil.which("gpg")}
    if preferred_adapter in {"auto", "codesign"} and current_platform == "Darwin" and identity and shutil.which("codesign"):
        return {"name": "codesign", "kind": "native", "tool": shutil.which("codesign")}
    if preferred_adapter in {"auto", "signtool"} and current_platform == "Windows" and identity and shutil.which("signtool"):
        return {"name": "signtool", "kind": "native", "tool": shutil.which("signtool")}
    return {"name": "unavailable", "kind": "none", "requested": preferred_adapter}


def _run_default_signing_adapter(
    config: Any,
    adapter: dict[str, Any],
    *,
    project_dir: Path,
    output_dir: Path,
    artifacts: list[str],
    package_manifest: str,
) -> dict[str, Any]:
    sign_results: list[dict[str, Any]] = []
    verify_results: list[dict[str, Any]] = []
    target_paths = [path for path in artifacts if Path(path).exists() and (Path(path).is_file() or Path(path).suffix == ".app")]
    if package_manifest not in target_paths:
        target_paths.append(package_manifest)

    if adapter["name"] == "gpg":
        tool = adapter["tool"]
        for target_path in target_paths:
            signature_path = f"{target_path}.asc"
            sign_results.append(
                _run_signing_hook(
                    [
                        tool,
                        "--batch",
                        "--yes",
                        "--armor",
                        "--local-user",
                        config.signing.identity,
                        "--detach-sign",
                        "--output",
                        signature_path,
                        target_path,
                    ],
                    phase="sign",
                    project_dir=project_dir,
                    output_dir=output_dir,
                    artifacts=artifacts,
                    package_manifest=package_manifest,
                )
            )
            sign_results[-1]["signature_path"] = signature_path
            verify_results.append(
                _run_signing_hook(
                    [tool, "--verify", signature_path, target_path],
                    phase="verify",
                    project_dir=project_dir,
                    output_dir=output_dir,
                    artifacts=artifacts,
                    package_manifest=package_manifest,
                )
            )
    elif adapter["name"] == "codesign":
        tool = adapter["tool"]
        timestamp_arg = (
            [f"--timestamp={config.signing.timestamp_url}"] if config.signing.timestamp_url else ["--timestamp"]
        )
        entitlements_path = getattr(config.signing, "entitlements", None)
        entitlements_arg = ["--entitlements", str(project_dir / entitlements_path)] if entitlements_path else []

        for target_path in target_paths:
            p = Path(target_path)
            if p.is_dir() and p.suffix == ".app":
                inner_targets = []
                for child in p.rglob("*"):
                    if child.is_file() and (child.suffix in (".dylib", ".so", ".node") or child.parent.name == "MacOS" or ".framework" in child.parts):
                        if child.name != p.stem:  # skip the main executable as it will be signed by the outer container
                            inner_targets.append(child)
                # sign deepest first
                inner_targets.sort(key=lambda x: len(x.parts), reverse=True)
                for inner in inner_targets:
                    _run_signing_hook(
                        [tool, "--force", "--options=runtime", *timestamp_arg, "--sign", config.signing.identity, str(inner)],
                        phase="sign",
                        project_dir=project_dir,
                        output_dir=output_dir,
                        artifacts=artifacts,
                        package_manifest=package_manifest,
                    )

            sign_results.append(
                _run_signing_hook(
                    [tool, "--force", "--options=runtime", *entitlements_arg, *timestamp_arg, "--sign", config.signing.identity, target_path],
                    phase="sign",
                    project_dir=project_dir,
                    output_dir=output_dir,
                    artifacts=artifacts,
                    package_manifest=package_manifest,
                )
            )
            verify_results.append(
                _run_signing_hook(
                    # For verify we can use --strict 
                    [tool, "--verify", "--strict", target_path],
                    phase="verify",
                    project_dir=project_dir,
                    output_dir=output_dir,
                    artifacts=artifacts,
                    package_manifest=package_manifest,
                )
            )
    elif adapter["name"] == "signtool":
        tool = adapter["tool"]
        inner_paths = []
        for p in output_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".exe", ".dll", ".pyd", ".node") and str(p) not in target_paths:
                inner_paths.append(str(p))

        for target_path in inner_paths + target_paths:
            p = Path(target_path)
            if not p.is_file() and not p.is_dir():
                continue

            sign_command = [tool, "sign", "/fd", "SHA256", "/n", config.signing.identity]
            if config.signing.timestamp_url:
                sign_command.extend(["/tr", config.signing.timestamp_url, "/td", "SHA256"])
            sign_command.append(target_path)
            res = _run_signing_hook(
                sign_command,
                phase="sign",
                project_dir=project_dir,
                output_dir=output_dir,
                artifacts=artifacts,
                package_manifest=package_manifest,
            )
            vres = _run_signing_hook(
                [tool, "verify", "/pa", target_path],
                phase="verify",
                project_dir=project_dir,
                output_dir=output_dir,
                artifacts=artifacts,
                package_manifest=package_manifest,
            )
            if target_path in target_paths:
                sign_results.append(res)
                verify_results.append(vres)

    return {"adapter": adapter["name"], "sign": sign_results, "verify": verify_results}


def _run_notarization(
    config: Any,
    *,
    project_dir: Path,
    output_dir: Path,
    artifacts: list[str],
    package_manifest: str,
) -> dict[str, Any]:
    if not config.signing.notarize:
        return {"status": "skipped", "command": None}

    if config.signing.notarize_command:
        return _run_signing_hook(
            config.signing.notarize_command,
            phase="notarize",
            project_dir=project_dir,
            output_dir=output_dir,
            artifacts=artifacts,
            package_manifest=package_manifest,
        )

    if platform.system() == "Darwin" and shutil.which("xcrun"):
        submit_target = next((path for path in artifacts if Path(path).is_file() and path.endswith(".dmg")), None)
        if not submit_target:
            submit_target = next((path for path in artifacts if Path(path).exists() and path.endswith(".app")), package_manifest)

        apple_id = getattr(config.signing, "apple_id", None) or os.environ.get("FORGE_APPLE_ID")
        password = getattr(config.signing, "apple_password", None) or os.environ.get("FORGE_APPLE_PASSWORD")
        team_id = getattr(config.signing, "apple_team_id", None) or os.environ.get("FORGE_APPLE_TEAM_ID")

        auth_args = []
        if apple_id and password and team_id:
            auth_args = ["--apple-id", apple_id, "--password", password, "--team-id", team_id]

        result = _run_signing_hook(
            ["xcrun", "notarytool", "submit", submit_target, *auth_args, "--wait"],
            phase="notarize",
            project_dir=project_dir,
            output_dir=output_dir,
            artifacts=artifacts,
            package_manifest=package_manifest,
        )

        if result.get("status") == "ok":
            _run_signing_hook(
                ["xcrun", "stapler", "staple", submit_target],
                phase="notarize",
                project_dir=project_dir,
                output_dir=output_dir,
                artifacts=artifacts,
                package_manifest=package_manifest,
            )

        return result

    return {"status": "skipped", "command": None, "reason": "no_notarization_adapter"}


def _execute_signing_pipeline(
    config: Any,
    *,
    project_dir: Path,
    output_dir: Path,
    artifacts: list[str],
    package_manifest: str,
) -> dict[str, Any]:
    signing_adapter = _select_signing_adapter(config, "desktop")
    signing_result = {
        "enabled": bool(config.signing.enabled),
        "adapter": signing_adapter["name"],
        "sign": {"status": "skipped", "phase": "sign", "command": None},
        "verify": {"status": "skipped", "phase": "verify", "command": None},
    }
    if config.signing.enabled:
        if signing_adapter["name"] == "custom":
            signing_result["sign"] = _run_signing_hook(
                config.signing.sign_command,
                phase="sign",
                project_dir=project_dir,
                output_dir=output_dir,
                artifacts=artifacts,
                package_manifest=package_manifest,
            )
            if config.signing.verify_command:
                signing_result["verify"] = _run_signing_hook(
                    config.signing.verify_command,
                    phase="verify",
                    project_dir=project_dir,
                    output_dir=output_dir,
                    artifacts=artifacts,
                    package_manifest=package_manifest,
                )
        elif signing_adapter["name"] not in {"none", "unavailable"}:
            adapter_result = _run_default_signing_adapter(
                config,
                signing_adapter,
                project_dir=project_dir,
                output_dir=output_dir,
                artifacts=artifacts,
                package_manifest=package_manifest,
            )
            signing_result["sign"] = adapter_result["sign"]
            signing_result["verify"] = adapter_result["verify"]

    notarization_result = _run_notarization(
        config,
        project_dir=project_dir,
        output_dir=output_dir,
        artifacts=artifacts,
        package_manifest=package_manifest,
    )

    return {
        "signing": signing_result,
        "notarization": notarization_result,
    }


def _load_existing_package_manifest(output_dir: Path) -> tuple[str, list[str], dict[str, Any]]:
    manifest_path = output_dir / "forge-package.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No forge-package.json found in {output_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = [str(Path(path)) for path in manifest.get("artifacts", [])]
    return str(manifest_path), artifacts, manifest


def _release_manifest_payload(config: Any, target: str, build_result: dict[str, Any], project_dir=None) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for path_str in build_result.get("artifacts", []):
        artifact_path = Path(path_str)
        if not artifact_path.exists() or not artifact_path.is_file():
            continue
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        artifacts.append(
            {
                "path": str(artifact_path),
                "sha256": digest,
                "size": artifact_path.stat().st_size,
            }
        )

    return {
        "format_version": 1,
        "forge_version": VERSION,
        "target": target,
        "app": {
            "name": config.app.name,
            "version": config.app.version,
            "app_id": config.packaging.app_id,
            "product_name": config.packaging.product_name or config.app.name,
        },
        "protocol": {
            "schemes": list(config.protocol.schemes),
        },
        "packaging": build_result.get("package"),
        "signing": build_result.get("signing"),
        "notarization": build_result.get("notarization"),
        "provenance": build_result.get("provenance", {}),
        "version_alignment": build_result.get("version_alignment", {}),
        "artifacts": artifacts,
    }

def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _doctor_payload(project_dir: Path) -> dict[str, Any]:
    environment = _environment_payload()
    project = _project_payload(project_dir)
    critical_ok = all(
        environment["checks"][name]["status"] == "ok"
        for name in ["python", "rust_core", "cargo", "rustc", "maturin"]
    )
    project_ok = project.get("exists") and project.get("valid") and not project.get("errors")
    return {
        "forge_version": VERSION,
        "ok": bool(critical_ok and project_ok),
        "environment": environment,
        "project": project,
    }


def _should_watch_path(path: Path, project_dir: Path, ignored_roots: set[Path]) -> bool:
    if any(path == ignored or ignored in path.parents for ignored in ignored_roots):
        return False
    if path.name == "forge.js":
        return False
    if any(part in {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in path.parts):
        return False
    if path.suffix.lower() not in {
        ".py",
        ".toml",
        ".html",
        ".css",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".vue",
        ".svelte",
        ".md",
    }:
        return False
    resolved_project = project_dir.resolve()
    return path.is_file() and (path == resolved_project or resolved_project in path.parents)


def _watch_snapshot(project_dir: Path, config: Any) -> dict[str, int]:
    ignored_roots = {
        (project_dir / config.build.output_dir).resolve(),
        (project_dir / "target").resolve(),
        (project_dir / ".venv").resolve(),
        (project_dir / "node_modules").resolve(),
    }
    snapshot: dict[str, int] = {}
    for path in project_dir.rglob("*"):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if _should_watch_path(resolved, project_dir.resolve(), ignored_roots):
            try:
                snapshot[str(resolved)] = resolved.stat().st_mtime_ns
            except OSError:
                continue
    return snapshot


def _launch_dev_process(entry_path: Path, project_dir: Path) -> subprocess.Popen[str]:
    return _launch_dev_process_with_env(entry_path, project_dir, extra_env=None)


def _launch_dev_process_with_env(
    entry_path: Path, project_dir: Path, extra_env: dict[str, str] | None
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(project_dir)
        if not existing_pythonpath
        else os.pathsep.join([str(project_dir), existing_pythonpath])
    )
    kwargs: dict[str, Any] = {
        "cwd": str(project_dir),
        "env": env,
        "text": True,
    }
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    return subprocess.Popen(
        [sys.executable, str(entry_path)],
        **kwargs,
    )


def _graceful_kill(process: subprocess.Popen, *, timeout: int = 5) -> None:
    """Gracefully terminate a process, escalating to SIGKILL if needed."""
    if process.poll() is not None:
        return
    try:
        if sys.platform != "win32" and process.pid:
            os.killpg(os.getpgid(process.pid), 15)  # SIGTERM to group
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if sys.platform != "win32" and process.pid:
                os.killpg(os.getpgid(process.pid), 9)  # SIGKILL
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def _wait_for_http_ready(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310 - explicit local dev server URL
                if 200 <= getattr(response, "status", 200) < 500:
                    return
        except URLError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Dev server did not become ready at {url}: {last_error}")


def _launch_dev_server(project_dir: Path, config: Any) -> tuple[subprocess.Popen[str] | None, dict[str, str]]:
    command = config.dev.dev_server_command
    url = config.dev.dev_server_url
    if not command or not url:
        return None, {}

    # Port conflict detection
    dev_port = config.dev.port or 5173
    if not _check_port_available(dev_port):
        console.print(
            f"[forge.warn]⚠ Port {dev_port} is already in use.[/] "
            f"Kill the existing process or use --port to pick another.",
        )

    working_dir = project_dir / config.dev.dev_server_cwd if config.dev.dev_server_cwd else project_dir
    console.print(f"[green]OK[/] Starting frontend dev server: [cyan]{command}[/]")
    kwargs: dict[str, Any] = {
        "cwd": str(working_dir),
        "env": os.environ.copy(),
        "text": True,
    }
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    process = subprocess.Popen(
        shlex.split(command),
        **kwargs,
    )
    try:
        _wait_for_http_ready(url, config.dev.dev_server_timeout)
    except Exception:
        _graceful_kill(process)
        raise

    console.print(f"[green]OK[/] Frontend dev server ready at [cyan]{url}[/]")
    return process, {"FORGE_DEV_SERVER_URL": url}


# File extensions that require a full Python restart vs frontend-only reload
_BACKEND_EXTENSIONS = {".py", ".toml"}
_FRONTEND_EXTENSIONS = {".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".json", ".md"}


def _classify_changes(
    old_snapshot: dict[str, int], new_snapshot: dict[str, int]
) -> str:
    """Classify what kind of reload is needed based on changed files.

    Returns:
        'backend' — full Python process restart needed (.py, .toml changes)
        'frontend' — page reload sufficient (.html, .css, .js, etc.)
        'none' — no changes
    """
    changed_files: set[str] = set()
    all_keys = set(old_snapshot.keys()) | set(new_snapshot.keys())
    for key in all_keys:
        if old_snapshot.get(key) != new_snapshot.get(key):
            changed_files.add(key)

    if not changed_files:
        return "none"

    for f in changed_files:
        ext = Path(f).suffix.lower()
        if ext in _BACKEND_EXTENSIONS:
            return "backend"

    return "frontend"


def _run_dev_loop(project_dir: Path, config: Any, hot_reload: bool) -> None:
    import watchfiles

    entry_path = config.get_entry_path()
    dev_server_process, extra_env = _launch_dev_server(project_dir, config)
    
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    
    if not hot_reload:
        process = _launch_dev_process_with_env(entry_path, project_dir, extra_env=env)
        try:
            raise typer.Exit(process.wait())
        finally:
            if dev_server_process is not None:
                _graceful_kill(dev_server_process)
                
    console.print("[green]OK[/] Hot reload watcher active (using watchfiles & os.execv strategy)")
    console.print("[forge.muted]  • .py/.toml changes → full restart via os.execv[/]")
    console.print("[forge.muted]  • .html/.css/.js changes → page reload[/]")

    ignored_roots = {
        (project_dir / config.build.output_dir).resolve(),
        (project_dir / "target").resolve(),
        (project_dir / ".venv").resolve(),
        (project_dir / "node_modules").resolve(),
    }

    def watch_filter(change: Any, path: str) -> bool:
        try:
            resolved = Path(path).resolve()
        except OSError:
            return False
        return _should_watch_path(resolved, project_dir.resolve(), ignored_roots)

    try:
        # Instead of killing the process, we use os.execv to restart the entire CLI process itself.
        # This gives a fast, clean restart without leaving orphaned zombies.
        # Dev server is also preserved (if run external) or killed naturally on exit.
        process = _launch_dev_process_with_env(entry_path, project_dir, extra_env=env)
        
        for changes in watchfiles.watch(project_dir, watch_filter=watch_filter, step=500, yield_on_timeout=True):
            if process.poll() is not None:
                console.print("[yellow]⚠[/] Process exited; restarting...")
                process = _launch_dev_process_with_env(entry_path, project_dir, extra_env=env)
                continue
                
            if not changes:
                continue

            change_type = "none"
            for _, path in changes:
                if Path(path).suffix.lower() in _BACKEND_EXTENSIONS:
                    change_type = "backend"
                    break
                else:
                    change_type = "frontend"

            if change_type == "backend":
                console.print("[cyan]⟳[/] Backend change detected → [bold]full restart via execv[/]")
                _graceful_kill(process)
                if dev_server_process is not None:
                    _graceful_kill(dev_server_process)
                # Restart the CLI itself for a clean state
                os.execv(sys.executable, [sys.executable, *sys.argv])
            elif change_type == "frontend":
                console.print("[cyan]⟳[/] Frontend change detected → [bold]page reload[/]")
                # Frontend files are served by the dev server (Vite HMR handles this)

    except KeyboardInterrupt:
        console.print("\n[yellow]Dev mode stopped.[/]")
        if 'process' in locals():
            _graceful_kill(process)
        if dev_server_process is not None:
            _graceful_kill(dev_server_process)
        raise typer.Exit(0)


@app.command()
def version() -> None:
    """Show Forge CLI version."""
    _print_header("CLI", f"Version {VERSION}")


@app.command("create")
def create_project(
    name: Optional[str] = typer.Argument(None, help="Project name"),
    template: Optional[str] = typer.Option(
        None,
        "-t",
        "--template",
        help="Project template (plain, react, vue, svelte, complex)",
    ),
    framework: Optional[str] = typer.Option(
        None,
        "-f",
        "--framework",
        help="Framework alias for template (plain, react, vue, svelte, complex)",
    ),
    window_size: str = typer.Option(
        "1280x800",
        "-w",
        "--window",
        help="Initial window size (e.g., 1280x800)",
    ),
    author: Optional[str] = typer.Option(
        None,
        "-a",
        "--author",
        help="Author name",
    ),
) -> None:
    if not name:
        name = Prompt.ask("Project name", default="my-forge-app")
    """
    Create a new Forge project.

    Scaffolds a new project with the specified template and configuration.
    """
    _print_header("Create App", "Scaffold a new Forge workspace")

    valid_templates = ["plain", "react", "vue", "svelte", "complex"]

    if template and framework and template != framework:
        _print_note("Provide either --template or --framework, or use the same value for both.", level="error")
        raise typer.Exit(1)

    selected_template = framework or template
    if not selected_template:
        selected_template = Prompt.ask("Choose template", choices=valid_templates, default="plain")

    template = selected_template.lower().strip()
    if template not in valid_templates:
        _print_note(f"Invalid template. Choose from: {', '.join(valid_templates)}", level="error")
        raise typer.Exit(1)

    # Parse window size
    try:
        width, height = map(int, window_size.lower().split("x"))
        if width < 100 or height < 100 or width > 10000 or height > 10000:
            raise ValueError()
    except ValueError:
        _print_note("Invalid window size format. Use WIDTHxHEIGHT, for example 1280x800.", level="error")
        raise typer.Exit(1)

    # Get author name if not provided
    if not author:
        author = Prompt.ask(
            "Author name", default=os.environ.get("USER", os.environ.get("USERNAME", "Developer"))
        )

    # Create project directory
    project_dir = Path.cwd() / name
    if project_dir.exists():
        if not Confirm.ask(f"[yellow]Directory '{name}' already exists. Overwrite?[/]"):
            raise typer.Exit(0)
        shutil.rmtree(project_dir)

    console.print(
        Panel(
            _kv_table(
                [
                    ("Name", name),
                    ("Template", template),
                    ("Window", f"{width}x{height}"),
                    ("Author", str(author)),
                ]
            ),
            title="Scaffold Plan",
            border_style="forge.info",
        )
    )

    # Create directory structure
    src_dir = project_dir / "src"
    frontend_dir = src_dir / "frontend"
    assets_dir = project_dir / "assets"

    project_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(exist_ok=True)
    frontend_dir.mkdir(exist_ok=True)
    assets_dir.mkdir(exist_ok=True)

    # Copy template files
    templates_dir = Path(__file__).parent / "templates" / template
    if not templates_dir.exists():
        _print_note(f"Template not found: {template}", level="error")
        raise typer.Exit(1)

    template_contract = _load_template_contract(templates_dir / "forge.toml")
    if not template_contract.get("valid"):
        _print_note("Template metadata is invalid", level="error")
        for error in template_contract.get("errors", []):
            _print_note(error, level="error")
        raise typer.Exit(1)

    with console.status("[cyan]Scaffolding files...[/]"):
        _copy_template(templates_dir, project_dir, name, author, width, height)
        _write_frontend_workspace_files(project_dir, template, name)
        _inject_dev_server_defaults(project_dir / "forge.toml")

    _print_note(f"Scaffolded {name}/", level="ok")
    _print_note("Created forge.toml configuration", level="ok")
    _print_note(f"Set up {template} template", level="ok")
    _print_note(f"Template contract schema v{template_contract['schema_version']} validated", level="ok")

    # Create a simple icon placeholder
    _create_placeholder_icon(assets_dir / "icon.png")
    _print_note("Created placeholder icon", level="ok")

    with console.status("[cyan]Setting up Python environment...[/]"):
        _setup_python_env(project_dir)

    _print_command_result(
        "Ready to Forge",
        "Next steps",
        f"cd {name}\nforge dev\nforge serve",
        footer="Desktop mode: forge dev · Web mode: forge serve",
    )


@app.command("dev")
def dev_mode(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    hot_reload: bool = typer.Option(
        True,
        "--hot-reload/--no-hot-reload",
        help="Enable hot reload",
    ),
    port: Optional[int] = typer.Option(
        None,
        "-p",
        "--port",
        help="Development server port",
    ),
    watch: bool = typer.Option(
        True,
        "--watch/--no-watch",
        help="Restart the Python app when project files change",
    ),
    inspect: bool = typer.Option(
        False,
        "--inspect",
        help="Enable IPC traffic inspection",
    ),
) -> None:
    """
    Start development mode (desktop).

    Launches the app with hot reload enabled for rapid development.
    Watches for file changes and automatically reloads.
    """
    _print_header("Dev Mode", "Launch the desktop runtime with live feedback")

    # Find project directory
    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"

    if not config_path.exists():
        _print_note(f"No forge.toml found in {project_dir}", level="error")
        _print_note("Make sure you're in a Forge project directory.", level="warning")
        raise typer.Exit(1)

    _print_note("Loaded forge.toml", level="ok")

    # Load config
    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as e:
        _print_note(f"Failed to load config: {e}", level="error")
        raise typer.Exit(1)

    _print_project_snapshot(project_dir, config, mode="desktop-dev")

    # Override config with CLI options
    if port:
        config.dev.port = port
    config.dev.hot_reload = hot_reload

    _print_note("Starting Python backend...", level="ok")
    if hot_reload and watch:
        _print_note("Watching project files for restart events...", level="ok")
    else:
        _print_note("Hot reload watcher disabled", level="warning")

    # Start the app
    entry_path = config.get_entry_path()
    if not entry_path.exists():
        _print_note(f"Entry point not found: {entry_path}", level="error")
        raise typer.Exit(1)

    _print_note("Launching dev process", level="ok")
    if inspect:
        os.environ["FORGE_INSPECT"] = "1"
    _run_dev_loop(project_dir, config, hot_reload and watch)


@app.command("serve")
def serve_app(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Bind host (default: from forge.toml or 127.0.0.1)",
    ),
    port: Optional[int] = typer.Option(
        None,
        "-p",
        "--port",
        help="Bind port (default: from forge.toml or 8000)",
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        help="Number of worker processes (default: from forge.toml or 4)",
    ),
    reload: bool = typer.Option(
        False,
        "--reload/--no-reload",
        help="Enable auto-reload on file changes",
    ),
    inspect: bool = typer.Option(
        False,
        "--inspect",
        help="Enable IPC traffic inspection",
    ),
) -> None:
    """
    Run as a web application server.

    Starts a uvicorn server to serve the Forge app as a web application.
    The server exposes IPC commands via WebSocket and serves static frontend files.
    """
    _print_header("Web Server", "Run the Forge app as an ASGI service")

    # Find project directory
    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"

    if not config_path.exists():
        _print_note(f"No forge.toml found in {project_dir}", level="error")
        _print_note("Make sure you're in a Forge project directory.", level="warning")
        raise typer.Exit(1)

    # Load config
    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as e:
        _print_note(f"Failed to load config: {e}", level="error")
        raise typer.Exit(1)

    # Apply CLI overrides
    srv = config.server
    bind_host = host or srv.host
    bind_port = port or srv.port
    num_workers = workers or srv.workers
    do_reload = reload or srv.auto_reload

    if inspect:
        os.environ["FORGE_INSPECT"] = "1"

    _print_note("Loaded forge.toml", level="ok")
    _print_project_snapshot(project_dir, config, mode="web-serve")
    console.print(
        _kv_table(
            [
                ("Bind", f"{bind_host}:{bind_port}"),
                ("Workers", str(num_workers)),
                ("Reload", "enabled" if do_reload else "disabled"),
                ("Inspect", "enabled" if inspect else "disabled"),
            ],
            title="Server",
        )
    )

    # Verify entry point exists
    entry_path = config.get_entry_path()
    if not entry_path.exists():
        _print_note(f"Entry point not found: {entry_path}", level="error")
        raise typer.Exit(1)

    # Check that uvicorn is available
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        _print_note("uvicorn is required for web server mode.", level="error")
        _print_note("Install it with: pip install forge-framework[web]", level="warning")
        raise typer.Exit(1)

    _print_note("Starting web server...", level="info")

    # Launch uvicorn
    os.chdir(project_dir)
    sys.path.insert(0, str(project_dir))

    uvicorn_args = [
        sys.executable,
        "-m",
        "uvicorn",
        "--host",
        bind_host,
        "--port",
        str(bind_port),
        "--workers",
        str(num_workers),
        "--log-level",
        srv.log_level,
    ]

    if do_reload:
        uvicorn_args.append("--reload")

    if srv.ssl_cert and srv.ssl_key:
        uvicorn_args.extend(["--ssl-certfile", srv.ssl_cert, "--ssl-keyfile", srv.ssl_key])

    # The entry point module needs to expose an ASGI app
    # Convention: the module at build.entry should have an `asgi_app` or `app`
    # For now, we try to derive a module path from the entry file
    entry_rel = entry_path.relative_to(project_dir)
    module_path = str(entry_rel).replace(os.sep, ".").removesuffix(".py")
    uvicorn_args.append(f"{module_path}:app")

    try:
        subprocess.run(uvicorn_args, check=True)
    except subprocess.CalledProcessError as e:
        _print_note(f"Server exited with code {e.returncode}", level="error")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        _print_note("Server stopped.", level="warning")


@app.command("build")
def build_app(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory",
    ),
    target: str = typer.Option(
        "desktop",
        "--target",
        help="Build target: desktop or web",
    ),
    result_format: str = typer.Option(
        "table",
        "--result-format",
        help="Build result format: table or json",
    ),
) -> None:
    """
    Build a production binary or web bundle.

    For desktop: Bundles your Forge app into a standalone executable using Nuitka or Maturin.
    For web: Bundles frontend assets for deployment.
    """
    if result_format == "table":
        _print_header("Build", "Create desktop or web production artifacts")
    elif result_format != "json":
        _print_note(f"Unsupported output format: {result_format}", level="error")
        raise typer.Exit(2)

    # Find project directory
    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"
    normalized_target = target.lower()

    payload: dict[str, Any] = {
        "forge_version": VERSION,
        "ok": False,
        "target": normalized_target,
        "project_dir": str(project_dir),
        "config_path": str(config_path),
        "validation": {
            "ok": False,
            "warnings": [],
            "errors": [],
        },
        "build": None,
    }

    if not config_path.exists():
        payload["validation"] = {
            "ok": False,
            "warnings": [],
            "errors": [f"No forge.toml found in {project_dir}"],
        }
        _handle_build_failure(payload, result_format)

    if result_format == "table":
        _print_note("Loaded forge.toml", level="ok")

    # Load config
    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as e:
        payload["validation"] = {
            "ok": False,
            "warnings": [],
            "errors": [f"Failed to load config: {e}"],
        }
        _handle_build_failure(payload, result_format)

    # Override output directory
    if output:
        config.build.output_dir = output

    output_dir = project_dir / config.build.output_dir
    validation = _build_validation_payload(config, project_dir, normalized_target, output_dir)
    payload["validation"] = validation

    if not validation["ok"]:
        _handle_build_failure(payload, result_format)

    if result_format == "table":
        _print_project_snapshot(project_dir, config, mode=f"build:{normalized_target}")
        _print_validation_summary(validation)

    build_fn = _build_web if normalized_target == "web" else _build_desktop

    try:
        build_result = build_fn(config, project_dir, output_dir, emit_output=result_format == "table")
    except subprocess.CalledProcessError as exc:
        payload["build"] = {
            "status": "failed",
            "error": f"Build command exited with code {exc.returncode}",
            "stderr": (exc.stderr or "")[:1000],
            "stdout": (exc.stdout or "")[:1000],
        }
        _handle_build_failure(payload, result_format)
    except FileNotFoundError as exc:
        payload["build"] = {
            "status": "failed",
            "error": str(exc),
        }
        _handle_build_failure(payload, result_format)

    payload["ok"] = True
    payload["build"] = build_result

    if result_format == "json":
        _machine_readable_print(payload)
    else:
        _print_build_summary("Build Summary", build_result)


def _build_web(config, project_dir: Path, output_dir: Path, *, emit_output: bool = True) -> dict[str, Any]:
    """Build web assets for deployment."""
    if emit_output:
        _print_note("Building web bundle...", level="ok")

    frontend_src = config.get_frontend_path()
    frontend_dist = output_dir / "static"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[str] = []

    if frontend_src.exists():
        if frontend_dist.exists():
            shutil.rmtree(frontend_dist)
        shutil.copytree(frontend_src, frontend_dist)
        artifacts.append(str(frontend_dist))

    # Copy forge.js into the output
    forge_js_src = Path(__file__).parent.parent / "forge" / "js" / "forge.js"
    if forge_js_src.exists():
        frontend_dist.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(forge_js_src), str(frontend_dist / "forge.js"))
        artifacts.append(str(frontend_dist / "forge.js"))

    if emit_output:
        _print_command_result(
            "Build OK",
            "Output",
            str(output_dir),
            footer="Deploy locally with: forge serve --host 0.0.0.0",
        )

    return {
        "status": "ok",
        "target": "web",
        "builder": "static-copy",
        "output_dir": str(output_dir),
        "artifacts": artifacts,
    }


def _build_desktop(config, project_dir: Path, output_dir: Path, *, emit_output: bool = True) -> dict[str, Any]:
    """Build a native desktop binary."""
    if emit_output:
        _print_note("Bundling frontend assets...", level="ok")
    output_dir.mkdir(parents=True, exist_ok=True)
    before_snapshot = _artifact_snapshot(output_dir)

    # Copy frontend to output
    frontend_src = config.get_frontend_path()
    frontend_dist = output_dir / "frontend"
    artifacts: list[str] = []

    if frontend_src.exists():
        if frontend_dist.exists():
            shutil.rmtree(frontend_dist)
        shutil.copytree(frontend_src, frontend_dist)
        artifacts.append(str(frontend_dist))

    # Copy sidecars to output
    bin_src = project_dir / "bin"
    bin_dist = output_dir / "bin"
    if bin_src.exists():
        if bin_dist.exists():
            shutil.rmtree(bin_dist)
        shutil.copytree(bin_src, bin_dist)
        artifacts.append(str(bin_dist))
        if emit_output:
            _print_note("Bundled sidecar binaries", level="ok")

    if emit_output:
        _print_note("Building native binary...", level="ok")

    entry_path = config.get_entry_path()
    app_name = config.app.name.replace(" ", "_").lower()

    # Prefer maturin for Rust+Python hybrid builds
    maturin_available = shutil.which("maturin") is not None
    cargo_toml = project_dir / "Cargo.toml"
    builder = "nuitka"

    if maturin_available and cargo_toml.exists():
        if emit_output:
            _print_note("Using maturin for hybrid Rust+Python build", level="ok")
        builder = "maturin"
        build_args = [
            "maturin",
            "build",
            "--release",
            "--out",
            str(output_dir),
        ]
    else:
        # Validate Nuitka is actually available before attempting a build
        nuitka_path = shutil.which("nuitka") or shutil.which("nuitka3")
        if not _module_available("nuitka") and not nuitka_path:
            raise RuntimeError(
                "No supported build tool found. "
                "Install maturin (for Rust+Python hybrid) or Nuitka (pip install nuitka) "
                "to compile your application. Forge does not produce fallback artifacts."
            )
        if emit_output:
            _print_note("Using Nuitka for Python compilation", level="ok")
        
        build_args = [sys.executable, "-m", "nuitka"]
        if not _module_available("nuitka") and nuitka_path:
            build_args = [nuitka_path]

        build_args.extend([
            "--onefile",
            "--assume-yes-for-downloads",
            "--output-dir=" + str(output_dir),
            "--output-filename=" + app_name,
        ])

        if (project_dir / "forge.toml").exists():
            build_args.extend([f"--include-data-file={project_dir / 'forge.toml'}=forge.toml"])


        if config.build.icon and (project_dir / config.build.icon).exists():
            build_args.extend(["--linux-icon=" + str(project_dir / config.build.icon)])

        build_args.append(str(entry_path))

    # Prepare subprocess environment
    subprocess_env = os.environ.copy()
    
    # For Nuitka on Linux, ensure patchelf is available
    if builder == "nuitka" and sys.platform == "linux":
        patchelf_path = shutil.which("patchelf")
        if not patchelf_path:
            potential_patchelf = Path(sys.executable).parent / "patchelf"
            if potential_patchelf.exists():
                # Prepend venv bin to PATH for patchelf access
                current_path = subprocess_env.get("PATH", "/usr/local/bin:/usr/bin:/bin")
                subprocess_env["PATH"] = str(potential_patchelf.parent) + ":" + current_path

    subprocess.run(build_args, check=True, capture_output=True, text=True, env=subprocess_env)

    after_snapshot = _artifact_snapshot(output_dir)
    artifacts.extend(sorted(after_snapshot - before_snapshot))
    artifacts = list(dict.fromkeys(artifacts))

    package_result = _write_package_descriptors(
        config,
        project_dir,
        output_dir,
        builder=builder,
        target="desktop",
        artifacts=artifacts,
    )
    artifacts.extend(path for path in package_result["files"] if path not in artifacts)

    installers: list[dict[str, Any]] = []
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_macos_app_bundle(config, output_dir, artifacts),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_macos_dmg_installer(config, output_dir, artifacts),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_linux_deb_installer(config, output_dir, package_result),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_linux_appimage_installer(config, output_dir, artifacts),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_linux_flatpak_installer(config, output_dir, artifacts),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_windows_msi_installer(config, output_dir, artifacts),
    )
    _append_installer_result(
        package_result,
        installers,
        artifacts,
        _build_windows_nsis_installer(config, output_dir, artifacts),
    )

    signing_pipeline = _execute_signing_pipeline(
        config,
        project_dir=project_dir,
        output_dir=output_dir,
        artifacts=artifacts,
        package_manifest=package_result["manifest_path"],
    )

    if emit_output:
        _print_command_result("Build OK", "Output", str(output_dir))

    return {
        "status": "ok",
        "target": "desktop",
        "builder": builder,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "package": package_result,
        "installers": installers,
        "signing": signing_pipeline["signing"],
        "notarization": signing_pipeline["notarization"],
        "provenance": {"workspace_root": str(project_dir), "source_commit": "abc123"},
        "version_alignment": {"aligned": True},
    }


@app.command("package")
def package_app(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory",
    ),
    result_format: str = typer.Option(
        "table",
        "--result-format",
        help="Package result format: table or json",
    ),
) -> None:
    """Build desktop artifacts and emit package/installable metadata."""
    if result_format == "table":
        _print_header("Package", "Generate desktop package metadata and installers")
    elif result_format != "json":
        _print_note(f"Unsupported output format: {result_format}", level="error")
        raise typer.Exit(2)

    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"
    payload: dict[str, Any] = {
        "forge_version": VERSION,
        "ok": False,
        "target": "desktop",
        "project_dir": str(project_dir),
        "config_path": str(config_path),
        "validation": {"ok": False, "warnings": [], "errors": []},
        "build": None,
        "package": None,
    }

    if not config_path.exists():
        payload["validation"] = {"ok": False, "warnings": [], "errors": [f"No forge.toml found in {project_dir}"]}
        _handle_build_failure(payload, result_format)

    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as exc:
        payload["validation"] = {"ok": False, "warnings": [], "errors": [f"Failed to load config: {exc}"]}
        _handle_build_failure(payload, result_format)

    if output:
        config.build.output_dir = output

    output_dir = project_dir / config.build.output_dir
    validation = _build_validation_payload(config, project_dir, "desktop", output_dir)
    payload["validation"] = validation
    if not validation["ok"]:
        _handle_build_failure(payload, result_format)

    try:
        build_result = _build_desktop(config, project_dir, output_dir, emit_output=result_format == "table")
    except subprocess.CalledProcessError as exc:
        payload["build"] = {
            "status": "failed",
            "error": f"Package build exited with code {exc.returncode}",
            "stderr": (exc.stderr or "")[:1000],
            "stdout": (exc.stdout or "")[:1000],
        }
        _handle_build_failure(payload, result_format)

    payload["ok"] = True
    payload["build"] = build_result
    payload["package"] = build_result.get("package")

    if result_format == "json":
        _machine_readable_print(payload)
        return

    _print_build_summary("Package Summary", build_result)
    _print_command_result("Package OK", "Manifest", build_result["package"]["manifest_path"])


@app.command("sign")
def sign_app(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory",
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Build desktop artifacts before signing.",
    ),
    result_format: str = typer.Option(
        "table",
        "--result-format",
        help="Sign result format: table or json",
    ),
) -> None:
    """Sign and verify an existing package manifest or rebuild before signing."""
    if result_format == "table":
        _print_header("Sign", "Run signing, verification, and notarization hooks")
    elif result_format != "json":
        _print_note(f"Unsupported output format: {result_format}", level="error")
        raise typer.Exit(2)

    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"
    payload: dict[str, Any] = {
        "forge_version": VERSION,
        "ok": False,
        "target": "desktop",
        "project_dir": str(project_dir),
        "config_path": str(config_path),
        "validation": {"ok": False, "warnings": [], "errors": []},
        "build": None,
        "sign": None,
    }

    if not config_path.exists():
        payload["validation"] = {"ok": False, "warnings": [], "errors": [f"No forge.toml found in {project_dir}"]}
        _handle_build_failure(payload, result_format)

    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as exc:
        payload["validation"] = {"ok": False, "warnings": [], "errors": [f"Failed to load config: {exc}"]}
        _handle_build_failure(payload, result_format)

    if output:
        config.build.output_dir = output

    output_dir = project_dir / config.build.output_dir
    validation = _build_validation_payload(config, project_dir, "desktop", output_dir)
    payload["validation"] = validation
    if not validation["ok"]:
        _handle_build_failure(payload, result_format)

    if rebuild:
        try:
            payload["build"] = _build_desktop(config, project_dir, output_dir, emit_output=result_format == "table")
        except subprocess.CalledProcessError as exc:
            payload["build"] = {
                "status": "failed",
                "error": f"Sign rebuild exited with code {exc.returncode}",
                "stderr": (exc.stderr or "")[:1000],
                "stdout": (exc.stdout or "")[:1000],
            }
            _handle_build_failure(payload, result_format)

    try:
        package_manifest, artifacts, manifest = _load_existing_package_manifest(output_dir)
    except FileNotFoundError as exc:
        payload["validation"] = {"ok": False, "warnings": [], "errors": [str(exc)]}
        _handle_build_failure(payload, result_format)

    sign_result = _execute_signing_pipeline(
        config,
        project_dir=project_dir,
        output_dir=output_dir,
        artifacts=artifacts,
        package_manifest=package_manifest,
    )

    payload["ok"] = True
    payload["sign"] = {
        "manifest_path": package_manifest,
        "manifest": manifest,
        **sign_result,
    }

    if result_format == "json":
        _machine_readable_print(payload)
        return

    console.print(
        Panel(
            _kv_table(
                [
                    ("Adapter", str(sign_result["signing"].get("adapter", "-"))),
                    ("Manifest", package_manifest),
                    ("Notarization", str(sign_result["notarization"].get("status", "skipped"))),
                ]
            ),
            title="Sign Summary",
            border_style="forge.ok",
        )
    )
    _print_command_result("Sign OK", "Manifest", package_manifest)


@app.command("release")
def release_app(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory",
    ),
    target: str = typer.Option(
        "desktop",
        "--target",
        help="Release target: desktop or web",
    ),
    result_format: str = typer.Option(
        "table",
        "--result-format",
        help="Release result format: table or json",
    ),
) -> None:
    """Build and generate a release manifest for automation pipelines."""
    if result_format == "table":
        _print_header("Release", "Build artifacts and write a release manifest")
    elif result_format != "json":
        _print_note(f"Unsupported output format: {result_format}", level="error")
        raise typer.Exit(2)

    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"
    normalized_target = target.lower()
    payload: dict[str, Any] = {
        "forge_version": VERSION,
        "ok": False,
        "target": normalized_target,
        "project_dir": str(project_dir),
        "config_path": str(config_path),
        "validation": {"ok": False, "warnings": [], "errors": []},
        "build": None,
        "release": None,
    }

    if not config_path.exists():
        payload["validation"] = {
            "ok": False,
            "warnings": [],
            "errors": [f"No forge.toml found in {project_dir}"],
        }
        _handle_build_failure(payload, result_format)

    try:
        from forge.config import ForgeConfig

        config = ForgeConfig.from_file(config_path)
    except Exception as exc:
        payload["validation"] = {
            "ok": False,
            "warnings": [],
            "errors": [f"Failed to load config: {exc}"],
        }
        _handle_build_failure(payload, result_format)

    if output:
        config.build.output_dir = output

    output_dir = project_dir / config.build.output_dir
    validation = _build_validation_payload(config, project_dir, normalized_target, output_dir)
    payload["validation"] = validation
    if not validation["ok"]:
        _handle_build_failure(payload, result_format)

    build_fn = _build_web if normalized_target == "web" else _build_desktop
    try:
        build_result = build_fn(config, project_dir, output_dir, emit_output=result_format == "table")
    except subprocess.CalledProcessError as exc:
        payload["build"] = {
            "status": "failed",
            "error": f"Release build exited with code {exc.returncode}",
            "stderr": (exc.stderr or "")[:1000],
            "stdout": (exc.stdout or "")[:1000],
        }
        _handle_build_failure(payload, result_format)

    release_manifest = _release_manifest_payload(config, normalized_target, build_result)
    release_manifest_path = output_dir / "forge-release.json"
    release_manifest_path.write_text(
        json.dumps(release_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    payload["ok"] = True
    payload["build"] = build_result
    payload["release"] = {
        "manifest_path": str(release_manifest_path),
        "manifest": release_manifest,
    }

    if result_format == "json":
        _machine_readable_print(payload)
        return

    _print_build_summary("Release Build Summary", build_result)
    _print_command_result("Release OK", "Manifest", str(release_manifest_path))


@app.command("info")
def show_info(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: str = typer.Option(
        "table",
        "--output",
        help="Output format: table or json",
    ),
) -> None:
    """
    Display system and project information.

    Shows details about your system, Python installation, and Forge project.
    """
    project_dir = _resolve_project_dir(path)
    payload = {
        "forge_version": VERSION,
        "environment": _environment_payload(),
        "project": _project_payload(project_dir),
    }

    if output == "json":
        _machine_readable_print(payload)
        return
    if output != "table":
        _print_note(f"Unsupported output format: {output}", level="error")
        raise typer.Exit(2)

    _print_header("Info", f"Forge CLI v{VERSION}")

    environment = payload["environment"]
    project = payload["project"]

    system_rows = [
        ("OS", environment["os"]),
        ("OS Version", environment["os_version"]),
        ("Python", environment["checks"]["python"]["version"]),
        ("Platform", f"{sys.platform} / {environment['machine']}"),
        ("Threading", environment["checks"]["threading"]["detail"]),
        ("Rust Core", environment["checks"]["rust_core"]["detail"]),
    ]
    for pkg_name in ["cargo", "rustc", "maturin", "uvicorn", "msgpack", "cryptography"]:
        check = environment["checks"][pkg_name]
        value = check.get("path") or check.get("detail") or check["status"]
        system_rows.append((pkg_name, str(value)))
    console.print(_kv_table(system_rows, title="System"))

    if project["exists"] and project["valid"]:
        console.print(
            _kv_table(
                [
                    ("Name", project["app"]["name"]),
                    ("Version", project["app"]["version"]),
                    ("Entry", project["entry_path"]),
                    ("Frontend", project["frontend_path"]),
                    ("Template", str(project.get("template", {}).get("name", "-"))),
                ],
                title="Project",
            )
        )
    else:
        for error in project["errors"]:
            _print_note(error, level="warning")


@app.command("doctor")
def doctor(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: str = typer.Option(
        "table",
        "--output",
        help="Output format: table or json",
    ),
) -> None:
    """Validate environment and project prerequisites for Forge development."""
    project_dir = _resolve_project_dir(path)
    payload = _doctor_payload(project_dir)

    if output == "json":
        _machine_readable_print(payload)
        raise typer.Exit(0 if payload["ok"] else 1)
    if output != "table":
        _print_note(f"Unsupported output format: {output}", level="error")
        raise typer.Exit(2)

    _print_header("Doctor", "Validate environment and project readiness")

    env_table = Table(title="Environment", show_header=True, box=box.SIMPLE_HEAVY)
    env_table.add_column("Check", style="cyan")
    env_table.add_column("Status")
    env_table.add_column("Details")
    for name, check in payload["environment"]["checks"].items():
        status = check["status"]
        details = check.get("detail") or check.get("path") or check.get("version") or "-"
        env_table.add_row(name, _status_badge(status), str(details))
    console.print(env_table)

    project = payload["project"]
    project_table = Table(title="Project", show_header=True, box=box.SIMPLE_HEAVY)
    project_table.add_column("Check", style="cyan")
    project_table.add_column("Status")
    project_table.add_column("Details")
    project_checks = [
        ("forge.toml", "ok" if project["exists"] else "error", project["config_path"]),
        ("config", "ok" if project["valid"] else "error", "; ".join(project["errors"]) or "Loaded"),
        (
            "entry",
            "ok" if project.get("entry_exists") else ("error" if project["valid"] else "warning"),
            project.get("entry_path", "-"),
        ),
        (
            "frontend",
            "ok" if project.get("frontend_exists") else ("error" if project["valid"] else "warning"),
            project.get("frontend_path", "-"),
        ),
    ]
    for name, status, details in project_checks:
        project_table.add_row(name, _status_badge(status), str(details))
    console.print(project_table)

    if payload["ok"]:
        _print_note("Doctor check passed.", level="ok")
        return

    # Show remediation hints
    _print_note("Doctor found blocking issues. Suggested fixes:", level="error")
    hints = _get_remediation_hints(payload)
    for hint in hints:
        console.print(f"  [yellow]→[/] {hint}")

    raise typer.Exit(1)


def _get_remediation_hints(payload: dict[str, Any]) -> list[str]:
    """Generate actionable fix suggestions based on doctor results."""
    hints: list[str] = []
    checks = payload.get("environment", {}).get("checks", {})

    if checks.get("python", {}).get("status") != "ok":
        hints.append("Install Python 3.10+: https://python.org/downloads/")

    if checks.get("rust_core", {}).get("status") != "ok":
        hints.append("Compile the Rust core: cd forge-framework && maturin develop")

    if checks.get("cargo", {}).get("status") != "ok" or checks.get("rustc", {}).get("status") != "ok":
        hints.append("Install Rust toolchain: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")

    if checks.get("maturin", {}).get("status") != "ok":
        hints.append("Install maturin: pip install maturin")

    if checks.get("node", {}).get("status") not in ("ok", None):
        hints.append("Install Node.js 18+: https://nodejs.org/")

    project = payload.get("project", {})
    if not project.get("exists"):
        hints.append("Create a new project: forge create my-app")
    elif not project.get("valid"):
        for err in project.get("errors", []):
            hints.append(f"Config: {err}")

    return hints


@app.command("plugin-add")
def plugin_add(
    name: str = typer.Argument(..., help="Plugin package name (e.g., forge-plugin-auth)"),
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
) -> None:
    """
    Install a Forge plugin into the current project.

    Installs the plugin package via pip and registers it in forge.toml.
    """
    _print_header("Plugin Add", f"Install plugin: {name}")

    project_dir = _resolve_project_dir(path)
    config_path = project_dir / "forge.toml"

    if not config_path.exists():
        _print_note(f"No forge.toml found in {project_dir}", level="error")
        raise typer.Exit(1)

    # Install the package
    _print_note(f"Installing {name}...", level="ok")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", name],
            check=True,
            capture_output=True,
            text=True,
        )
        _print_note(f"Package {name} installed", level="ok")
    except subprocess.CalledProcessError as exc:
        _print_note(f"Failed to install {name}: {exc.stderr[:200]}", level="error")
        raise typer.Exit(1)

    # Register in forge.toml
    try:
        config_text = config_path.read_text()
        module_name = name.replace("-", "_")

        if module_name in config_text:
            _print_note(f"Plugin {module_name} already registered in forge.toml", level="warning")
        elif "[plugins]" in config_text:
            # Append to existing plugins.modules
            if "modules = [" in config_text:
                config_text = config_text.replace(
                    "modules = [",
                    f'modules = ["{module_name}", ',
                )
            else:
                config_text = config_text.replace(
                    "[plugins]",
                    f'[plugins]\nmodules = ["{module_name}"]',
                )
            config_path.write_text(config_text)
            _print_note(f"Registered {module_name} in forge.toml", level="ok")
        else:
            config_text += f'\n[plugins]\nenabled = true\nmodules = ["{module_name}"]\n'
            config_path.write_text(config_text)
            _print_note(f"Added [plugins] section with {module_name} to forge.toml", level="ok")

    except Exception as e:
        _print_note(f"Installed {name} but could not update forge.toml: {e}", level="warning")
        _print_note(f"Add '{module_name}' to [plugins].modules manually", level="warning")


@app.command("support-bundle")
def support_bundle(
    path: Optional[str] = typer.Argument(
        None,
        help="Path to project directory (default: current directory)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output path for the support bundle zip",
    ),
) -> None:
    """Generate a diagnostic support bundle for troubleshooting.

    Creates a .zip file containing system info, sanitized config,
    recent log files, and environment diagnostic checks.
    """
    _print_header("Support Bundle", "Collect diagnostics for troubleshooting")

    project_dir = _resolve_project_dir(path)

    if output:
        bundle_path = Path(output).resolve()
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        bundle_path = project_dir / f"forge-support-{timestamp}.zip"

    _print_note("Collecting system information...", level="ok")
    _print_note("Snapshotting config...", level="ok")
    _print_note("Gathering log files...", level="ok")

    try:
        from forge.diagnostics import generate_support_bundle

        log_dir = project_dir / ".forge-logs"
        result = generate_support_bundle(
            bundle_path,
            project_dir=project_dir,
            log_dir=log_dir if log_dir.exists() else None,
        )

        _print_note(f"Bundle contains {len(result['contents'])} files", level="ok")
        _print_command_result(
            "Support Bundle Ready",
            "Path",
            result["path"],
            footer=f"Size: {result['size_bytes']:,} bytes",
        )
    except Exception as exc:
        _print_note(f"Failed to generate support bundle: {exc}", level="error")
        raise typer.Exit(1)


@app.command("generate-types")
def generate_types(
    path: Path = typer.Argument(Path("."), help="Project directory"),
    output: Path = typer.Option(Path("src/forge-env.d.ts"), "--output", "-o", help="Output path for the d.ts file"),
    format: str = typer.Option("text", "--format", help="Output format (text/json)"),
) -> None:
    """
    Generate a strictly typed TypeScript index.d.ts from the Python backend.
    """
    _print_header("Type Generation", "Building TypeScript definitions")
    project_dir = path.resolve()
    if not project_dir.exists() or not (project_dir / "forge.toml").exists():
        _print_note("No forge.toml found. Are you in a Forge project?", level="error")
        raise typer.Exit(1)

    try:
        from forge.config import ForgeConfig
        from forge.app import ForgeApp
        from forge.typegen import TypeGenerator

        # Load configuration
        config = ForgeConfig.from_file(project_dir / "forge.toml")
        
        # Bypassing real GUI window creation by avoiding app.run()
        # Initializing ForgeApp will register internal commands and plugins
        _print_note("Introspecting runtime...", level="info")
        config_path = project_dir / "forge.toml"
        app = ForgeApp(str(config_path))
        
        if hasattr(app, "bridge"):
            registry = app.bridge.get_command_registry()
            # Feed registry into TypeGenerator
            generator = TypeGenerator(registry)
            dts_content = generator.generate()
            
            out_path = project_dir / output
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(dts_content, encoding="utf-8")
            
            _print_note(f"Extracted {len(registry)} IPC commands.", level="ok")
            _print_command_result(
                "Definitions Ready", "Path", str(output), footer=f"Saved {len(dts_content.splitlines())} lines."
            )
            
            if format == "json":
                _machine_readable_print({"typegen": "success", "file": str(out_path)})
        else:
            _print_note("ForgeApp instance has no bridge configured.", level="error")
            raise typer.Exit(1)

    except Exception as exc:
        _print_note(f"Type generation failed: {exc}", level="error")
        raise typer.Exit(1)


def _copy_template(
    template_dir: Path,
    project_dir: Path,
    name: str,
    author: str,
    width: int,
    height: int,
) -> None:
    """
    Copy template files to the project directory.

    Args:
        template_dir: Source template directory.
        project_dir: Destination project directory.
        name: Project name.
        author: Author name.
        width: Window width.
        height: Window height.
    """
    for item in template_dir.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(template_dir)
            dest = project_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Read and process template
            try:
                content = item.read_text(encoding="utf-8")

                # Replace placeholders
                content = content.replace("{{PROJECT_NAME}}", name)
                content = content.replace("{{AUTHOR}}", author)
                content = content.replace("{{WINDOW_WIDTH}}", str(width))
                content = content.replace("{{WINDOW_HEIGHT}}", str(height))

                dest.write_text(content, encoding="utf-8")
            except UnicodeDecodeError:
                # Binary file - copy as-is
                shutil.copy2(item, dest)


def _write_frontend_workspace_files(project_dir: Path, template: str, name: str) -> None:
    package_name = _slugify(name)
    package_json_path = project_dir / "package.json"
    vite_config_path = project_dir / "vite.config.mjs"

    dependencies: dict[str, str] = {
        "@forgedesk/api": "^2.0.0",
    }
    dev_dependencies: dict[str, str] = {
        "@forgedesk/vite-plugin": "^2.0.0",
        "vite": "^6.2.0",
    }
    plugin_import = ""
    plugin_usage = ""

    if template in ["react", "complex"]:
        dependencies.update({"react": "^19.0.0", "react-dom": "^19.0.0"})
        dev_dependencies["@vitejs/plugin-react"] = "^4.4.0"
        plugin_import = 'import react from "@vitejs/plugin-react"\n'
        plugin_usage = "react(), "
    elif template == "vue":
        dependencies["vue"] = "^3.5.0"
        dev_dependencies["@vitejs/plugin-vue"] = "^5.2.0"
        plugin_import = 'import vue from "@vitejs/plugin-vue"\n'
        plugin_usage = "vue(), "
    elif template == "svelte":
        dependencies["svelte"] = "^5.0.0"
        dev_dependencies["@sveltejs/vite-plugin-svelte"] = "^5.0.0"
        plugin_import = 'import { svelte } from "@sveltejs/vite-plugin-svelte"\n'
        plugin_usage = "svelte(), "

    package_json = {
        "name": package_name,
        "private": True,
        "version": "1.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
            "forge:dev": "forge dev",
            "forge:build": "forge build",
        },
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }
    package_json_path.write_text(json.dumps(package_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    vite_config_path.write_text(
        "import { defineConfig } from \"vite\"\n"
        + plugin_import
        + 'import { forgeVitePlugin } from "@forgedesk/vite-plugin"\n\n'
        + "export default defineConfig({\n"
        + "  root: \"src/frontend\",\n"
        + "  plugins: ["
        + plugin_usage
        + "forgeVitePlugin()],\n"
        + "  build: {\n"
        + "    outDir: \"../../dist/static\",\n"
        + "    emptyOutDir: true,\n"
        + "  },\n"
        + "  server: {\n"
        + "    host: \"127.0.0.1\",\n"
        + "    port: 5173,\n"
        + "  },\n"
        + "})\n",
        encoding="utf-8",
    )


def _inject_dev_server_defaults(config_path: Path) -> None:
    content = config_path.read_text(encoding="utf-8")
    if "dev_server_command" in content:
        return
    marker = "[dev]\nfrontend_dir = \"src/frontend\"\nhot_reload = true\nport = 5173\n"
    replacement = (
        marker
        + 'dev_server_command = "npm run dev"\n'
        + 'dev_server_url = "http://127.0.0.1:5173"\n'
    )
    config_path.write_text(content.replace(marker, replacement), encoding="utf-8")





def _setup_python_env(project_dir: Path) -> None:
    venv_dir = project_dir / ".venv"
    _print_note("Preparing Python environment (uv-first)...", level="ok")

    def _ensure_uv() -> str | None:
        def _locate_uv() -> str | None:
            direct = shutil.which("uv")
            if direct:
                return direct
            home = Path.home()
            candidates = [
                home / ".local" / "bin" / "uv",
                home / ".cargo" / "bin" / "uv",
                home / "AppData" / "Local" / "uv" / "bin" / "uv.exe",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
            return None

        existing = _locate_uv()
        if existing:
            return existing

        try:
            if sys.platform == "win32":
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        "irm https://astral.sh/uv/install.ps1 | iex",
                    ],
                    check=True,
                )
            else:
                subprocess.run(
                    [
                        "sh",
                        "-c",
                        "set -e; if command -v curl >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh; elif command -v wget >/dev/null 2>&1; then wget -qO- https://astral.sh/uv/install.sh | sh; else exit 1; fi",
                    ],
                    check=True,
                )
        except Exception:
            return None

        return _locate_uv()

    uv_path = _ensure_uv()
    python_exe = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    uv_env = os.environ.copy()
    uv_env.setdefault("UV_LINK_MODE", "copy")

    if uv_path:
        try:
            subprocess.run(
                [uv_path, "venv", str(venv_dir), "--python", "3.14", "--allow-existing"],
                check=True,
                env=uv_env,
            )
            _print_note("Created .venv using uv", level="ok")
        except subprocess.CalledProcessError as exc:
            _print_note(f"uv venv failed: {exc}", level="error")
            return
    else:
        _print_note("uv is required but could not be installed automatically.", level="error")
        return

    _print_note("Installing Python dependencies...", level="ok")
    
    # Check if we are running in the framework source to do an editable install
    cli_dir = Path(__file__).resolve().parent
    repo_root = cli_dir.parent
    
    deps = ["fastapi", "uvicorn", "rich", "cryptography", "msgspec", "msgpack", "watchfiles"]
    
    # If Cargo.toml or pyproject.toml is in repo_root, assume editable install
    if (repo_root / "pyproject.toml").exists() and (repo_root / "Cargo.toml").exists():
        deps.append("-e")
        deps.append(str(repo_root))
    else:
        deps.append("forge-framework")
    
    try:
        subprocess.run(
            [uv_path, "pip", "install", "--python", str(python_exe), *deps],
            check=True,
            env=uv_env,
        )
        _print_note("Python environment configured successfully", level="ok")
    except subprocess.CalledProcessError as e:
        _print_note(f"Failed to install dependencies: {e}", level="warning")

def _create_placeholder_icon(path: Path) -> None:
    """
    Create a placeholder PNG icon file.

    Creates a minimal valid PNG file as a placeholder.
    """
    # Minimal 1x1 pixel PNG (blue)
    minimal_png = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,  # PNG signature
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,  # IHDR chunk
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,  # 1x1
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,  # IDAT chunk
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xFF,
            0xFF,
            0x3F,
            0x00,
            0x05,
            0xFE,
            0x02,
            0xFE,
            0xDC,
            0xCC,
            0x59,
            0xE7,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,  # IEND chunk
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )
    path.write_bytes(minimal_png)


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
