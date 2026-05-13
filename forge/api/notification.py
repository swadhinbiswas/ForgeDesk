"""Forge desktop notification API."""

from __future__ import annotations

import logging
from typing import Any

from forge.bridge import command
from forge.forge_core import NotificationManager  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class NotificationAPI:
    """Desktop notification surface with native Rust backend."""

    __forge_capability__ = "notifications"

    def __init__(self, app: Any) -> None:
        self._app = app
        self._manager = NotificationManager()
        self._history: list[dict[str, Any]] = []
        self._max_history = 50

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

        payload = {
            "title": title,
            "body": body,
            "icon": icon,
            "app_name": app_name or self._app.config.app.name,
            "timeout": int(timeout),
            "backend": "notify-rust",
            "delivered": False,
        }

        try:
            self._manager.show(
                title,
                body,
                payload["app_name"],
                payload["icon"],
                int(timeout * 1000) if timeout else None,
            )
            payload["delivered"] = True
        except Exception as exc:
            payload["error"] = str(exc)
            logger.warning(f"notification delivery failed: {exc}")

        return self._record(payload)

    @command("notification_state")
    def state(self) -> dict[str, Any]:
        """Return notification backend and delivery history information."""
        return {
            "backend": "notify-rust",
            "backend_available": True,
            "sent_count": len(self._history),
            "last": self._history[-1] if self._history else None,
        }

    @command("notification_history")
    def history(self, limit: int | None = 20) -> list[dict[str, Any]]:
        """Return recently sent notification metadata."""
        if limit is None or limit <= 0:
            return list(self._history)
        return self._history[-int(limit) :]
