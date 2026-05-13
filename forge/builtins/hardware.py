"""Hardware discovery (serial via pyserial; Bluetooth stub)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinHardwareAPI:
    __forge_capability__ = _CAP

    def serial_ports(self) -> list[dict[str, Any]]:
        """List serial ports (same data as :class:`forge.api.serial.SerialAPI` when enabled)."""
        try:
            import serial.tools.list_ports  # type: ignore[import-untyped]
        except ImportError:
            return []
        ports = serial.tools.list_ports.comports()
        return [
            {
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "manufacturer": getattr(p, "manufacturer", None),
            }
            for p in ports
        ]

    def bluetooth_status(self) -> dict[str, Any]:
        """Cross-platform Bluetooth stack is not exposed in Forge core yet."""
        return {
            "available": False,
            "note": "Use OS-specific tools or a dedicated native extension; serial/USB devices use permissions.serial.",  # noqa: E501
        }


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinHardwareAPI())
