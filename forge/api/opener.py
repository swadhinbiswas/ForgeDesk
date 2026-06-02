"""Forge Opener API — open files/URLs and reveal in file manager.

Provides ``open_path`` (open with default app) and ``reveal_in_folder``
(show in Finder/Explorer/Nautilus), matching Tauri's ``opener`` plugin.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_CAP = "os_integration"

# Only these URL schemes may be passed to the default browser.
_ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto", "tel", "sms"})


def _safe_open_path_arg(path: str) -> str:
    """Prevent option-injection for command-line file openers.

    Some openers (xdg-open, open) treat a leading ``-`` as a flag rather than
    a file path. We defuse this by prefixing such paths with ``./``.
    """
    if path.startswith("-"):
        return os.path.join(".", path)
    return path


class OpenerAPI:
    """Open files/URLs with default apps and reveal in file manager."""

    __forge_capability__ = _CAP

    def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the default browser.

        Only http/https/mailto/tel/sms schemes are allowed. file://, javascript:,
        data:, chrome:, etc. are rejected to prevent local-file disclosure and
        cross-protocol attacks from the frontend.

        Args:
            url: The URL to open.

        Returns:
            ``{ok: true}`` on success.
        """
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            return {"ok": False, "error": f"invalid URL: {exc}"}
        scheme = (parsed.scheme or "").lower()
        if scheme not in _ALLOWED_URL_SCHEMES:
            return {
                "ok": False,
                "error": f"refusing to open URL with scheme {scheme!r}",
            }
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_path(self, path: str) -> dict[str, Any]:
        """Open a file or directory with the system default application.

        Args:
            path: The file/directory path to open.

        Returns:
            ``{ok: true}`` on success.
        """
        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                return {"ok": False, "error": f"Path not found: {path}"}

            safe_path = _safe_open_path_arg(abs_path)

            if sys.platform == "darwin":
                subprocess.Popen(["open", "--", safe_path])
            elif sys.platform == "win32":
                os.startfile(abs_path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", safe_path])

            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def reveal_in_folder(self, path: str) -> dict[str, Any]:
        """Reveal a file in the system file manager (Finder/Explorer/Nautilus).

        - **macOS**: ``open -R <path>`` (reveals in Finder, file selected)
        - **Windows**: ``explorer /select,<path>`` (reveals in Explorer, file selected)
        - **Linux**: Uses D-Bus ``org.freedesktop.FileManager1`` or ``xdg-open`` on the parent

        Args:
            path: The file path to reveal.

        Returns:
            ``{ok: true}`` on success.
        """
        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                return {"ok": False, "error": f"Path not found: {path}"}

            safe_path = _safe_open_path_arg(abs_path)

            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", "--", safe_path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", abs_path])
            else:
                # Linux: try D-Bus FileManager1, fall back to xdg-open on parent
                try:
                    subprocess.Popen(
                        [
                            "dbus-send",
                            "--session",
                            "--dest=org.freedesktop.FileManager1",
                            "--type=method_call",
                            "/org/freedesktop/FileManager1",
                            "org.freedesktop.FileManager1.ShowItems",
                            f"array:string:file://{abs_path}",
                            "string:",
                        ]
                    )
                except Exception:
                    # D-Bus not available; open the parent directory
                    parent = os.path.dirname(abs_path)
                    subprocess.Popen(["xdg-open", _safe_open_path_arg(parent)])

            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
