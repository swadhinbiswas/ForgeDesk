"""
Forge Framework ASGI Integration.

Allows ForgeApp to act as an ASGI application, enabling it to be served
by Uvicorn, Hypercorn, or Daphne in "Web Mode". Serves the frontend
directory statically and bridges IPC commands seamlessly over WebSockets.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app import ForgeApp

logger = logging.getLogger("forge.asgi")


class ASGIWebSocketProxy:
    """
    Mocks the Rust WindowProxy so that the IPC Bridge can
    call `evaluate_script()` and we can forward that data through the WebSocket.
    """

    def __init__(
        self, send: Callable[[dict[str, Any]], Awaitable[None]], loop: asyncio.AbstractEventLoop
    ) -> None:
        self.send = send
        self.loop = loop

    def evaluate_script(self, script: str) -> None:
        """
        Extract the JSON payload from the `window.__forge__._handleMessage(...)` script
        and send it securely over the WebSocket.
        """
        # We only really care about sending the JSON payload back over the websocket
        # Luckily, the bridge typically formats this as window.__forge__._handleMessage({...})
        prefix = "window.__forge__._handleMessage("
        suffix = ")"

        payload_text = script
        if script.startswith(prefix) and script.endswith(suffix):
            payload_text = script[len(prefix) : -len(suffix)]

        asyncio.run_coroutine_threadsafe(
            self.send({"type": "websocket.send", "text": payload_text}),  # type: ignore[arg-type]
            self.loop,
        )


class ASGIApp:
    """
    The main ASGI callable handler.
    Initialized with the current ForgeApp instance.
    """

    def __init__(self, app: ForgeApp) -> None:
        self.app = app
        self._frontend_dir = self.app.config.get_frontend_path()
        self._forge_js_path = Path(__file__).parent / "js" / "forge.js"

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            raise NotImplementedError(f"Unknown scope type {scope['type']}")

    async def _handle_http(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        path = scope.get("path", "/")

        # 1. Intercept requests for forge.js
        if path == "/forge.js":
            await self._serve_file(self._forge_js_path, send)
            return

        # 2. Serve static frontend files
        if not self._frontend_dir.exists():
            await self._send_404(send, "Frontend directory not found")
            return

        # Determine requested file
        target_path = path.lstrip("/")
        if not target_path or target_path == "/":
            target_path = "index.html"

        resolved_path = (self._frontend_dir / target_path).resolve()

        # Security: Prevent directory traversal outside frontend
        if not self._is_path_safe(resolved_path):
            await self._send_404(send, "Access denied")
            return

        if resolved_path.is_file():
            await self._serve_file(resolved_path, send)
        else:
            # SPA Fallback (Serve index.html for 404s to allow client-side routing)
            index_path = self._frontend_dir / "index.html"
            if index_path.is_file():
                await self._serve_file(index_path, send)
            else:
                await self._send_404(send)

    def _is_path_safe(self, resolved_path: Path) -> bool:
        """Ensure the resolved path inside the static dir doesn't escape the frontend directory."""
        try:
            resolved_path.relative_to(self._frontend_dir)
            return True
        except ValueError:
            return False

    async def _serve_file(
        self, file_path: Path, send: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"

        try:
            file_size = file_path.stat().st_size  # noqa: ASYNC240
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", content_type.encode()),
                        (b"content-length", str(file_size).encode()),
                    ],
                }
            )

            with open(file_path, "rb") as f:  # noqa: ASYNC230
                # Streaming files iteratively
                chunk = f.read(65536)
                while chunk:
                    more_body = len(chunk) == 65536
                    await send(
                        {"type": "http.response.body", "body": chunk, "more_body": more_body}
                    )
                    if not more_body:
                        break
                    chunk = f.read(65536)
        except Exception as e:
            logger.error(f"Error serving {file_path}: {e}")
            await self._send_404(send)

    async def _send_404(
        self, send: Callable[[dict[str, Any]], Awaitable[None]], message: str = "Not Found"
    ) -> None:
        body = message.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    async def _handle_websocket(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        path = scope.get("path", "/")

        # Only allow ipc websocket connections
        if path != "/_forge/ipc":
            await send({"type": "websocket.close", "code": 403})
            return

        # Handle handshake
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
                break
            elif message["type"] == "websocket.disconnect":
                return

        proxy = ASGIWebSocketProxy(send, asyncio.get_running_loop())

        # Mark app as ready on the initial connection
        if not self.app._is_ready:
            self.app._is_ready = True

        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                break
            elif message["type"] == "websocket.receive":
                text_data = message.get("text")
                if text_data:
                    # Offload the blocking execution to a threadpool to prevent ASGI blockage
                    await asyncio.to_thread(self.app._on_ipc_message, text_data, proxy)
