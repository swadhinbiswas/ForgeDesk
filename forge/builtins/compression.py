"""zlib / gzip compression helpers for IPC-friendly base64 payloads (built-in extension)."""

from __future__ import annotations

import base64
import gzip
import zlib
from typing import Any, Literal

_CAP = "forge_extensions"
Method = Literal["gzip", "zlib"]


class BuiltinCompressionAPI:
    __forge_capability__ = _CAP

    def compress_text(
        self,
        text: str,
        method: Method = "gzip",
        level: int = 6,
    ) -> dict[str, Any]:
        """Compress UTF-8 text; returns base64 and original byte length."""
        raw = text.encode("utf-8")
        try:
            if method == "gzip":
                out = gzip.compress(raw, compresslevel=max(1, min(level, 9)))
            else:
                out = zlib.compress(raw, level=max(-1, min(level, 9)))
            return {
                "ok": True,
                "method": method,
                "b64": base64.b64encode(out).decode("ascii"),
                "original_bytes": len(raw),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def decompress_text(self, b64: str, method: Method = "gzip") -> dict[str, Any]:
        """Decompress to UTF-8 string."""
        try:
            data = base64.b64decode(b64.encode("ascii"))
            if method == "gzip":
                raw = gzip.decompress(data)
            else:
                raw = zlib.decompress(data)
            return {"ok": True, "text": raw.decode("utf-8")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinCompressionAPI())
