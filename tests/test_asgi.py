"""
Tests for the Forge Web Mode (ASGI) proxy.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.app import ForgeApp
from forge.asgi import ASGIApp, ASGIWebSocketProxy


@pytest.fixture
def mock_app(tmp_path):
    """Create a mocked ForgeApp instance."""
    app = ForgeApp.__new__(ForgeApp)
    app.config = MagicMock()
    app._is_ready = False

    # Mocking config paths to our temp directory
    app.config.get_frontend_path.return_value = tmp_path / "frontend"
    app._on_ipc_message = MagicMock()
    return app


@pytest.mark.asyncio
async def test_websocket_proxy_evaluate_script():
    """Verify ASGIWebSocketProxy strips evaluate_script wrapping and sends raw JSON payload."""
    send_mock = AsyncMock()
    loop = asyncio.get_running_loop()
    proxy = ASGIWebSocketProxy(send_mock, loop)

    proxy.evaluate_script('window.__forge__._handleMessage({"type": "reply", "id": 1})')

    # Give the threadsafe coroutine a tiny moment to run within the current loop
    await asyncio.sleep(0.01)

    send_mock.assert_called_once_with(
        {"type": "websocket.send", "text": '{"type": "reply", "id": 1}'}
    )


@pytest.mark.asyncio
async def test_asgi_http_routing_no_frontend_dir(mock_app):
    """Test standard ASGI routing fails gracefully with 404 when no directory exists."""
    asgi_app = ASGIApp(mock_app)

    scope = {"type": "http", "path": "/"}
    receive = AsyncMock()
    send = AsyncMock()

    await asgi_app(scope, receive, send)

    # First call should be the 404 response start
    send.assert_any_call(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", b"28")],
        }
    )


@pytest.mark.asyncio
async def test_asgi_http_routing_valid_file(mock_app, tmp_path):
    """Test ASGI routing correctly serves an existing file."""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    test_file = frontend_dir / "test.txt"
    test_file.write_text("hello forge")

    asgi_app = ASGIApp(mock_app)

    scope = {"type": "http", "path": "/test.txt"}
    receive = AsyncMock()
    send = AsyncMock()

    await asgi_app(scope, receive, send)

    # First call response start
    send.assert_any_call(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", b"11")],
        }
    )

    # Second call response body
    send.assert_any_call({"type": "http.response.body", "body": b"hello forge", "more_body": False})


@pytest.mark.asyncio
async def test_asgi_http_routing_directory_traversal(mock_app, tmp_path):
    """Test ASGI routing prevents directory traversal."""
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("password")

    asgi_app = ASGIApp(mock_app)

    # Attempt directory traversal
    scope = {"type": "http", "path": "/../secret.txt"}
    receive = AsyncMock()
    send = AsyncMock()

    await asgi_app(scope, receive, send)

    assert send.call_args_list[0][0][0]["status"] == 404


@pytest.mark.asyncio
async def test_asgi_websocket_intercepts(mock_app):
    """Test ASGI successfully intercepts /_forge/ipc websocket requests."""
    asgi_app = ASGIApp(mock_app)

    scope = {"type": "websocket", "path": "/_forge/ipc"}

    # We will simulate the client sending a connect, then a receive, then disconnect
    receive = AsyncMock(
        side_effect=[
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": '{"cmd":"ping"}'},
            {"type": "websocket.disconnect"},
        ]
    )
    send = AsyncMock()

    await asgi_app(scope, receive, send)

    # Should accept the connection
    send.assert_any_call({"type": "websocket.accept"})

    # Yield control repeatedly to allow the asyncio.to_thread backend to fire its mock
    await asyncio.sleep(0.05)

    # Ensure bridge integration is called with correct text
    assert mock_app._on_ipc_message.call_count == 1
    call_args = mock_app._on_ipc_message.call_args[0]
    assert call_args[0] == '{"cmd":"ping"}'
    assert isinstance(call_args[1], ASGIWebSocketProxy)
