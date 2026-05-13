"""Path, glob, and disk usage helpers confined to the app tree (built-in extension)."""

from __future__ import annotations

import fnmatch
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinFsToolsAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def _base(self) -> Path:
        return self._app.config.get_base_dir().resolve()  # type: ignore[no-any-return]

    def _safe_child(self, path: str) -> Path | None:
        base = self._base()
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = base / p
        try:
            p = p.resolve()
        except OSError:
            return None
        try:
            p.relative_to(base)
        except ValueError:
            return None
        return p

    def resolve_under_app(self, path: str) -> dict[str, Any]:
        """Return absolute path if it stays under the app project root."""
        p = self._safe_child(path)
        if p is None:
            return {"ok": False, "error": "path escapes app directory"}
        return {"ok": True, "path": str(p)}

    def glob(self, pattern: str) -> dict[str, Any]:
        """Glob under the app base directory (e.g. ``**/*.json``)."""
        base = self._base()
        try:
            matches: list[str] = []
            for item in base.glob(pattern):
                try:
                    item.resolve().relative_to(base)
                except ValueError:
                    continue
                matches.append(str(item))
            matches.sort()
            return {"ok": True, "paths": matches}
        except Exception as exc:
            logger.exception("glob")
            return {"ok": False, "error": str(exc), "paths": []}

    def fnmatch_names(self, names: list[str], pattern: str) -> dict[str, Any]:
        """Filter filename strings with :func:`fnmatch.fnmatch` (no disk IO)."""
        return {"matched": [n for n in names if fnmatch.fnmatch(n, pattern)]}

    def disk_usage(self, path: str = ".") -> dict[str, Any]:
        """Free/total space for a path under the app directory."""
        p = self._safe_child(path)
        if p is None:
            return {"ok": False, "error": "path escapes app directory"}
        try:
            u = shutil.disk_usage(str(p))
            return {
                "ok": True,
                "total": u.total,
                "used": u.used,
                "free": u.free,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinFsToolsAPI(app))
