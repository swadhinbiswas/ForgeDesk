"""
Autostart API.

Provides methods to register the application to run automatically
when the user logs into their operating system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from forge import forge_core

if TYPE_CHECKING:
    from forge.app import ForgeApp


class AutostartAPI:
    """
    Manage OS-specific login autostart registration.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        # Default name derived from app config
        name = self._app.config.app.name or "ForgeApp"
        # We instantiate the rust-side auto-launch manager
        self._manager = getattr(forge_core, "AutoLaunchManager", None)
        if self._manager:
            try:
                self._manager = self._manager(name)
            except Exception:
                self._manager = None

    def _require_capability(self) -> None:
        if not self._app.has_capability("autostart"):
            raise PermissionError("The 'autostart' capability is required.")

    def enable(self) -> bool:
        """
        Enable autostart at login.
        """
        self._require_capability()
        if self._manager:
            try:
                return self._manager.enable()
            except Exception:
                return False
        return False

    def disable(self) -> bool:
        """
        Disable autostart at login.
        """
        self._require_capability()
        if self._manager:
            try:
                return self._manager.disable()
            except Exception:
                return False
        return False

    def is_enabled(self) -> bool:
        """
        Check if autostart at login is currently enabled.
        """
        self._require_capability()
        if self._manager:
            try:
                return self._manager.is_enabled()
            except Exception:
                return False
        return False
