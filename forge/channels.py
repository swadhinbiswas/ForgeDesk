"""Forge Event Channel System.

Provides named channels for streaming data from Python backend to
JavaScript frontend. Used by WebSocket, file transfer, and task
systems to send multiple messages per initial invoke.

A channel is a named pipe that pushes ``{type: "channel", channel_id, data, done}``
messages to the frontend through the window proxy.

NoGIL Notes:
    Channel send operations are thread-safe. Multiple background threads
    can push data into the same channel concurrently without GIL contention.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _ChannelRecord:
    """Internal state for an active channel."""

    channel_id: str
    name: str
    created_at: float
    message_count: int = 0
    closed: bool = False
    proxy: Any = None  # WindowProxy for sending JS
    target_label: str = "main"


class ChannelManager:
    """Named event channels for streaming data from Python to JS.

    A channel is a named pipe that can push multiple messages to
    the frontend over time. Used for:
    - File upload/download progress
    - WebSocket message streams
    - Background task output
    - Real-time search results

    Usage::

        channel_id = channels.create("download-progress", proxy)
        channels.send(channel_id, {"percent": 25, "bytes": 1024})
        channels.send(channel_id, {"percent": 50, "bytes": 2048})
        channels.send(channel_id, {"percent": 100, "bytes": 4096})
        channels.close(channel_id)
    """

    def __init__(self) -> None:
        self._channels: dict[str, _ChannelRecord] = {}
        self._lock = threading.Lock()

    def create(
        self,
        name: str,
        proxy: Any = None,
        *,
        target_label: str = "main",
    ) -> str:
        """Create a new channel.

        Args:
            name: Human-readable channel name (e.g. "download-progress").
            proxy: WindowProxy used to send messages to the WebView.
            target_label: The window label to target.

        Returns:
            The channel_id string.
        """
        channel_id = str(uuid.uuid4())
        record = _ChannelRecord(
            channel_id=channel_id,
            name=name,
            created_at=time.monotonic(),
            proxy=proxy,
            target_label=target_label,
        )
        with self._lock:
            self._channels[channel_id] = record
        return channel_id

    def send(self, channel_id: str, data: Any) -> bool:
        """Send data through a channel.

        The data is delivered to the frontend as a JSON message:
        ``{type: "channel", channel_id: "...", data: {...}, done: false}``

        Args:
            channel_id: The channel to send on.
            data: Any JSON-serializable data.

        Returns:
            True if the message was sent, False if channel not found or closed.
        """
        with self._lock:
            record = self._channels.get(channel_id)
            if record is None or record.closed:
                return False
            record.message_count += 1
            proxy = record.proxy

        if proxy is not None:
            self._deliver(proxy, channel_id, data, done=False)
            return True
        return False

    def close(self, channel_id: str) -> bool:
        """Close a channel, sending a final ``done: true`` message.

        Args:
            channel_id: The channel to close.

        Returns:
            True if the channel was found and closed.
        """
        with self._lock:
            record = self._channels.get(channel_id)
            if record is None or record.closed:
                return False
            record.closed = True
            proxy = record.proxy

        if proxy is not None:
            self._deliver(proxy, channel_id, None, done=True)
        return True

    def list_channels(self) -> list[dict[str, Any]]:
        """List all active (non-closed) channels."""
        with self._lock:
            return [
                {
                    "channel_id": r.channel_id,
                    "name": r.name,
                    "message_count": r.message_count,
                    "closed": r.closed,
                }
                for r in self._channels.values()
                if not r.closed
            ]

    def close_all(self) -> int:
        """Close all active channels. Used during app shutdown."""
        count = 0
        with self._lock:
            active = [r for r in self._channels.values() if not r.closed]
        for record in active:
            self.close(record.channel_id)
            count += 1
        return count

    @staticmethod
    def _deliver(proxy: Any, channel_id: str, data: Any, *, done: bool) -> None:
        """Deliver a channel message to the frontend via WindowProxy."""
        import json  # noqa: F401  # delayed to avoid circular

        payload = json.dumps(
            {
                "type": "channel",
                "channel_id": channel_id,
                "data": data,
                "done": done,
            },
            separators=(",", ":"),
        )

        script = f"window.__forge__._handleMessage({payload})"
        try:
            proxy.evaluate_script(script)
        except Exception as exc:
            logger.error("Channel %s delivery failed: %s", channel_id, exc)
