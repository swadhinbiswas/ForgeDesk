"""
App Lifecycle & Single Instance API.

Provides methods to request single-instance locks and control application lifecycle.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.app import ForgeApp


class LifecycleAPI:
    """
    Control application startup locks and OS lifecycle events.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        self._guard = None

    def _require_capability(self) -> None:
        if not self._app.has_capability("lifecycle"):
            raise PermissionError("The 'lifecycle' capability is required.")

    def request_single_instance_lock(self, instance_name: str | None = None) -> bool:
        """
        Request a lock to ensure only a single instance of the application runs.
        
        If another instance is already running with the same lock name, this 
        will return False. It is usually best to call sys.exit(0) if this is False.

        Args:
            instance_name: A unique identifier for your app. Defaults to the config app name.

        Returns:
            bool: True if this is the ONLY running instance. False if another instance exists.
        """
        self._require_capability()
        
        lock_name = instance_name or self._app.config.app.name or "forge-app-locked"
        
        # We hold the guard reference closely so it isn't garbage collected.
        # Once garbage collected, the Rust memory drops and the Mutex/File lock is removed.
        from forge import forge_core
        self._guard = forge_core.SingleInstanceGuard(lock_name)
        
        return self._guard.is_single()

    def relaunch(self) -> None:
        """
        Immediately forcefully relaunch the entire application.
        """
        self._require_capability()
        import os
        import subprocess
        
        # Relaunch using the exact same arguments and executable
        subprocess.Popen([sys.executable] + sys.argv)
        self._app.window.close()
        sys.exit(0)
