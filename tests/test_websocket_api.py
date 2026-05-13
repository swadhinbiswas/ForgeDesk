from unittest.mock import MagicMock, patch

import pytest

from forge.api.websocket import WebSocketAPI, WSState


@pytest.fixture
def ws_api():
    mock_app = MagicMock()
    mock_app.config.permissions.websocket.allowed_origins = []
    mock_app.config.permissions.websocket.max_connections = 10
    api = WebSocketAPI(mock_app)
    return api


@patch("forge.api.websocket.threading.Thread")
def test_ws_connect(mock_thread, ws_api):
    res = ws_api.ws_connect("wss://echo.websocket.events", auto_reconnect=False)

    assert res["ok"] is True
    conn_id = res["connection_id"]
    assert conn_id in ws_api._connections
    mock_thread.assert_called_once()


def test_ws_send_and_close(ws_api):
    res = ws_api.ws_connect("wss://echo.websocket.events")
    conn_id = res["connection_id"]

    mock_ws = MagicMock()
    ws_api._connections[conn_id].ws = mock_ws
    ws_api._connections[conn_id].state = WSState.OPEN

    send_res = ws_api.ws_send(conn_id, "test message")
    assert send_res["ok"] is True
    mock_ws.send.assert_called_once_with("test message")

    close_res = ws_api.ws_close(conn_id)
    assert close_res["ok"] is True
    mock_ws.close.assert_called_once()
    assert ws_api._connections[conn_id].state == WSState.CLOSED
