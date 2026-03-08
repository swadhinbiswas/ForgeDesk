"""
Screen and Displays API.

Provides methods to query connected monitors, primary displays,
screen dimensions, and DPI scale factors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from forge.app import ForgeApp


class ScreenAPI:
    """
    Query system displays, resolutions, and work areas.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app

    def _require_capability(self) -> None:
        if not self._app.has_capability("screen"):
            raise PermissionError("The 'screen' capability is required to access display info.")

    def get_monitors(self) -> List[Dict[str, Any]]:
        """
        Get all connected monitors.
        
        Returns:
            List[Dict]: A list of monitors with properties:
                - name (str): Display name
                - position (Dict[x, y]): Top-left coordinates
                - size (Dict[width, height]): Total resolution
                - scale_factor (float): DPI scale scaling factor
                - is_primary (bool): Whether it is the primary monitor
        """
        self._require_capability()
        return self._app._ipc_screen_get_monitors()

    def get_primary_monitor(self) -> Dict[str, Any] | None:
        """
        Get the primary monitor.
        
        Returns:
            Dict: Primary monitor details or None if unable to detect.
        """
        self._require_capability()
        return self._app._ipc_screen_get_primary()

    def get_cursor_screen_point(self) -> Dict[str, int]:
        """
        Get the current absolute position of the mouse cursor.
        """
        self._require_capability()
        return self._app._ipc_screen_get_cursor()
