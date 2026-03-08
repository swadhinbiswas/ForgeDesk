"""
Forge System API (v2.0).

Provides system information and application control for Forge applications.

V2 changes:
    - Removed all pywebview dependencies
    - No longer takes a webview.Window parameter
    - Uses pure Python stdlib for system operations
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import webbrowser
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SystemAPI:
    """
    System API for Forge applications.

    Provides methods for getting system information and
    controlling the application lifecycle. No external dependencies.
    """

    def __init__(
        self,
        app_name: str = "Forge App",
        app_version: str = "1.0.0",
    ) -> None:
        """
        Initialize the System API.

        Args:
            app_name: The application name.
            app_version: The application version.
        """
        self._app_name = app_name
        self._app_version = app_version

    def get_version(self) -> str:
        """
        Get the application version.

        Returns:
            The version string from forge.toml.
        """
        return self._app_version

    def version(self) -> str:
        """Compatibility alias for getting the application version."""
        return self.get_version()

    def get_platform(self) -> str:
        """
        Get the current platform name.

        Returns:
            Platform identifier: 'windows', 'macos', or 'linux'.
        """
        system = platform.system().lower()

        if system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        else:
            return system

    def platform(self) -> str:
        """Compatibility alias for getting the current platform name."""
        return self.get_platform()

    def get_info(self) -> Dict[str, Any]:
        """
        Get detailed system information.

        Returns:
            Dictionary containing system information.
        """
        return {
            "app_name": self._app_name,
            "app_version": self._app_version,
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": self.get_platform(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "node": platform.node(),
            "free_threaded": not sys._is_gil_enabled()
            if hasattr(sys, "_is_gil_enabled")
            else False,
        }

    def info(self) -> Dict[str, Any]:
        """Compatibility alias for getting detailed system information."""
        return self.get_info()

    def exit_app(self) -> None:
        """
        Exit the application gracefully.

        Terminates the application process.
        """
        logger.info("Exiting application")
        sys.exit(0)

    def exit(self) -> None:
        """Compatibility alias for exiting the application."""
        self.exit_app()

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get an environment variable.

        Args:
            key: The environment variable name.
            default: Default value if not found.

        Returns:
            The environment variable value, or default.
        """
        return os.environ.get(key, default)

    def get_cwd(self) -> str:
        """
        Get the current working directory.

        Returns:
            The current working directory path.
        """
        return os.getcwd()

    def open_url(self, url: str) -> None:
        """
        Open a URL in the default browser.

        Args:
            url: The URL to open.
        """
        webbrowser.open(url)
        logger.debug(f"Opened URL: {url}")

    def open_file(self, path: str) -> None:
        """
        Open a file with the default application.

        Args:
            path: Path to the file to open.
        """
        path = os.path.abspath(path)

        try:
            current_platform = self.get_platform()
            if current_platform == "windows":
                os.startfile(path)  # type: ignore[attr-defined]  # Windows-only
            elif current_platform == "macos":
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)

            logger.debug(f"Opened file: {path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            raise
