"""MessagePack and JSON helpers (built-in extension)."""

from __future__ import annotations

import base64
import json
from typing import Any

import msgpack  # type: ignore[import-untyped]

_CAP = "forge_extensions"


class BuiltinSerializationAPI:
    __forge_capability__ = _CAP

    def msgpack_packb(self, obj: Any) -> dict[str, Any]:
        """Serialize a JSON-compatible object to URL-safe base64 MessagePack bytes."""
        try:
            raw = msgpack.packb(obj, use_bin_type=True)
            return {"ok": True, "b64": base64.b64encode(raw).decode("ascii")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def msgpack_unpackb(self, b64: str) -> dict[str, Any]:
        """Decode base64 MessagePack to Python values."""
        try:
            raw = base64.b64decode(b64.encode("ascii"))
            return {"ok": True, "value": msgpack.unpackb(raw, raw=False)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def json_dumps(self, obj: Any) -> str:
        """Compact JSON string."""
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

    def json_loads(self, text: str) -> Any:
        """Parse JSON string."""
        return json.loads(text)


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinSerializationAPI())
