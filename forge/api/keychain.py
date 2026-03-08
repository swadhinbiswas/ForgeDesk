"""
Secure Keychain Storage API.

Provides methods for securely storing credentials and tokens using the OS native keychain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from forge import forge_core

if TYPE_CHECKING:
    from forge.app import ForgeApp


class KeychainAPI:
    """
    Manage encrypted credentials via OS native keychains.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        name = self._app.config.app.name or "ForgeApp"
        # We instantiate the rust-side keychain manager
        self._manager = getattr(forge_core, "KeychainManager", None)
        if self._manager:
            try:
                self._manager = self._manager(name)
            except Exception:
                self._manager = None

    def _require_capability(self) -> None:
        if not self._app.has_capability("keychain"):
            raise PermissionError("The 'keychain' capability is required.")

    def set_password(self, key: str, password: str) -> bool:
        """
        Store a password securely.
        """
        self._require_capability()
        if self._manager:
            try:
                self._manager.set_password(key, password)
                return True
            except Exception:
                return False
        return False

    def get_password(self, key: str) -> str | None:
        """
        Retrieve a stored password.
        """
        self._require_capability()
        if self._manager:
            try:
                return self._manager.get_password(key)
            except Exception:
                return None
        return None

    def delete_password(self, key: str) -> bool:
        """
        Delete a stored password.
        """
        self._require_capability()
        if self._manager:
            try:
                self._manager.delete_password(key)
                return True
            except Exception:
                return False
        return False
