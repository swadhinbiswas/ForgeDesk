"""Tests for TrayAPI and NotificationAPI — adapted to actual API implementation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


def _make_app():
    app = MagicMock()
    app.config.app.name = "TestApp"
    app.emit = MagicMock()
    return app


# ─── TrayAPI Tests ───

class TestTraySetMenu:

    def test_set_menu_stores_items(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.set_menu([
            {"label": "Show", "action": "show"},
            {"label": "Quit", "action": "quit"},
        ])
        assert len(result) == 2
        assert result[0]["label"] == "Show"

    def test_set_menu_with_separator(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.set_menu([
            {"label": "Show", "action": "show"},
            {"separator": True},
            {"label": "Quit", "action": "quit"},
        ])
        assert len(result) == 3
        assert result[1]["separator"] is True

    def test_set_menu_with_checkable(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.set_menu([
            {"label": "Pin", "action": "pin", "checkable": True, "checked": True},
        ])
        assert result[0]["checkable"] is True
        assert result[0]["checked"] is True

    def test_set_menu_invalid_item_type(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        with pytest.raises(TypeError, match="must be an object"):
            api.set_menu(["invalid"])

    def test_set_menu_invalid_not_list(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        with pytest.raises(TypeError, match="must be a list"):
            api.set_menu("not a list")

    def test_set_menu_missing_label(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        with pytest.raises(ValueError, match="label"):
            api.set_menu([{"action": "show"}])

    def test_set_menu_missing_action(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        with pytest.raises(ValueError, match="action"):
            api.set_menu([{"label": "Show"}])


class TestTrayTrigger:

    def test_trigger_emits_event(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.trigger("my_action", {"source": "test"})
        assert result["action"] == "my_action"
        app.emit.assert_called_once()

    def test_trigger_calls_handler(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        handler_calls = []
        api.set_action_handler(lambda action, payload: handler_calls.append((action, payload)))
        api.trigger("click", None)
        assert len(handler_calls) == 1
        assert handler_calls[0][0] == "click"


class TestTrayState:

    def test_state_structure(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        state = api.state()
        assert "visible" in state
        assert "icon_path" in state
        assert "menu" in state
        assert "backend" in state
        assert state["visible"] is False

    def test_is_visible_default_false(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        assert api.is_visible() is False

    def test_show_without_backend(self):
        """Show with no pystray reports no backend available."""
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.show()
        assert result is False  # No backend available

    def test_hide_when_not_visible(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        result = api.hide()
        assert result is False

    @patch("forge.api.tray.importlib.import_module")
    @patch("threading.Thread")
    def test_show_and_hide_with_backend(self, mock_thread, mock_importlib, tmp_path):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        
        # Create a mock image file
        icon_path = tmp_path / "icon.png"
        icon_path.write_text("fake png")
        api.set_icon(str(icon_path))
        
        # Setup mocks for pystray and PIL
        mock_pystray = MagicMock()
        mock_pil = MagicMock()
        mock_pil.open.return_value = "img"
        def _mock_import(name):
            if name == "pystray":
                return mock_pystray
            if name == "PIL.Image":
                return mock_pil
            raise ImportError(name)
        mock_importlib.side_effect = _mock_import
        
        # Show tray (should initialize pystray and run thread)
        result = api.show()
        assert result is True
        assert api.is_visible() is True
        mock_pystray.Icon.assert_called_once()
        mock_thread.assert_called_once()
        
        # Check repeated show doesn't recreate
        assert api.show() is True
        assert mock_pystray.Icon.call_count == 1
        
        # Hide tray
        api._icon = mock_pystray.Icon()
        icon_mock = api._icon
        assert api.hide() is True
        assert api.is_visible() is False
        icon_mock.stop.assert_called_once()
        
        # Check hide again is False
        assert api.hide() is False

    @patch("forge.api.tray.importlib.import_module")
    def test_tray_create_handles_exception(self, mock_importlib, tmp_path):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        
        icon_path = tmp_path / "icon.png"
        icon_path.write_text("fake png")
        api.set_icon(str(icon_path))
        
        mock_pystray = MagicMock()
        # Make Icon initialization throw Exception
        mock_pystray.Icon.side_effect = Exception("X Server missing")
        def _mock_import(name):
            if name == "pystray":
                return mock_pystray
            return MagicMock() # PIL
        mock_importlib.side_effect = _mock_import
        
        # Tray attempts to launch, catches and sets backend unavailable silently
        result = api.show()
        assert api._backend_available is False
        assert result is False

    def test_tray_set_icon_missing(self):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        with pytest.raises(FileNotFoundError):
            api.set_icon("/does/not/exist/icon.png")

    @patch("forge.api.tray.importlib.import_module")
    def test_tray_dynamic_menu_update_while_visible(self, mock_importlib, tmp_path):
        from forge.api.tray import TrayAPI
        app = _make_app()
        api = TrayAPI(app)
        
        icon_path = tmp_path / "icon.png"
        icon_path.write_text("fake png")
        api.set_icon(str(icon_path))
        
        mock_pystray = MagicMock()
        def _mock_import(name):
            return mock_pystray
        mock_importlib.side_effect = _mock_import
        
        api.show()
        assert mock_pystray.Icon.call_count == 1
        
        # Updating menu while visible dynamically destroys and recreates tray
        with patch.object(api, "_destroy_tray") as mock_destroy:
            api.set_menu([{"label": "New Action", "action": "test"}])
            mock_destroy.assert_called_once()
        
        # Updating icon while visible does the same
        with patch.object(api, "_destroy_tray") as mock_destroy:
            api.set_icon(str(icon_path))
            mock_destroy.assert_called_once()

# ─── NotificationAPI Tests ───

class TestNotificationState:

    def test_state_returns_structure(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        state = api.state()
        assert "backend" in state
        assert "backend_available" in state
        assert "sent_count" in state

    def test_notify_records_history(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        api.notify("Test", "Body")
        assert len(api._history) == 1
        assert api._history[0]["title"] == "Test"

    def test_notify_empty_title_raises(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        with pytest.raises(ValueError, match="title"):
            api.notify("", "Body")

    def test_history_returns_recent(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        for i in range(5):
            api.notify(f"Title-{i}", "Body")
        hist = api.history(3)
        assert len(hist) == 3

    def test_history_zero_limit(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        api.notify("T", "B")
        all_hist = api.history(0)
        assert len(all_hist) == 1  # Returns all

    def test_history_prunes_beyond_max(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        api._max_history = 5
        for i in range(10):
            api.notify(f"Title-{i}", "Body")
        assert len(api._history) == 5

    def test_state_after_notification(self):
        from forge.api.notification import NotificationAPI
        app = _make_app()
        api = NotificationAPI(app)
        api.notify("Hello", "World")
        state = api.state()
        assert state["sent_count"] == 1
        assert state["last"]["title"] == "Hello"
