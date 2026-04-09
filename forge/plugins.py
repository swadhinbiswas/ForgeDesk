"""Forge plugin loading, lifecycle, and capability enforcement.

Plugin Manifest Contract:
    Plugins declare their identity and requirements via a module-level
    ``__forge_plugin__`` dict or ``manifest`` dict:

    __forge_plugin__ = {
        "name": "my-plugin",
        "version": "1.0.0",
        "capabilities": ["fs", "clipboard"],     # required capabilities
        "forge_version": ">=0.1.0",              # minimum framework version
        "depends": ["other-plugin"],              # plugin dependencies
    }

    def register(app):
        # Called during plugin loading
        ...

    def on_ready(app):     # optional lifecycle hook
        ...

    def on_shutdown(app):  # optional lifecycle hook
        ...
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PluginRecord:
    """Serializable state for a loaded or failed plugin."""

    name: str
    module: str
    version: str | None = None
    source: str | None = None
    loaded: bool = False
    error: str | None = None
    manifest: dict[str, Any] | None = None
    capabilities: list[str] = field(default_factory=list)
    has_on_ready: bool = False
    has_on_shutdown: bool = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "version": self.version,
            "source": self.source,
            "loaded": self.loaded,
            "error": self.error,
            "manifest": self.manifest or {},
            "capabilities": self.capabilities,
            "has_on_ready": self.has_on_ready,
            "has_on_shutdown": self.has_on_shutdown,
        }


def _version_key(version: str) -> tuple[int, ...]:
    """Parse a semver string into a comparable tuple."""
    parts = [int(p) for p in re.findall(r"\d+", version)]
    return tuple(parts or [0])


def _check_version_constraint(constraint: str, current: str) -> bool:
    """Check if current version satisfies a simple constraint like '>=0.1.0'."""
    constraint = constraint.strip()
    if constraint.startswith(">="):
        return _version_key(current) >= _version_key(constraint[2:])
    if constraint.startswith(">"):
        return _version_key(current) > _version_key(constraint[1:])
    if constraint.startswith("<="):
        return _version_key(current) <= _version_key(constraint[2:])
    if constraint.startswith("<"):
        return _version_key(current) < _version_key(constraint[1:])
    if constraint.startswith("==") or constraint.startswith("="):
        clean = constraint.lstrip("=")
        return _version_key(current) == _version_key(clean)
    # Bare version treated as exact match
    return _version_key(current) >= _version_key(constraint)


class PluginManager:
    """Load, validate, and manage Forge plugins with capability enforcement."""

    # Current framework version for compatibility checks
    FRAMEWORK_VERSION = "0.1.0"

    def __init__(self, app: Any, config: Any) -> None:
        self._app = app
        self._config = config
        self._records: list[PluginRecord] = []
        self._loaded_modules: list[ModuleType] = []
        self._ready_called: bool = False
        self._shutdown_called: bool = False

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._config, "enabled", False))

    def load_all(self) -> list[dict[str, Any]]:
        self._records.clear()
        self._loaded_modules.clear()
        self._ready_called = False
        self._shutdown_called = False
        if not self.enabled:
            return []

        seen: set[str] = set()
        for module_name in getattr(self._config, "modules", []) or []:
            normalized = str(module_name).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                self._load_module_name(normalized)

        for raw_path in getattr(self._config, "paths", []) or []:
            candidate = Path(raw_path)
            if not candidate.is_absolute() and self._app.config.config_path is not None:
                candidate = self._app.config.get_base_dir() / candidate
            if candidate.is_dir():
                for plugin_file in sorted(candidate.glob("*.py")):
                    module_key = str(plugin_file.resolve())
                    if module_key not in seen:
                        seen.add(module_key)
                        self._load_file(plugin_file)
            elif candidate.is_file():
                module_key = str(candidate.resolve())
                if module_key not in seen:
                    seen.add(module_key)
                    self._load_file(candidate)
            else:
                self._records.append(
                    PluginRecord(
                        name=candidate.stem or str(candidate),
                        module=str(candidate),
                        source=str(candidate),
                        loaded=False,
                        error="plugin path not found",
                    )
                )

        # Validate dependencies after all plugins are loaded
        self._validate_dependencies()

        return self.list()

    def on_ready(self) -> None:
        """Call on_ready(app) lifecycle hook on all loaded plugins."""
        if self._ready_called:
            return
        self._ready_called = True
        for module in self._loaded_modules:
            hook = getattr(module, "on_ready", None)
            if callable(hook):
                try:
                    hook(self._app)
                except Exception as exc:
                    logger.error(
                        "Plugin on_ready hook failed for %s: %s",
                        getattr(module, "__name__", "unknown"),
                        exc,
                    )

    def on_shutdown(self) -> None:
        """Call on_shutdown(app) lifecycle hook on all loaded plugins."""
        if self._shutdown_called:
            return
        self._shutdown_called = True
        for module in reversed(self._loaded_modules):
            hook = getattr(module, "on_shutdown", None)
            if callable(hook):
                try:
                    hook(self._app)
                except Exception as exc:
                    logger.error(
                        "Plugin on_shutdown hook failed for %s: %s",
                        getattr(module, "__name__", "unknown"),
                        exc,
                    )

    def list(self) -> list[dict[str, Any]]:
        return [record.snapshot() for record in self._records]

    def summary(self) -> dict[str, Any]:
        loaded = sum(1 for record in self._records if record.loaded)
        failed = sum(1 for record in self._records if not record.loaded)
        return {
            "enabled": self.enabled,
            "loaded": loaded,
            "failed": failed,
            "plugins": self.list(),
        }

    def get_plugin(self, name: str) -> dict[str, Any] | None:
        """Look up a plugin by name."""
        for record in self._records:
            if record.name == name and record.loaded:
                return record.snapshot()
        return None

    def _load_module_name(self, module_name: str) -> None:
        try:
            module = importlib.import_module(module_name)
            self._register_module(module, source=module_name)
        except Exception as exc:
            logger.error("failed to load Forge plugin module %s: %s", module_name, exc)
            self._records.append(
                PluginRecord(
                    name=module_name.rsplit(".", 1)[-1],
                    module=module_name,
                    source=module_name,
                    loaded=False,
                    error=str(exc),
                )
            )

    def _load_file(self, path: Path) -> None:
        resolved = path.resolve()
        module_name = f"forge_plugin_{resolved.stem}_{abs(hash(str(resolved)))}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, resolved)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Unable to create import spec for {resolved}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            self._register_module(module, source=str(resolved))
        except Exception as exc:
            logger.error("failed to load Forge plugin file %s: %s", resolved, exc)
            self._records.append(
                PluginRecord(
                    name=resolved.stem,
                    module=module_name,
                    source=str(resolved),
                    loaded=False,
                    error=str(exc),
                )
            )

    def _register_module(self, module: ModuleType, *, source: str) -> None:
        manifest = getattr(module, "manifest", None) or getattr(module, "__forge_plugin__", None) or {}
        if not isinstance(manifest, dict):
            manifest = {"name": getattr(module, "__name__", source)}

        plugin_name = str(manifest.get("name") or module.__name__.rsplit(".", 1)[-1])
        version = manifest.get("version")

        # ── Capability enforcement ──
        required_capabilities = manifest.get("capabilities", [])
        if isinstance(required_capabilities, (list, tuple)):
            for cap in required_capabilities:
                if not self._app.has_capability(str(cap)):
                    raise PermissionError(
                        f"Plugin {plugin_name!r} requires capability {cap!r} "
                        f"which is not granted in the app configuration."
                    )

        # ── Version compatibility check ──
        forge_version_constraint = manifest.get("forge_version")
        if forge_version_constraint:
            if not _check_version_constraint(str(forge_version_constraint), self.FRAMEWORK_VERSION):
                raise RuntimeError(
                    f"Plugin {plugin_name!r} requires forge {forge_version_constraint} "
                    f"but current version is {self.FRAMEWORK_VERSION}"
                )

        # ── Check for namespace collision ──
        existing = self.get_plugin(plugin_name)
        if existing:
            raise RuntimeError(
                f"Plugin name collision: {plugin_name!r} is already loaded from {existing['source']}"
            )

        # ── Register function ──
        register = getattr(module, "register", None) or getattr(module, "setup", None)
        if not callable(register):
            raise RuntimeError(f"Plugin {plugin_name!r} must define register(app) or setup(app)")

        register(self._app)
        self._loaded_modules.append(module)
        self._records.append(
            PluginRecord(
                name=plugin_name,
                module=module.__name__,
                version=str(version) if version is not None else None,
                source=source,
                loaded=True,
                manifest={k: v for k, v in manifest.items() if isinstance(k, str)},
                capabilities=list(required_capabilities) if isinstance(required_capabilities, (list, tuple)) else [],
                has_on_ready=callable(getattr(module, "on_ready", None)),
                has_on_shutdown=callable(getattr(module, "on_shutdown", None)),
            )
        )

    def _validate_dependencies(self) -> None:
        """Warn about missing plugin dependencies after all plugins are loaded."""
        loaded_names = {r.name for r in self._records if r.loaded}
        for record in self._records:
            if not record.loaded or not record.manifest:
                continue
            depends = record.manifest.get("depends", [])
            if not isinstance(depends, (list, tuple)):
                continue
            for dep in depends:
                if str(dep) not in loaded_names:
                    logger.warning(
                        "Plugin %s declares dependency on %s, which is not loaded",
                        record.name,
                        dep,
                    )
                    record.error = f"missing dependency: {dep}"
