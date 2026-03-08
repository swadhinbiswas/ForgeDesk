"""
Forge Clipboard API (v2.0).

Provides clipboard read/write functionality for Forge applications
via IPC commands dispatched to the JavaScript frontend.

V2 changes:
    - Removed all pywebview dependencies
    - Clipboard operations use the browser's Clipboard API via IPC
    - Methods return command descriptors for the frontend to execute
"""

from __future__ import annotations

import logging
from typing import Dict

from forge.bridge import command

logger = logging.getLogger(__name__)


class ClipboardAPI:
    """

    __forge_capability__ = "clipboard"
    Clipboard API for Forge applications.

    In v2.0, clipboard operations are handled by the JavaScript frontend
    using the browser's Clipboard API (navigator.clipboard).
    """

    @command("clipboard_read")
    def read(self) -> Dict[str, str]:
        """
        Request the frontend to read from the system clipboard.

        Returns:
            Dict with action descriptor for the frontend.
        """
        return {"action": "clipboard_read"}

    @command("clipboard_write")
    def write(self, text: str) -> Dict[str, str]:
        """
        Request the frontend to write text to the system clipboard.

        Args:
            text: The text to write to the clipboard.

        Returns:
            Dict with action descriptor for the frontend.
        """
        return {"action": "clipboard_write", "text": text}

    @command("clipboard_clear")
    def clear(self) -> Dict[str, str]:
        """
        Request the frontend to clear the clipboard.

        Returns:
            Dict with action descriptor for the frontend.
        """
        return {"action": "clipboard_write", "text": ""}
