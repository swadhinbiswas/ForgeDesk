"""Desktop automation hooks for mouse and keyboard control (PyAutoGUI bindings)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_automation"


class BuiltinAutomationAPI:
    """Plugin to run native UI automation commands from the frontend."""

    __forge_capability__ = _CAP

    def _get_pyautogui(self) -> Any:
        try:
            import pyautogui  # type: ignore[import-untyped]

            # Ensure pyautogui fails safe rather than locking the machine indefinitely
            pyautogui.FAILSAFE = True
            return pyautogui
        except ImportError as e:
            raise RuntimeError("pip install pyautogui to use the automation capability") from e

    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> dict[str, Any]:
        """Move the mouse cursor to absolute coordinates."""
        try:
            pag = self._get_pyautogui()
            pag.moveTo(x, y, duration=duration)
            return {"ok": True}
        except Exception as exc:
            logger.exception("automation.mouse_move")
            return {"ok": False, "error": str(exc)}

    def mouse_click(
        self, button: str = "left", clicks: int = 1, interval: float = 0.0
    ) -> dict[str, Any]:
        """Click the mouse at the current position."""
        try:
            pag = self._get_pyautogui()
            pag.click(button=button, clicks=clicks, interval=interval)
            return {"ok": True}
        except Exception as exc:
            logger.exception("automation.mouse_click")
            return {"ok": False, "error": str(exc)}

    def keyboard_type(self, text: str, interval: float = 0.0) -> dict[str, Any]:
        """Simulate typing a string of keyboard characters."""
        try:
            pag = self._get_pyautogui()
            pag.write(text, interval=interval)
            return {"ok": True}
        except Exception as exc:
            logger.exception("automation.keyboard_type")
            return {"ok": False, "error": str(exc)}

    def keyboard_press(self, keys: list[str]) -> dict[str, Any]:
        """Press a sequence or combination of keys (e.g., ['ctrl', 'c'])."""
        try:
            pag = self._get_pyautogui()
            if len(keys) == 1:
                pag.press(keys[0])
            else:
                pag.hotkey(*keys)
            return {"ok": True}
        except Exception as exc:
            logger.exception("automation.keyboard_press")
            return {"ok": False, "error": str(exc)}

    def screen_size(self) -> dict[str, Any]:
        """Get the resolution of the primary monitor."""
        try:
            pag = self._get_pyautogui()
            width, height = pag.size()
            return {"ok": True, "width": width, "height": height}
        except Exception as exc:
            logger.exception("automation.screen_size")
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinAutomationAPI())
