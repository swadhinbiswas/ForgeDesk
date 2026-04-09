"""Forge diagnostics and support bundle generation.

Generates a .zip support bundle containing:
- system_info.json — OS, Python version, Rust core status
- config_snapshot.json — sanitized forge.toml (no secrets)
- recent_logs/ — last 3 log files
- environment.json — full environment check payload
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _system_info() -> dict[str, Any]:
    """Collect system information for diagnostics."""
    forge_core_ok = True
    forge_core_detail = "Available"
    try:
        from forge import forge_core  # noqa: F401
    except ImportError:
        forge_core_ok = False
        forge_core_detail = "Not compiled"

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "forge_core": {
            "available": forge_core_ok,
            "detail": forge_core_detail,
        },
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }


def _sanitize_config(config_data: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive values from config before including in bundle."""
    sanitized = json.loads(json.dumps(config_data))  # deep copy

    # Redact known sensitive fields
    sensitive_paths = [
        ("signing", "identity"),
        ("signing", "sign_command"),
        ("signing", "verify_command"),
        ("signing", "notarize_command"),
        ("updater", "public_key"),
        ("updater", "endpoint"),
        ("database", "url"),
        ("database", "password"),
    ]

    for path in sensitive_paths:
        obj = sanitized
        for key in path[:-1]:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                obj = None
                break
        if isinstance(obj, dict) and path[-1] in obj and obj[path[-1]]:
            obj[path[-1]] = "***REDACTED***"

    return sanitized


def _load_config_snapshot(project_dir: Path) -> dict[str, Any]:
    """Load and sanitize the project config for bundle inclusion."""
    config_path = project_dir / "forge.toml"
    if not config_path.exists():
        return {"error": "No forge.toml found", "path": str(config_path)}

    try:
        import tomllib
        with config_path.open("rb") as f:
            raw = tomllib.load(f)
        return _sanitize_config(raw)
    except Exception as exc:
        return {"error": f"Failed to parse config: {exc}", "path": str(config_path)}


def generate_support_bundle(
    output_path: Path | str,
    *,
    project_dir: Path | str | None = None,
    log_dir: Path | str | None = None,
    logger: Any = None,
    extra_files: list[Path] | None = None,
) -> dict[str, Any]:
    """Generate a diagnostic support bundle as a .zip file.

    Args:
        output_path: Path for the output .zip file.
        project_dir: Project directory to snapshot config from.
        log_dir: Directory containing log files.
        logger: Optional ForgeLogger instance to pull recent files from.
        extra_files: Additional files to include in the bundle.

    Returns:
        Dict with bundle metadata (path, contents, size).
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    contents: list[str] = []

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. System info
        sys_info = _system_info()
        zf.writestr("system_info.json", json.dumps(sys_info, indent=2, sort_keys=True))
        contents.append("system_info.json")

        # 2. Config snapshot
        if project_dir is not None:
            config = _load_config_snapshot(Path(project_dir))
            zf.writestr("config_snapshot.json", json.dumps(config, indent=2, sort_keys=True))
            contents.append("config_snapshot.json")

        # 3. Environment checks (if CLI is available)
        try:
            from forge_cli.main import _environment_payload
            env = _environment_payload()
            zf.writestr("environment.json", json.dumps(env, indent=2, sort_keys=True))
            contents.append("environment.json")
        except ImportError:
            pass

        # 4. Recent logs
        log_files: list[Path] = []
        if logger is not None and hasattr(logger, "recent_files"):
            log_files = logger.recent_files(3)
        elif log_dir is not None:
            log_path = Path(log_dir)
            if log_path.exists():
                log_files = sorted(
                    log_path.glob("forge-*.log*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:3]

        for log_file in log_files:
            if log_file.exists() and log_file.is_file():
                arcname = f"recent_logs/{log_file.name}"
                zf.write(log_file, arcname)
                contents.append(arcname)

        # 5. Extra files
        for extra in extra_files or []:
            if extra.exists() and extra.is_file():
                arcname = f"extra/{extra.name}"
                zf.write(extra, arcname)
                contents.append(arcname)

    return {
        "path": str(output),
        "size_bytes": output.stat().st_size,
        "contents": contents,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
