"""Extended window manager tests — dispatch_event, create, close, and URL resolution."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest


def make_app():
    """Create a ForgeApp with minimal init for window manager testing."""
    from forge.app import ForgeApp
    from forge.config import ForgeConfig
    from forge.events import EventEmitter
    from forge.window import WindowAPI, WindowManagerAPI

    app = ForgeApp.__new__(ForgeApp)
    app.config = ForgeConfig()
    app._proxy = None
    app._is_ready = False
    app._dev_server_url = None
    app._log_buffer = MagicMock()
    app._runtime_events = []
    app.events = EventEmitter()
    app.window = WindowAPI(app)
    app.windows = WindowManagerAPI(app)
    app.windows._windows["main"] = {
        "label": "main", "title": "Main", "width": 800, "height": 600,
        "visible": True, "focused": True, "closed": False,
        "x": 0, "y": 0, "fullscreen": False, "minimized": False, "maximized": False,
        "backend": "native",
    }
    return app


class TestDispatchEvent:

    def test_dispatch_created_event(self):
        app = make_app()
        label = app.windows._apply_native_event("created", {
            "label": "popup", "width": 500, "height": 400,
            "visible": True, "focused": False,
        })
        assert label == "popup"
        assert app.windows._windows["popup"]["closed"] is False
        assert app.windows._windows["popup"]["visible"] is True

    def test_dispatch_close_requested(self):
        app = make_app()
        app.windows._windows["panel"] = {
            "label": "panel", "visible": True, "focused": True, "closed": False,
        }
        app.windows._apply_native_event("close_requested", {"label": "panel"})
        assert app.windows._windows["panel"]["visible"] is False
        assert app.windows._windows["panel"]["focused"] is False

    def test_dispatch_destroyed(self):
        app = make_app()
        app.windows._windows["panel"] = {
            "label": "panel", "visible": True, "focused": True, "closed": False,
        }
        app.windows._apply_native_event("destroyed", {"label": "panel"})
        assert app.windows._windows["panel"]["closed"] is True
        assert app.windows._windows["panel"]["visible"] is False

    def test_dispatch_focused(self):
        app = make_app()
        app.windows._windows["panel"] = {
            "label": "panel", "visible": True, "focused": False, "closed": False,
        }
        app.windows._apply_native_event("focused", {"label": "panel", "focused": True})
        assert app.windows._windows["panel"]["focused"] is True

    def test_dispatch_navigated(self):
        app = make_app()
        app.windows._windows["panel"] = {
            "label": "panel", "visible": True, "focused": False, "closed": False,
            "url": "forge://app/index.html",
        }
        app.windows._apply_native_event("navigated", {
            "label": "panel", "url": "https://example.com",
        })
        assert app.windows._windows["panel"]["url"] == "https://example.com"

    def test_dispatch_main_syncs(self):
        app = make_app()
        # Should not raise even without a real proxy
        label = app.windows._apply_native_event("focused", {"label": "main"})
        assert label == "main"

    def test_dispatch_updates_size(self):
        app = make_app()
        app.windows._windows["panel"] = {
            "label": "panel", "visible": True, "focused": False, "closed": False,
            "width": 400, "height": 300,
        }
        app.windows._apply_native_event("resized", {
            "label": "panel", "width": 600, "height": 500,
        })
        assert app.windows._windows["panel"]["width"] == 600
        assert app.windows._windows["panel"]["height"] == 500


class TestURLResolution:

    def test_default_url(self):
        app = make_app()
        url = app.windows._resolve_url()
        assert url == "forge://app/index.html"

    def test_explicit_url(self):
        app = make_app()
        url = app.windows._resolve_url(explicit_url="https://custom.com")
        assert url == "https://custom.com"

    def test_custom_route(self):
        app = make_app()
        url = app.windows._resolve_url(route="/settings")
        assert url == "forge://app/settings"

    def test_dev_server_url(self):
        app = make_app()
        app._dev_server_url = "http://localhost:5173"
        url = app.windows._resolve_url(route="/")
        assert url == "http://localhost:5173/"

    def test_dev_server_with_route(self):
        app = make_app()
        app._dev_server_url = "http://localhost:5173/"
        url = app.windows._resolve_url(route="/settings")
        assert url == "http://localhost:5173/settings"


class TestWindowClose:

    def test_close_child_window(self):
        app = make_app()
        app.windows._windows["popup"] = {
            "label": "popup", "visible": True, "focused": True,
            "closed": False, "backend": "managed-popup",
        }
        result = app.windows.close("popup")
        assert result is True
        assert app.windows._windows["popup"]["closed"] is True
        assert app.windows._windows["popup"]["visible"] is False

    def test_close_unknown_raises(self):
        app = make_app()
        with pytest.raises(KeyError, match="Unknown window label"):
            app.windows.close("nonexistent")


class TestWindowList:

    def test_list_returns_all_windows(self):
        app = make_app()
        app.windows._windows["settings"] = {"label": "settings"}
        windows = app.windows.list()
        labels = [w["label"] for w in windows]
        assert "main" in labels
        assert "settings" in labels

    def test_get_returns_specific_window(self):
        app = make_app()
        app.windows._windows["settings"] = {"label": "settings", "title": "Settings"}
        win = app.windows.get("settings")
        assert win is not None
        assert win["title"] == "Settings"

    def test_get_unknown_raises_key_error(self):
        app = make_app()
        with pytest.raises(KeyError, match="Unknown window label"):
            app.windows.get("nonexistent")


class TestSupportChecks:

    def test_supports_native_multiwindow_without_proxy(self):
        app = make_app()
        assert app.windows._supports_native_multiwindow() is False

    def test_supports_native_multiwindow_with_proxy(self):
        app = make_app()
        app._proxy = MagicMock()
        app._proxy.create_window = MagicMock()
        assert app.windows._supports_native_multiwindow() is True

    def test_emit_frontend_open_without_proxy(self):
        app = make_app()
        # Should not raise
        app.windows._emit_frontend_open({"label": "test"})

    def test_emit_frontend_close_without_proxy(self):
        app = make_app()
        # Should not raise
        app.windows._emit_frontend_close("test")
