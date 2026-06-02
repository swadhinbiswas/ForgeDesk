"""Forge Window Positioner API.

Provides utility commands for positioning windows at common screen
locations: center, tray-anchor, corners, etc. Inspired by Tauri's
``positioner`` plugin (port of ``electron-positioner``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PositionerAPI:
    """Position windows at common screen locations."""

    __forge_capability__ = "window_state"

    def __init__(self, app: Any) -> None:
        self._app = app

    def _get_screen_size(self) -> tuple[int, int]:
        """Get the primary screen size from the Rust runtime."""
        try:
            screen_api = getattr(self._app, "screen", None)
            if screen_api:
                info = screen_api.get_current()
                if info and info.get("ok"):
                    return info.get("width", 1920), info.get("height", 1080)
        except Exception:
            pass
        # Fallback to sane defaults
        return 1920, 1080

    def _get_window_size(self) -> tuple[int, int]:
        """Get the current window size from config."""
        return self._app.config.window.width, self._app.config.window.height

    def position_center(self, label: str | None = None) -> dict[str, Any]:
        """Center the window on the primary screen.

        Args:
            label: Optional window label. Defaults to main window.

        Returns:
            ``{ok: true, x, y}`` with the new position.
        """
        screen_w, screen_h = self._get_screen_size()
        win_w, win_h = self._get_window_size()
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        return self._apply_position(label, x, y)

    def position_top_right(self, label: str | None = None, margin: int = 20) -> dict[str, Any]:
        """Position the window at the top-right corner.

        Args:
            label: Optional window label.
            margin: Margin from screen edge in pixels.

        Returns:
            ``{ok: true, x, y}``
        """
        screen_w, _ = self._get_screen_size()
        win_w, _ = self._get_window_size()
        x = screen_w - win_w - margin
        y = margin
        return self._apply_position(label, x, y)

    def position_bottom_right(self, label: str | None = None, margin: int = 20) -> dict[str, Any]:
        """Position the window at the bottom-right corner.

        Args:
            label: Optional window label.
            margin: Margin from screen edge in pixels.

        Returns:
            ``{ok: true, x, y}``
        """
        screen_w, screen_h = self._get_screen_size()
        win_w, win_h = self._get_window_size()
        x = screen_w - win_w - margin
        y = screen_h - win_h - margin
        return self._apply_position(label, x, y)

    def position_top_left(self, label: str | None = None, margin: int = 20) -> dict[str, Any]:
        """Position the window at the top-left corner.

        Args:
            label: Optional window label.
            margin: Margin from screen edge in pixels.

        Returns:
            ``{ok: true, x, y}``
        """
        return self._apply_position(label, margin, margin)

    def position_bottom_left(self, label: str | None = None, margin: int = 20) -> dict[str, Any]:
        """Position the window at the bottom-left corner.

        Args:
            label: Optional window label.
            margin: Margin from screen edge in pixels.

        Returns:
            ``{ok: true, x, y}``
        """
        _, screen_h = self._get_screen_size()
        _, win_h = self._get_window_size()
        x = margin
        y = screen_h - win_h - margin
        return self._apply_position(label, x, y)

    def position_tray_anchor(self, label: str | None = None) -> dict[str, Any]:
        """Position the window anchored to the system tray area.

        Platform behavior:
        - macOS: top-right (menu bar area)
        - Windows: bottom-right (taskbar area)
        - Linux: top-right (panel area)

        Args:
            label: Optional window label.

        Returns:
            ``{ok: true, x, y}``
        """
        import sys

        screen_w, screen_h = self._get_screen_size()
        win_w, win_h = self._get_window_size()

        if sys.platform == "win32":
            # Windows: taskbar is at the bottom
            x = screen_w - win_w - 10
            y = screen_h - win_h - 50  # Above taskbar
        else:
            # macOS/Linux: menubar/panel at the top
            x = screen_w - win_w - 10
            y = 30  # Below menubar

        return self._apply_position(label, x, y)

    def _apply_position(self, label: str | None, x: int, y: int) -> dict[str, Any]:
        """Apply a position to a window via the window manager."""
        wm = getattr(self._app, "windows", None)
        if wm is not None and label:
            try:
                wm.set_position(label=label, x=x, y=y)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return {"ok": True, "x": x, "y": y}
