"""
OS Integration API.

Provides methods for native OS integration, such as taskbar progress bars,
dock bouncing, and window flashes, to command the user's attention natively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.app import ForgeApp


class OSIntegrationAPI:
    """
    Manage OS-specific shell integrations like taskbar progress or attention requests.
    """

    def __init__(self, app: ForgeApp) -> None:
        self._app = app

    def _require_capability(self) -> None:
        if not self._app.has_capability("os_integration"):
            raise PermissionError("The 'os_integration' capability is required.")

    def set_progress_bar(self, progress: float) -> None:
        """
        Set the taskbar/dock progress bar.

        Args:
            progress: A value between 0.0 and 1.0. Set to -1 to remove the progress bar.
        """
        self._require_capability()
        self._app._ipc_os_set_progress_bar(progress)

    def request_user_attention(self, is_critical: bool = False) -> None:
        """
        Request user attention (bounces macOS dock icon, flashes Windows taskbar).

        Args:
            is_critical: If True, bounces continuously until focused. 
                         If False, bounces once. (Behavior varies by OS).
        """
        self._require_capability()
        self._app._ipc_os_request_user_attention(is_critical)

    def clear_user_attention(self) -> None:
        """
        Stop requesting user attention (stops bouncing/flashing).
        """
        self._require_capability()
        self._app._ipc_os_clear_user_attention()
