from unittest.mock import MagicMock

import pytest

from forge.api.window_messaging import WindowMessagingAPI


@pytest.fixture
def messaging():
    mock_app = MagicMock()
    mock_app.windows = MagicMock()
    mock_app.windows.evaluate_script.return_value = {"ok": True}
    mock_app.windows.broadcast.return_value = {"ok": True, "count": 2}

    return WindowMessagingAPI(mock_app)


def test_window_send(messaging):
    res = messaging.window_send("secondary", "test_event", {"data": 123})
    assert res["ok"] is True
    assert res["delivered"] is True

    messaging._app.windows.evaluate_script.assert_called_once()
    script = messaging._app.windows.evaluate_script.call_args[1]["script"]
    assert "test_event" in script
    assert "123" in script


def test_window_send_invalid_label(messaging):
    messaging._app.windows.evaluate_script.return_value = {"ok": False, "error": "Not found"}
    res = messaging.window_send("missing", "test_event", {})
    assert res["ok"] is False
    assert "error" in res


def test_window_broadcast(messaging):
    res = messaging.window_broadcast("test_event", {"payload": "test"}, exclude_self=False)
    assert res["ok"] is True
    assert res["delivered_count"] == 2

    messaging._app.windows.broadcast.assert_called_once()
