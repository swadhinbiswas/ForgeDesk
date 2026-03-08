"""Forge plugin loading and lifecycle support."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass
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

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "version": self.version,
            "source": self.source,
            "loaded": self.loaded,
            "error": self.error,
            "manifest": self.manifest or {},
        }


class PluginManager:
    """Load Forge plugins from Python modules or file paths."""

    def __init__(self, app: Any, config: Any) -> None:
        self._app = app
        self._config = config
        self._records: list[PluginRecord] = []
        self._loaded_modules: list[ModuleType] = []

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._config, "enabled", False))

    def load_all(self) -> list[dict[str, Any]]:
        self._records.clear()
        self._loaded_modules.clear()
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

        return self.list()

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
            )
        )
