"""Forge desktop notification API."""

from __future__ import annotations

import importlib
import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from forge.bridge import command

logger = logging.getLogger(__name__)


class NotificationAPI:
    """Desktop notification surface with graceful backend fallback."""

    __forge_capability__ = "notifications"

    def __init__(self, app: Any) -> None:
        self._app = app
        self._backend_name = "none"
        self._backend_available = False
        self._history: list[dict[str, Any]] = []
        self._max_history = 50

    def _resolve_backend(self) -> tuple[str, Any] | None:
        try:
            notification_module = importlib.import_module("plyer.notification")
            self._backend_name = "plyer"
            self._backend_available = True
            return self._backend_name, notification_module
        except ImportError:
            pass

        if platform.system() == "Linux" and shutil.which("notify-send"):
            self._backend_name = "notify-send"
            self._backend_available = True
            return self._backend_name, shutil.which("notify-send")

        if platform.system() == "Darwin" and shutil.which("osascript"):
            self._backend_name = "osascript"
            self._backend_available = True
            return self._backend_name, shutil.which("osascript")

        if platform.system() == "Windows" and shutil.which("powershell"):
            self._backend_name = "powershell"
            self._backend_available = True
            return self._backend_name, shutil.which("powershell")

        self._backend_name = "none"
        self._backend_available = False
        return None

    def _record(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._history.append(payload)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        self._app.emit("notification:sent", payload)
        return payload

    @command("notification_notify")
    def notify(
        self,
        title: str,
        body: str,
        icon: str | None = None,
        app_name: str | None = None,
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Send a desktop notification using the best available backend."""
        if not title:
            raise ValueError("Notification title cannot be empty")

        backend = self._resolve_backend()
        payload = {
            "title": title,
            "body": body,
            "icon": str(Path(icon).resolve()) if icon else None,
            "app_name": app_name or self._app.config.app.name,
            "timeout": int(timeout),
            "backend": backend[0] if backend is not None else self._backend_name,
            "delivered": False,
        }

        if backend is None:
            logger.info("No notification backend available")
            return self._record(payload)

        backend_name, backend_impl = backend
        try:
            if backend_name == "plyer":
                backend_impl.notify(
                    title=title,
                    message=body,
                    app_name=payload["app_name"],
                    timeout=payload["timeout"],
                    app_icon=payload["icon"],
                )
            elif backend_name == "notify-send":
                cmd = [backend_impl, title, body]
                if payload["icon"]:
                    cmd.extend(["-i", payload["icon"]])
                subprocess.run(cmd, check=False, capture_output=True, text=True)
            elif backend_name == "osascript":
                script = f'display notification {body!r} with title {title!r}'
                subprocess.run([backend_impl, "-e", script], check=False, capture_output=True, text=True)
            elif backend_name == "powershell":
                script = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$n=New-Object System.Windows.Forms.NotifyIcon;"
                    "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                    f'$n.BalloonTipTitle={title!r};'
                    f'$n.BalloonTipText={body!r};'
                    "$n.Visible=$true;"
                    f'$n.ShowBalloonTip({max(int(timeout), 1) * 1000});'
                )
                subprocess.run([backend_impl, "-NoProfile", "-Command", script], check=False, capture_output=True, text=True)
            payload["delivered"] = True
        except Exception as exc:
            payload["error"] = str(exc)
            logger.warning(f"notification delivery failed: {exc}")

        return self._record(payload)

    @command("notification_state")
    def state(self) -> dict[str, Any]:
        """Return notification backend and delivery history information."""
        self._resolve_backend()
        return {
            "backend": self._backend_name,
            "backend_available": self._backend_available,
            "sent_count": len(self._history),
            "last": self._history[-1] if self._history else None,
        }

    @command("notification_history")
    def history(self, limit: int | None = 20) -> list[dict[str, Any]]:
        """Return recently sent notification metadata."""
        if limit is None or limit <= 0:
            return list(self._history)
        return self._history[-int(limit) :]
