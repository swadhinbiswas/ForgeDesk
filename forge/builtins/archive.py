"""ZIP list/extract with path traversal protection (built-in extension)."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinArchiveAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def _base(self) -> Path:
        return self._app.config.get_base_dir().resolve()  # type: ignore[no-any-return]

    def _safe_path(self, path: str) -> Path | None:
        base = self._base()
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = base / p
        try:
            p = p.resolve()
            p.relative_to(base)
        except ValueError, OSError:
            return None
        return p

    def zip_list(self, zip_path: str) -> dict[str, Any]:
        """List member names in a zip under the app directory."""
        zp = self._safe_path(zip_path)
        if zp is None:
            return {"ok": False, "error": "path escapes app directory", "names": []}
        if not zp.is_file():
            return {"ok": False, "error": "not a file", "names": []}
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                names = zf.namelist()
            return {"ok": True, "names": names}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "names": []}

    def zip_extract_safe(self, zip_path: str, dest_dir: str) -> dict[str, Any]:
        """Extract all members, skipping any that would escape ``dest_dir``."""
        zp = self._safe_path(zip_path)
        dest = self._safe_path(dest_dir)
        if zp is None or dest is None:
            return {"ok": False, "error": "path escapes app directory", "extracted": 0}
        if not zp.is_file():
            return {"ok": False, "error": "zip not found", "extracted": 0}
        dest.mkdir(parents=True, exist_ok=True)
        extracted = 0
        dest_root = dest.resolve()
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                for name in zf.namelist():
                    try:
                        out = (dest / name).resolve()
                        out.relative_to(dest_root)
                    except ValueError:
                        logger.warning("zip slip blocked: %s", name)
                        continue
                    if name.endswith("/"):
                        out.mkdir(parents=True, exist_ok=True)
                    else:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, out.open("wb") as dst:
                            dst.write(src.read())
                        extracted += 1
            return {"ok": True, "extracted": extracted}
        except Exception as exc:
            logger.exception("zip_extract_safe")
            return {"ok": False, "error": str(exc), "extracted": extracted}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinArchiveAPI(app))
