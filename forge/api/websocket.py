"""Forge WebSocket Client API.

Provides managed WebSocket client connections from the Python backend.
The frontend calls ``ws_connect(url)`` to open a connection; incoming
messages are pushed to the JS frontend via the event channel system.

Security:
    - WebSocket connections require the ``websocket`` capability.
    - If ``WebSocketPermissions.allowed_origins`` is configured, only
      those server URLs may be connected to.

NoGIL Notes:
    Each WebSocket connection runs in its own daemon thread. Under
    Python 3.14+ free-threaded mode, multiple connections process
    messages truly in parallel.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "websocket"


class WSState(StrEnum):
    CONNECTING = "connecting"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class _WSConnection:
    """Internal state for a managed WebSocket connection."""

    connection_id: str
    url: str
    state: WSState = WSState.CONNECTING
    created_at: float = 0.0
    thread: threading.Thread | None = field(default=None, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    ws: Any = field(default=None, repr=False)  # websockets sync connection
    error: str | None = None
    messages_sent: int = 0
    messages_received: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "url": self.url,
            "state": self.state.value,
            "created_at": self.created_at,
            "error": self.error,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
        }


class WebSocketAPI:
    """WebSocket client manager exposed to the frontend via IPC.

    Each connection runs in a background thread and pushes incoming
    messages to the frontend via ``app.emit()``.

    Events emitted:
    - ``ws:open``     — ``{connection_id, url}``
    - ``ws:message``  — ``{connection_id, data, binary}``
    - ``ws:close``    — ``{connection_id, code, reason}``
    - ``ws:error``    — ``{connection_id, error}``
    """

    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app
        self._connections: dict[str, _WSConnection] = {}
        self._lock = threading.Lock()

    def ws_connect(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        protocols: list[str] | None = None,
        auto_reconnect: bool = False,
        reconnect_delay: float = 2.0,
        max_reconnect_attempts: int = 5,
    ) -> dict[str, Any]:
        """Open a new WebSocket connection.

        Args:
            url: WebSocket server URL (ws:// or wss://).
            headers: Optional HTTP headers for the handshake.
            protocols: Optional subprotocols to request.
            auto_reconnect: If True, auto-reconnect on unexpected close.
            reconnect_delay: Initial delay between reconnection attempts.
            max_reconnect_attempts: Maximum reconnection attempts (0 = unlimited).

        Returns:
            ``{ok: true, connection_id: "..."}`` on success.
        """
        # Validate URL scheme
        if not url.startswith(("ws://", "wss://")):
            return {"ok": False, "error": "URL must use ws:// or wss:// scheme"}

        # Check WebSocket permission scopes
        perm = self._app.config.permissions.websocket
        if hasattr(perm, "allowed_origins") and perm.allowed_origins:
            allowed = False
            for pattern in perm.allowed_origins:
                if url.startswith(pattern) or pattern == "*":
                    allowed = True
                    break
            if not allowed:
                return {
                    "ok": False,
                    "error": f"WebSocket connection to {url} not allowed by permissions",
                }

        # Check max connections
        max_conns = perm.max_connections if hasattr(perm, "max_connections") else 10
        with self._lock:
            active = sum(
                1
                for c in self._connections.values()
                if c.state in (WSState.CONNECTING, WSState.OPEN)
            )
            if active >= max_conns:
                return {"ok": False, "error": f"Maximum connections ({max_conns}) reached"}

        conn_id = str(uuid.uuid4())
        conn = _WSConnection(
            connection_id=conn_id,
            url=url,
            created_at=time.time(),
        )

        def _reader() -> None:
            """Background thread: connect, read messages, emit events."""
            attempts = 0
            while not conn.cancel_event.is_set():
                try:
                    import websockets.sync.client as ws_client  # type: ignore[import-not-found]

                    extra_headers = headers or {}
                    subprotocols = protocols or []

                    conn.state = WSState.CONNECTING
                    with ws_client.connect(
                        url,
                        additional_headers=extra_headers,
                        subprotocols=subprotocols,
                        close_timeout=5,
                    ) as websocket:
                        conn.ws = websocket
                        conn.state = WSState.OPEN
                        conn.error = None
                        attempts = 0
                        self._emit("ws:open", {"connection_id": conn_id, "url": url})

                        for message in websocket:
                            if conn.cancel_event.is_set():
                                break
                            conn.messages_received += 1
                            is_binary = isinstance(message, bytes)
                            self._emit(
                                "ws:message",
                                {
                                    "connection_id": conn_id,
                                    "data": message if not is_binary else message.hex(),
                                    "binary": is_binary,
                                },
                            )

                    # Clean close
                    conn.state = WSState.CLOSED
                    self._emit(
                        "ws:close",
                        {
                            "connection_id": conn_id,
                            "code": 1000,
                            "reason": "normal",
                        },
                    )
                    if not auto_reconnect:
                        break

                except Exception as exc:
                    conn.state = WSState.ERROR
                    conn.error = str(exc)
                    conn.ws = None
                    self._emit(
                        "ws:error",
                        {
                            "connection_id": conn_id,
                            "error": str(exc),
                        },
                    )

                    if not auto_reconnect or conn.cancel_event.is_set():
                        conn.state = WSState.CLOSED
                        break

                    attempts += 1
                    if max_reconnect_attempts > 0 and attempts >= max_reconnect_attempts:
                        logger.warning("WS %s max reconnect attempts reached", conn_id)
                        conn.state = WSState.CLOSED
                        self._emit(
                            "ws:close",
                            {
                                "connection_id": conn_id,
                                "code": 1006,
                                "reason": "max reconnect attempts",
                            },
                        )
                        break

                    # Exponential backoff
                    delay = min(reconnect_delay * (2 ** (attempts - 1)), 60.0)
                    logger.info(
                        "WS %s reconnecting in %.1fs (attempt %d)", conn_id, delay, attempts
                    )
                    conn.cancel_event.wait(delay)

        thread = threading.Thread(target=_reader, name=f"forge-ws-{conn_id[:8]}", daemon=True)
        conn.thread = thread

        with self._lock:
            self._connections[conn_id] = conn

        thread.start()
        return {"ok": True, "connection_id": conn_id}

    def ws_send(self, connection_id: str, data: str) -> dict[str, Any]:
        """Send a text message on an open WebSocket connection.

        Args:
            connection_id: The connection ID returned by ``ws_connect``.
            data: The text data to send.

        Returns:
            ``{ok: true}`` on success.
        """
        with self._lock:
            conn = self._connections.get(connection_id)
        if conn is None:
            return {"ok": False, "error": "Connection not found"}
        if conn.state != WSState.OPEN or conn.ws is None:
            return {"ok": False, "error": f"Connection is {conn.state.value}"}
        try:
            conn.ws.send(data)
            conn.messages_sent += 1
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def ws_send_binary(self, connection_id: str, data_b64: str) -> dict[str, Any]:
        """Send binary data (base64-encoded) on an open WebSocket connection.

        Args:
            connection_id: The connection ID.
            data_b64: Base64-encoded binary data.

        Returns:
            ``{ok: true}`` on success.
        """
        import base64

        with self._lock:
            conn = self._connections.get(connection_id)
        if conn is None:
            return {"ok": False, "error": "Connection not found"}
        if conn.state != WSState.OPEN or conn.ws is None:
            return {"ok": False, "error": f"Connection is {conn.state.value}"}
        try:
            raw = base64.b64decode(data_b64)
            conn.ws.send(raw)
            conn.messages_sent += 1
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def ws_close(
        self,
        connection_id: str,
        code: int = 1000,
        reason: str = "client close",
    ) -> dict[str, Any]:
        """Close a WebSocket connection.

        Args:
            connection_id: The connection ID.
            code: WebSocket close code (default 1000).
            reason: Close reason string.

        Returns:
            ``{ok: true}`` on success.
        """
        with self._lock:
            conn = self._connections.get(connection_id)
        if conn is None:
            return {"ok": False, "error": "Connection not found"}
        conn.cancel_event.set()
        if conn.ws is not None:
            try:
                conn.ws.close(code, reason)
            except Exception:
                pass  # Already closed or broken
        conn.state = WSState.CLOSED
        return {"ok": True}

    def ws_state(self, connection_id: str) -> dict[str, Any]:
        """Get the current state of a WebSocket connection."""
        with self._lock:
            conn = self._connections.get(connection_id)
        if conn is None:
            return {"ok": False, "error": "Connection not found"}
        return {"ok": True, **conn.snapshot()}

    def ws_list(self) -> dict[str, Any]:
        """List all WebSocket connections."""
        with self._lock:
            connections = [c.snapshot() for c in self._connections.values()]
        return {"ok": True, "connections": connections}

    def close_all(self) -> int:
        """Close all connections. Used during app shutdown."""
        count = 0
        with self._lock:
            conns = list(self._connections.values())
        for conn in conns:
            conn.cancel_event.set()
            if conn.ws is not None:
                try:
                    conn.ws.close()
                except Exception:
                    pass
            conn.state = WSState.CLOSED
            count += 1
        return count

    def _emit(self, event: str, data: dict) -> None:
        """Emit a WebSocket event to the frontend."""
        if self._app and hasattr(self._app, "emit"):
            try:
                self._app.emit(event, data)
            except Exception:
                pass
