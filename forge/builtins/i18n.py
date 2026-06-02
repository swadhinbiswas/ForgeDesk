"""JSON locale bundles merged by language tag (built-in extension)."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


def _flatten(prefix: str, obj: Any, out: dict[str, str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            _flatten(key, v, out)
    elif prefix:
        out[prefix] = str(obj)


class BuiltinI18nAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app
        self._bundles: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def _under_base(self, path: str) -> Path | None:
        base = self._app.config.get_base_dir().resolve()
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = base / p
        try:
            p = p.resolve()
            p.relative_to(base)
        except ValueError:
            return None
        except OSError:
            return None
        return p

    def load_json(self, locale: str, path: str) -> dict[str, Any]:
        """Load a nested JSON file and flatten keys like ``a.b.c``."""
        p = self._under_base(path)
        if p is None:
            return {"ok": False, "error": "path must be under app directory"}
        if not p.is_file():
            return {"ok": False, "error": f"not found: {p}"}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            flat: dict[str, str] = {}
            _flatten("", data, flat)
            with self._lock:
                self._bundles[locale] = {**self._bundles.get(locale, {}), **flat}
            return {"ok": True, "locale": locale, "keys": len(flat)}
        except Exception as exc:
            logger.exception("load_json")
            return {"ok": False, "error": str(exc)}

    def translate(self, locale: str, key: str, default: str | None = None) -> dict[str, Any]:
        """Translate a flattened key for ``locale``."""
        with self._lock:
            bundle = self._bundles.get(locale, {})
            val = bundle.get(key)
        if val is None:
            return {"ok": True, "text": default if default is not None else key, "missing": True}
        return {"ok": True, "text": val, "missing": False}

    def list_locales(self) -> dict[str, Any]:
        """Return loaded locale tags."""
        with self._lock:
            return {"locales": sorted(self._bundles.keys())}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinI18nAPI(app))
