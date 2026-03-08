"""
Forge Dialog API (v2.0).

Provides dialog functionality for Forge applications by dispatching
commands to the JavaScript frontend via IPC.

V2 changes:
    - Removed all pywebview dependencies
    - Dialogs are now implemented as IPC commands that the JS frontend
      handles using the browser's native APIs (File System Access API,
      <input type="file">, window.confirm, etc.)
    - All methods are synchronous stubs that register as IPC commands
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DialogAPI:
    """

    __forge_capability__ = "dialogs"
    Dialog API for Forge applications.

    In v2.0, dialog operations are handled by the JavaScript frontend
    using browser-native APIs. The Python side provides command stubs
    that can be overridden for custom behavior.
    """

    def open_file(
        self,
        title: str = "Open File",
        filters: Optional[List[Dict[str, Any]]] = None,
        multiple: bool = False,
    ) -> Dict[str, Any]:
        """
        Request the frontend to show an open file dialog.

        The actual dialog is rendered by the browser/webview.
        This command returns metadata about the operation.

        Args:
            title: Dialog window title.
            filters: File type filters.
            multiple: Allow selecting multiple files.

        Returns:
            Dict with dialog parameters for the frontend to process.
        """
        return {
            "action": "open_file",
            "title": title,
            "filters": filters or [],
            "multiple": multiple,
        }

    def open(
        self,
        title: str = "Open File",
        filters: Optional[List[Dict[str, Any]]] = None,
        multiple: bool = False,
    ) -> Dict[str, Any]:
        """Compatibility alias for opening a file dialog."""
        return self.open_file(title=title, filters=filters, multiple=multiple)

    def save_file(
        self,
        title: str = "Save File",
        default_path: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Request the frontend to show a save file dialog.

        Args:
            title: Dialog window title.
            default_path: Default file path or name.
            filters: File type filters.

        Returns:
            Dict with dialog parameters for the frontend to process.
        """
        return {
            "action": "save_file",
            "title": title,
            "default_path": default_path,
            "filters": filters or [],
        }

    def save(
        self,
        title: str = "Save File",
        default_path: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Compatibility alias for saving a file dialog."""
        return self.save_file(title=title, default_path=default_path, filters=filters)

    def message(
        self,
        title: str,
        body: str,
        level: str = "info",
    ) -> Dict[str, Any]:
        """
        Request the frontend to show a message dialog.

        Args:
            title: Dialog title.
            body: Message body text.
            level: Dialog level - 'info', 'warning', or 'error'.

        Returns:
            Dict with dialog parameters for the frontend to process.
        """
        return {
            "action": "message",
            "title": title,
            "body": body,
            "level": level,
        }

    def confirm(
        self,
        title: str,
        message: str,
        level: str = "info",
    ) -> Dict[str, Any]:
        """
        Request the frontend to show a confirmation dialog.

        Args:
            title: Dialog title.
            message: Confirmation message.
            level: Dialog level - 'info', 'warning', or 'error'.

        Returns:
            Dict with dialog parameters for the frontend to process.
        """
        return {
            "action": "confirm",
            "title": title,
            "message": message,
            "level": level,
        }

    def open_directory(
        self,
        title: str = "Select Directory",
    ) -> Dict[str, Any]:
        """
        Request the frontend to show a directory selection dialog.

        Args:
            title: Dialog window title.

        Returns:
            Dict with dialog parameters for the frontend to process.
        """
        return {
            "action": "open_directory",
            "title": title,
        }
