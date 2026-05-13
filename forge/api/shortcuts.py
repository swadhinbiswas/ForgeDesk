"""
Global Shortcuts API.

Provides methods to register and unregister system-wide keyboard shortcuts
that trigger even when the application is out of focus or running in the background.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.app import ForgeApp


class ShortcutsAPI:
    """
    Manage system-wide global hotkeys.
    """

    __forge_capability__ = "global_shortcut"

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        self._callbacks: dict[str, Callable[[], None]] = {}

        # Listen for shortcut triggers emitted by the Rust event loop
        self._app.events.on("global_shortcut", self._on_shortcut_triggered)

    def _require_capability(self) -> None:
        if not self._app.has_capability("global_shortcut"):
            raise PermissionError("The 'global_shortcut' capability is required for hotkeys.")

    def register(self, accelerator: str, callback: Callable[[], None]) -> bool:
        """
        Register a global shortcut.

        Args:
            accelerator: The key combination (e.g., "CmdOrCtrl+Shift+X").
            callback: The function to execute when the shortcut is triggered.

        Returns:
            bool: True if registration was successful, False otherwise.
        """
        self._require_capability()
        success = self._app._ipc_shortcuts_register(accelerator)
        if success:
            self._callbacks[accelerator] = callback
        return success

    def _js_register(self, accelerator: str) -> bool:
        """Register a shortcut natively for the JS frontend."""

        def proxy_callback() -> None:
            self._app.events.emit("shortcut:triggered", {"accelerator": accelerator})

        return self.register(accelerator, proxy_callback)

    def unregister(self, accelerator: str) -> bool:
        """
        Unregister a previously registered global shortcut.

        Args:
            accelerator: The key combination to unregister.

        Returns:
            bool: True if successful, False otherwise.
        """
        self._require_capability()
        success = self._app._ipc_shortcuts_unregister(accelerator)
        if success and accelerator in self._callbacks:
            del self._callbacks[accelerator]
        return success

    def unregister_all(self) -> bool:
        """
        Unregister all currently registered global shortcuts.

        Returns:
            bool: True if successful.
        """
        self._require_capability()
        success = self._app._ipc_shortcuts_unregister_all()
        if success:
            self._callbacks.clear()
        return success

    def _on_shortcut_triggered(self, data: dict[str, str]) -> None:
        """Internal handler for shortcut events sent from Rust."""
        accelerator = data.get("accelerator")
        if accelerator and accelerator in self._callbacks:
            try:
                self._callbacks[accelerator]()
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(
                    f"Error in shortcut callback for {accelerator}: {e}"
                )
