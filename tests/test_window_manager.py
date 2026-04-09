"""Tests for WindowManagerAPI label-targeted controls."""
import pytest
from unittest.mock import MagicMock, patch


def make_app_with_child_window():
    """Create a ForgeApp with a child window registered."""
    from forge.app import ForgeApp
    app = ForgeApp.__new__(ForgeApp)
    # Minimal init to avoid full startup
    from forge.config import ForgeConfig
    app.config = ForgeConfig()
    app._proxy = None
    app._is_ready = False
    app._dev_server_url = None
    app._log_buffer = MagicMock()
    app._runtime_events = []
    from forge.events import EventEmitter
    app.events = EventEmitter()
    from forge.window import WindowAPI, WindowManagerAPI
    app.window = WindowAPI(app)
    app.windows = WindowManagerAPI(app)
    # Register main window
    app.windows._windows["main"] = {
        "label": "main", "title": "Main", "width": 800, "height": 600,
        "visible": True, "focused": True, "closed": False,
        "x": 0, "y": 0, "fullscreen": False, "minimized": False, "maximized": False,
    }
    # Register child window
    app.windows._windows["settings"] = {
        "label": "settings", "title": "Settings", "width": 400, "height": 300,
        "visible": True, "focused": False, "closed": False,
        "x": 100, "y": 100, "fullscreen": False, "minimized": False, "maximized": False,
    }
    return app


class TestLabelTargetedControls:
    def test_set_title_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.set_title("settings", "New Settings Title")
        assert app.windows._windows["settings"]["title"] == "New Settings Title"

    def test_set_size_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.set_size("settings", 500, 400)
        assert app.windows._windows["settings"]["width"] == 500
        assert app.windows._windows["settings"]["height"] == 400

    def test_set_position_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.set_position("settings", 200, 300)
        assert app.windows._windows["settings"]["x"] == 200
        assert app.windows._windows["settings"]["y"] == 300

    def test_focus_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.focus("settings")
        assert app.windows._windows["settings"]["focused"] is True

    def test_minimize_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.minimize("settings")
        assert app.windows._windows["settings"]["minimized"] is True
        assert app.windows._windows["settings"]["maximized"] is False

    def test_maximize_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.maximize("settings")
        assert app.windows._windows["settings"]["maximized"] is True
        assert app.windows._windows["settings"]["minimized"] is False

    def test_set_fullscreen_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.set_fullscreen("settings", True)
        assert app.windows._windows["settings"]["fullscreen"] is True

    def test_show_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows._windows["settings"]["visible"] = False
        app.windows.show("settings")
        assert app.windows._windows["settings"]["visible"] is True

    def test_hide_updates_child_descriptor(self):
        app = make_app_with_child_window()
        app.windows.hide("settings")
        assert app.windows._windows["settings"]["visible"] is False


class TestLabelValidation:
    def test_unknown_label_raises_key_error(self):
        app = make_app_with_child_window()
        with pytest.raises(KeyError, match="Unknown window label"):
            app.windows.set_title("nonexistent", "Title")

    def test_empty_label_raises_value_error(self):
        app = make_app_with_child_window()
        with pytest.raises(ValueError, match="Window label is required"):
            app.windows.set_title("", "Title")

    def test_label_normalization(self):
        app = make_app_with_child_window()
        # " Settings " should normalize to "settings"
        app.windows.set_title(" Settings ", "Normalized Title")
        assert app.windows._windows["settings"]["title"] == "Normalized Title"

    def test_invalid_size_raises_value_error(self):
        app = make_app_with_child_window()
        with pytest.raises(ValueError, match="positive"):
            app.windows.set_size("settings", 0, 100)


class TestMainWindowDelegation:
    def test_set_title_main_delegates_to_window_api(self):
        app = make_app_with_child_window()
        app.window.set_title = MagicMock()
        app.windows.set_title("main", "Updated Main Title")
        app.window.set_title.assert_called_once_with("Updated Main Title")
