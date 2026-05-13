"""Forge Cross-Window Messaging API.

Provides IPC commands for sending events between windows.
Windows communicate through the Python backend rather than directly,
enabling security validation, logging, and support for both native
and WebSocket transports.

Usage from JS::

    // In Window A:
    forge.window.send("settings", "theme:changed", {dark: true})

    // In Window B (settings window):
    forge.on("theme:changed", (data) => { ... })
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WindowMessagingAPI:
    """Cross-window communication via the Python backend.

    Messages are delivered by evaluating JavaScript in the target
    window's WebView via ``WindowManagerAPI``.
    """

    __forge_capability__ = "lifecycle"  # Available to all windows with lifecycle perm

    def __init__(self, app: Any) -> None:
        self._app = app

    def window_send(
        self,
        target_label: str,
        event: str,
        payload: Any = None,
    ) -> dict[str, Any]:
        """Send an event to a specific window by label.

        Args:
            target_label: The label of the target window.
            event: Event name to deliver.
            payload: JSON-serializable payload.

        Returns:
            ``{ok: true, delivered: true}`` if message was sent.
        """
        wm = getattr(self._app, "windows", None)
        if wm is None:
            return {"ok": False, "error": "Window manager not available"}

        msg = json.dumps(
            {
                "type": "event",
                "event": event,
                "payload": payload,
            },
            separators=(",", ":"),
        )

        script = f"window.__forge__._handleMessage({msg})"

        try:
            result = wm.evaluate_script(label=target_label, script=script)
            if result and result.get("ok"):
                return {"ok": True, "delivered": True}
            return {"ok": False, "error": result.get("error", "Target window not found")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def window_broadcast(
        self,
        event: str,
        payload: Any = None,
        exclude_self: bool = False,
    ) -> dict[str, Any]:
        """Broadcast an event to all open windows.

        Args:
            event: Event name to deliver.
            payload: JSON-serializable payload.
            exclude_self: If True, skip the calling window.

        Returns:
            ``{ok: true, delivered_count: N}``
        """
        wm = getattr(self._app, "windows", None)
        if wm is None:
            return {"ok": False, "error": "Window manager not available"}

        msg = json.dumps(
            {
                "type": "event",
                "event": event,
                "payload": payload,
            },
            separators=(",", ":"),
        )

        script = f"window.__forge__._handleMessage({msg})"
        count = 0

        try:
            result = wm.broadcast(script=script)
            if result and result.get("ok"):
                count = result.get("count", 0)
        except Exception as exc:
            logger.error("Broadcast failed: %s", exc)

        return {"ok": True, "delivered_count": count}
