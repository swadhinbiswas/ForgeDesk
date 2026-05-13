"""Process-local TTL cache for small JSON-serializable values (built-in extension)."""

from __future__ import annotations

import threading
import time
from typing import Any

_CAP = "forge_extensions"


class BuiltinMemoryCacheAPI:
    __forge_capability__ = _CAP

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[Any, float | None]] = {}

    def cache_set(self, key: str, value: Any, ttl_seconds: float | None = None) -> bool:
        """Store ``value`` under ``key``. Optional TTL in seconds."""
        exp: float | None = None
        if ttl_seconds is not None and ttl_seconds > 0:
            exp = time.monotonic() + float(ttl_seconds)
        with self._lock:
            self._data[key] = (value, exp)
        return True

    def cache_get(self, key: str) -> dict[str, Any]:
        """Get value or ``null`` if missing/expired."""
        with self._lock:
            item = self._data.get(key)
        if item is None:
            return {"hit": False, "value": None}
        val, exp = item
        if exp is not None and time.monotonic() > exp:
            with self._lock:
                self._data.pop(key, None)
            return {"hit": False, "value": None}
        return {"hit": True, "value": val}

    def cache_delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear_prefix(self, prefix: str) -> int:
        """Remove keys starting with ``prefix``; returns count removed."""
        removed = 0
        with self._lock:
            keys = [k for k in self._data if k.startswith(prefix)]
            for k in keys:
                del self._data[k]
                removed += 1
        return removed


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinMemoryCacheAPI())
