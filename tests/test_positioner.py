from unittest.mock import MagicMock

import pytest

from forge.api.positioner import PositionerAPI


@pytest.fixture
def positioner():
    mock_app = MagicMock()
    mock_app.windows = MagicMock()
    mock_app.config.window.width = 800
    mock_app.config.window.height = 600

    # Mock screen api
    mock_screen = MagicMock()
    mock_screen.get_current.return_value = {"ok": True, "width": 1920, "height": 1080}
    mock_app._screen_api = mock_screen

    return PositionerAPI(mock_app)


def test_position_center(positioner):
    res = positioner.position_center("main")
    assert res["ok"] is True
    # 1920/2 - 800/2 = 960 - 400 = 560
    # 1080/2 - 600/2 = 540 - 300 = 240
    assert res["x"] == 560
    assert res["y"] == 240
    positioner._app.windows.set_position.assert_called_once_with(label="main", x=560, y=240)


def test_position_top_right(positioner):
    res = positioner.position_top_right("main", margin=20)
    assert res["ok"] is True
    # 1920 - 800 - 20 = 1100
    # 0 + 20 = 20
    assert res["x"] == 1100
    assert res["y"] == 20
    positioner._app.windows.set_position.assert_called_once_with(label="main", x=1100, y=20)


def test_position_bottom_left(positioner):
    res = positioner.position_bottom_left("main", margin=20)
    assert res["ok"] is True
    # 0 + 20 = 20
    # 1080 - 600 - 20 = 460
    assert res["x"] == 20
    assert res["y"] == 460
    positioner._app.windows.set_position.assert_called_once_with(label="main", x=20, y=460)
