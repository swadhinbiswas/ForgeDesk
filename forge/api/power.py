"""
Power Monitor API.

Provides methods for checking battery status and power-saving modes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from forge.app import ForgeApp


class PowerAPI:
    """
    Manage power states, monitor battery, and suspend/resume events.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app

    def _require_capability(self) -> None:
        if not self._app.has_capability("power"):
            raise PermissionError("The 'power' capability is required.")

    def get_battery_info(self) -> Dict[str, Any]:
        """
        Get the current battery information (charge percentage, state, energy).
        """
        self._require_capability()
        return self._app._ipc_power_get_battery_info()

    def on_suspend(self, callback) -> None:
        """
        Register a callback to run when the desktop is suspended.
        """
        self._require_capability()
        self._app.events.on("power:suspended", callback)

    def on_resume(self, callback) -> None:
        """
        Register a callback to run when the desktop is resumed.
        """
        self._require_capability()
        self._app.events.on("power:resumed", callback)
