"""
Tests for Forge Window State Persistence (Phase 12).

Tests the enhanced WindowStateAPI with:
- remember_state config flag
- Maximized/fullscreen state tracking
- Monitor bounds validation
- clear() and snapshot() methods
- Debounced save lifecycle
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge.api.window_state import WindowStateAPI


@pytest.fixture
def mock_app(tmp_path):
    """Create a mock app with filesystem expansion pointing to tmp_path."""
    app = MagicMock()
    app.config.app.name = "forge-test"
    app.config.window.remember_state = True

    # Mock Forge FS expansion so data goes to tmp_path
    import forge.api.fs
    original_expand = forge.api.fs._expand_path_var

    def fake_expand(path):
        if path == "$APPDATA":
            return tmp_path
        return original_expand(path)

    forge.api.fs._expand_path_var = fake_expand

    # Simple event bus mock
    app.events = MagicMock()

    yield app

    forge.api.fs._expand_path_var = original_expand


@pytest.fixture
def disabled_app(tmp_path):
    """Create a mock app with remember_state = False."""
    app = MagicMock()
    app.config.app.name = "forge-disabled"
    app.config.window.remember_state = False

    import forge.api.fs
    original_expand = forge.api.fs._expand_path_var

    def fake_expand(path):
        if path == "$APPDATA":
            return tmp_path
        return original_expand(path)

    forge.api.fs._expand_path_var = fake_expand
    app.events = MagicMock()

    yield app

    forge.api.fs._expand_path_var = original_expand


# ─── Initialization Tests ───

class TestWindowStateInit:

    def test_initialization_hooks_bound(self, mock_app):
        api = WindowStateAPI(mock_app)
        assert "forge-test" in str(api._state_file)
        assert api._state_file.name == "window_state.json"
        mock_app.events.on.assert_any_call("resized", api._on_resized)
        mock_app.events.on.assert_any_call("moved", api._on_moved)
        mock_app.events.on.assert_any_call("ready", api._on_ready)

    def test_disabled_skips_hooks(self, disabled_app):
        api = WindowStateAPI(disabled_app)
        assert api._enabled is False
        assert api._cache == {}
        disabled_app.events.on.assert_not_called()

    def test_enabled_flag_defaults_true(self, mock_app):
        api = WindowStateAPI(mock_app)
        assert api._enabled is True


# ─── Caching & Debounce Tests ───

class TestWindowStateCaching:

    def test_resize_updates_cache(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        state = api.get_state("main")
        assert state["width"] == 800
        assert state["height"] == 600

    def test_move_updates_cache(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_moved({"label": "main", "x": 100, "y": 200})
        state = api.get_state("main")
        assert state["x"] == 100
        assert state["y"] == 200

    def test_debounced_save_not_immediate(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        assert not api._state_file.exists()

    def test_shutdown_flushes_to_disk(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        api._on_moved({"label": "main", "x": 100, "y": 200})
        mock_app.window.is_maximized.return_value = False
        api._on_shutdown()

        assert api._state_file.exists()
        with open(api._state_file) as f:
            saved = json.load(f)
        assert saved["main"]["width"] == 800
        assert saved["main"]["x"] == 100

    def test_invalid_size_not_cached(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": -50, "height": 0})
        state = api.get_state("main")
        assert "width" not in state
        assert "height" not in state


# ─── Maximized State Tracking ───

class TestMaximizedState:

    def test_shutdown_captures_maximized(self, mock_app):
        """On shutdown, the current maximized state should be saved."""
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})

        # Simulate window being maximized
        mock_app.window.is_maximized.return_value = True
        api._on_shutdown()

        assert api._state_file.exists()
        with open(api._state_file) as f:
            saved = json.load(f)
        assert saved["main"]["maximized"] is True

    def test_shutdown_captures_not_maximized(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})

        mock_app.window.is_maximized.return_value = False
        api._on_shutdown()

        with open(api._state_file) as f:
            saved = json.load(f)
        assert saved["main"]["maximized"] is False

    def test_ready_restores_maximized(self, mock_app):
        """On ready, if saved state has maximized=True, window should be maximized."""
        api = WindowStateAPI(mock_app)
        api._cache = {"main": {"maximized": True, "x": 100, "y": 100}}
        api._on_ready({})

        mock_app.window.maximize.assert_called_once()

    def test_ready_does_not_maximize_when_false(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._cache = {"main": {"maximized": False, "x": 100, "y": 100}}
        api._on_ready({})

        mock_app.window.maximize.assert_not_called()


# ─── Hydration Tests ───

class TestHydration:

    def test_hydrate_main_config(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._cache = {"main": {"width": 1024, "height": 768}}
        api._hydrate_main_config()
        assert mock_app.config.window.width == 1024
        assert mock_app.config.window.height == 768

    def test_hydrate_descriptor(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._cache = {"secondary": {"width": 1024, "height": 768, "x": 50, "y": 50}}

        descriptor = {"label": "secondary", "url": "index.html"}
        api.try_hydrate_descriptor(descriptor)

        assert descriptor["width"] == 1024
        assert descriptor["x"] == 50.0

    def test_hydrate_descriptor_disabled(self, disabled_app):
        api = WindowStateAPI(disabled_app)
        descriptor = {"label": "secondary", "url": "index.html", "width": 500}
        api.try_hydrate_descriptor(descriptor)
        assert descriptor["width"] == 500  # Unchanged


# ─── Monitor Bounds Validation ───

class TestMonitorBounds:

    def test_position_within_bounds(self, mock_app):
        api = WindowStateAPI(mock_app)
        assert api._is_position_on_screen(100, 200)
        assert api._is_position_on_screen(0, 0)
        assert api._is_position_on_screen(1920, 1080)

    def test_position_extreme_negative_rejected(self, mock_app):
        api = WindowStateAPI(mock_app)
        assert not api._is_position_on_screen(-30000, 100)
        assert not api._is_position_on_screen(100, -30000)

    def test_position_extreme_positive_rejected(self, mock_app):
        api = WindowStateAPI(mock_app)
        assert not api._is_position_on_screen(30000, 100)
        assert not api._is_position_on_screen(100, 30000)

    def test_ready_skips_off_screen_position(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._cache = {"main": {"x": -30000, "y": 100}}
        api._on_ready({})
        mock_app.window.set_position.assert_not_called()

    def test_ready_applies_on_screen_position(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._cache = {"main": {"x": 200, "y": 300}}
        api._on_ready({})
        mock_app.window.set_position.assert_called_once_with(200, 300)


# ─── Clear & Snapshot ───

class TestClearAndSnapshot:

    def test_clear_all(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        api._on_resized({"label": "secondary", "width": 400, "height": 300})
        api.clear()
        assert api.get_state("main") == {}
        assert api.get_state("secondary") == {}

    def test_clear_specific_label(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        api._on_resized({"label": "secondary", "width": 400, "height": 300})
        api.clear("secondary")
        assert api.get_state("main")["width"] == 800
        assert api.get_state("secondary") == {}

    def test_snapshot_returns_copy(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_resized({"label": "main", "width": 800, "height": 600})
        snap = api.snapshot()
        assert snap["main"]["width"] == 800

        # Mutating snapshot shouldn't affect internal state
        snap["main"]["width"] = 9999
        assert api.get_state("main")["width"] == 800


# ─── State Reload ───

class TestStateReload:

    def test_load_from_existing_file(self, mock_app, tmp_path):
        """State should be loaded from disk on initialization."""
        data_dir = tmp_path / "forge-test"
        data_dir.mkdir(exist_ok=True)
        state_file = data_dir / "window_state.json"
        state_file.write_text(json.dumps({
            "main": {"width": 1920, "height": 1080, "x": 50, "y": 50, "maximized": True}
        }))

        api = WindowStateAPI(mock_app)
        state = api.get_state("main")
        assert state["width"] == 1920
        assert state["maximized"] is True

    def test_load_corrupt_file_starts_fresh(self, mock_app, tmp_path):
        """Corrupt state file should not crash, just start empty."""
        data_dir = tmp_path / "forge-test"
        data_dir.mkdir(exist_ok=True)
        state_file = data_dir / "window_state.json"
        state_file.write_text("NOT VALID JSON {{{")

        api = WindowStateAPI(mock_app)
        assert api.get_state("main") == {}


# ─── on_ready Registration ───

class TestOnReady:

    def test_shutdown_hook_registered(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_ready({})
        mock_app.on_close.assert_called_with(api._on_shutdown)

    def test_shutdown_hook_registered_only_once(self, mock_app):
        api = WindowStateAPI(mock_app)
        api._on_ready({})
        api._on_ready({})
        assert mock_app.on_close.call_count == 1


# ─── Config Parsing ───

class TestRememberStateConfig:

    def test_remember_state_parsed_true(self, tmp_path):
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[window]
remember_state = true
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        assert config.window.remember_state is True

    def test_remember_state_parsed_false(self, tmp_path):
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[window]
remember_state = false
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        assert config.window.remember_state is False

    def test_remember_state_defaults_true(self, tmp_path):
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[window]
width = 800
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        assert config.window.remember_state is True
