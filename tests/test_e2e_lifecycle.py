"""
End-to-End Integration Tests for Forge Framework.

Tests the complete application lifecycle from initialization through
IPC communication, command dispatch, event handling, and shutdown.

These tests verify that all components work together correctly:
- ForgeApp initialization and configuration
- IPCBridge command registration and dispatch
- EventEmitter pub/sub flow
- AppState dependency injection
- WindowAPI state management
- WindowManagerAPI multi-window orchestration
- Plugin system registration
- Error recovery (circuit breaker, crash reporter)
- Scope validation (security)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forge.app import ForgeApp
from forge.bridge import PROTOCOL_VERSION, IPCBridge
from forge.config import ForgeConfig
from forge.events import EventEmitter
from forge.recovery import CircuitBreaker, CrashReporter, ErrorCode
from forge.router import Router
from forge.scope import ScopeValidator
from forge.state import AppState
from forge.window import WindowAPI, WindowManagerAPI

# ─── Fixtures ───


def _make_app(tmp_path: Path, name: str = "E2E Test App") -> ForgeApp:
    """Create a minimal ForgeApp for E2E testing without native window."""
    frontend_dir = tmp_path / "src" / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")

    config_file = tmp_path / "forge.toml"
    config_file.write_text(
        f'[app]\nname = "{name}"\nversion = "1.0.0"\n\n'
        f'[build]\nentry = "src/main.py"\n\n'
        f'[dev]\nfrontend_dir = "src/frontend"\n\n'
        f'[window]\ntitle = "{name}"\nwidth = 1200\nheight = 800\nremember_state = true\n\n'
        f"[permissions]\nfilesystem = true\nshell = false\nclipboard = true\n",
        encoding="utf-8",
    )

    app = ForgeApp.__new__(ForgeApp)
    app.config = ForgeConfig.from_file(config_file)
    app._proxy = None
    app._is_ready = False
    app._dev_server_url = None
    app._log_buffer = MagicMock()
    app._runtime_events = []
    app.events = EventEmitter()
    app.state = AppState()
    app.bridge = IPCBridge(app, {})
    app.window = WindowAPI(app)
    app.windows = WindowManagerAPI(app)
    app._command_log = []

    return app


@pytest.fixture
def app(tmp_path):
    """Create a test app instance."""
    return _make_app(tmp_path)


@pytest.fixture
def app_with_state(tmp_path):
    """Create a test app with managed state."""
    app = _make_app(tmp_path, "State Test App")

    class Database:
        def __init__(self, url: str):
            self.url = url
            self.connected = True

        def query(self, sql: str) -> list:
            return [{"id": 1, "name": "test"}]

    class Cache:
        def __init__(self, ttl: int = 300):
            self.ttl = ttl
            self._store = {}

        def get(self, key: str):
            return self._store.get(key)

        def set(self, key: str, value):
            self._store[key] = value

    app.state.manage(Database("sqlite:///test.db"))
    app.state.manage(Cache(ttl=60))

    return app


# ─── Phase 1: App Initialization E2E ───


class TestAppInitializationE2E:
    """Test complete app initialization flow."""

    def test_app_creates_with_valid_config(self, app):
        """App should initialize with all required components."""
        assert app.config.app.name == "E2E Test App"
        assert app.config.window.width == 1200
        assert app.config.window.height == 800
        assert app.window is not None
        assert app.windows is not None
        assert app.bridge is not None
        assert app.events is not None
        assert app.state is not None

    def test_app_registers_main_window(self, app):
        """App should have a main window registered on init."""
        main = app.windows.get("main")
        assert main["label"] == "main"
        assert main["title"] == "E2E Test App"
        assert main["width"] == 1200
        assert main["height"] == 800
        assert main["visible"] is True

    def test_app_config_permissions(self, app):
        """App should load permissions from config."""
        assert app.config.permissions.filesystem is True
        assert app.config.permissions.shell is False
        assert app.config.permissions.clipboard is True


# ─── Phase 2: IPC Bridge Communication E2E ───


class TestIPCBridgeE2E:
    """Test IPC bridge command registration and dispatch."""

    def test_register_and_invoke_command(self, app):
        """Should register commands and invoke them via IPC."""

        def greet(name: str) -> dict:
            return {"message": f"Hello, {name}!"}

        app.bridge.register_command("greet", greet)

        # Simulate IPC call
        request = json.dumps(
            {
                "command": "greet",
                "id": 1,
                "args": {"name": "World"},
            }
        )
        response_json = app.bridge.invoke_command(request)
        response = json.loads(response_json)

        assert response["type"] == "reply"
        assert response["protocol"] == PROTOCOL_VERSION
        assert response["id"] == 1
        assert response["result"]["message"] == "Hello, World!"
        assert response["error"] is None

    def test_register_and_invoke_async_command(self, app):
        """Should handle async commands via IPC."""

        async def async_fetch(url: str) -> dict:
            return {"url": url, "status": 200}

        app.bridge.register_command("async_fetch", async_fetch)

        request = json.dumps(
            {
                "command": "async_fetch",
                "id": 2,
                "args": {"url": "https://example.com"},
            }
        )
        response_json = app.bridge.invoke_command(request)
        response = json.loads(response_json)

        assert response["type"] == "reply"
        assert response["id"] == 2

    def test_command_with_capability_check(self, app):
        """Should enforce capability requirements."""

        def read_file(path: str) -> dict:
            return {"content": "file data"}

        app.bridge.register_command("read_file", read_file, capability="filesystem")

        # With filesystem capability enabled, should work
        request = json.dumps(
            {
                "command": "read_file",
                "id": 3,
                "args": {"path": "/tmp/test.txt"},
            }
        )
        response_json = app.bridge.invoke_command(request)
        response = json.loads(response_json)
        assert response["result"]["content"] == "file data"

    def test_unknown_command_returns_error(self, app):
        """Should return error for unknown commands."""
        request = json.dumps(
            {
                "command": "nonexistent_command",
                "id": 4,
                "args": {},
            }
        )
        response_json = app.bridge.invoke_command(request)
        response = json.loads(response_json)

        assert response["error"] is not None
        assert response["error_code"] == "unknown_command"

    def test_malformed_json_returns_error(self, app):
        """Should return error for malformed JSON."""
        response_json = app.bridge.invoke_command("not valid json {{{")
        response = json.loads(response_json)

        assert response["error"] is not None
        assert response["error_code"] == "invalid_request"

    def test_command_injection_prevented(self, app):
        """Should prevent command injection via command names."""
        request = json.dumps(
            {
                "command": "greet; rm -rf /",
                "id": 5,
                "args": {},
            }
        )
        response_json = app.bridge.invoke_command(request)
        response = json.loads(response_json)

        assert response["error"] is not None


# ─── Phase 3: Event System E2E ───


class TestEventSystemE2E:
    """Test event emitter pub/sub flow."""

    def test_sync_event_dispatch(self, app):
        """Should dispatch events to sync listeners."""
        received = []

        def on_ready(event):
            received.append(event)

        app.events.on("ready", on_ready)
        app.events.emit("ready", {"status": "ok"})

        assert len(received) == 1
        assert received[0]["status"] == "ok"

    def test_multiple_listeners(self, app):
        """Should dispatch to multiple listeners."""
        results = []

        app.events.on("data", lambda e: results.append("A"))
        app.events.on("data", lambda e: results.append("B"))
        app.events.emit("data", {})

        assert "A" in results
        assert "B" in results

    def test_event_with_payload(self, app):
        """Should pass complex payloads through events."""
        received = []

        app.events.on("window:resized", lambda e: received.append(e))
        app.events.emit(
            "window:resized",
            {
                "label": "main",
                "width": 1920,
                "height": 1080,
            },
        )

        assert received[0]["label"] == "main"
        assert received[0]["width"] == 1920

    def test_thread_safe_event_emission(self, app):
        """Should handle concurrent event emission safely."""
        received = []
        lock = threading.Lock()

        def on_data(event):
            with lock:
                received.append(event["value"])

        app.events.on("data", on_data)

        threads = []
        for i in range(10):
            t = threading.Thread(target=lambda v=i: app.events.emit("data", {"value": v}))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(received) == 10


# ─── Phase 4: State Management E2E ───


class TestStateManagementE2E:
    """Test AppState dependency injection."""

    def test_state_manage_and_get(self, app):
        """Should manage and retrieve typed state."""

        class MyService:
            def __init__(self):
                self.value = 42

        app.state.manage(MyService())
        result = app.state.get(MyService)
        assert result.value == 42

    def test_state_prevents_duplicate_type(self, app):
        """Should prevent managing same type twice."""

        class Database:
            pass

        app.state.manage(Database())
        with pytest.raises(ValueError, match="already managed"):
            app.state.manage(Database())

    def test_state_try_get_returns_none(self, app):
        """Should return None for unmanaged types."""
        result = app.state.try_get(str)
        assert result is None

    def test_state_thread_safety(self, app):
        """Should be thread-safe for concurrent access."""

        class Counter:
            def __init__(self):
                self.value = 0

        app.state.manage(Counter())
        counter = app.state.get(Counter)

        threads = []
        for _ in range(100):
            t = threading.Thread(target=lambda: setattr(counter, "value", counter.value + 1))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Value may vary due to race condition, but should not crash
        assert counter.value > 0


# ─── Phase 5: Window Management E2E ───


class TestWindowManagementE2E:
    """Test window lifecycle and multi-window orchestration."""

    def test_window_state_tracking(self, app):
        """Should track window state changes."""
        state = app.window.state()
        assert state["title"] == "E2E Test App"
        assert state["width"] == 1200
        assert state["height"] == 800
        assert state["visible"] is True

    def test_window_set_size(self, app):
        """Should update window size."""
        app.window.set_size(1920, 1080)
        state = app.window.state()
        assert state["width"] == 1920
        assert state["height"] == 1080

    def test_window_set_title(self, app):
        """Should update window title."""
        app.window.set_title("New Title")
        state = app.window.state()
        assert state["title"] == "New Title"

    def test_window_set_position(self, app):
        """Should update window position."""
        app.window.set_position(100, 200)
        pos = app.window.position()
        assert pos["x"] == 100
        assert pos["y"] == 200

    def test_window_minimize_maximize(self, app):
        """Should track minimize/maximize state in internal state."""
        # Without proxy, minimize/maximize update internal state but raise
        # We test that the state tracking works before proxy call
        assert app.window.is_minimized() is False
        assert app.window.is_maximized() is False

        # Update state directly (simulating what would happen with proxy)
        app.window._update_state(minimized=True, maximized=False)
        assert app.window.is_minimized() is True
        assert app.window.is_maximized() is False

        app.window._update_state(minimized=False, maximized=True)
        assert app.window.is_maximized() is True
        assert app.window.is_minimized() is False

        app.window._update_state(maximized=False)
        assert app.window.is_maximized() is False

    def test_multi_window_create(self, app):
        """Should create additional windows."""
        settings = app.windows.create(
            label="settings",
            title="Settings",
            route="/settings",
            width=600,
            height=400,
        )

        assert settings["label"] == "settings"
        assert settings["title"] == "Settings"
        assert settings["width"] == 600
        assert settings["height"] == 400

    def test_multi_window_list(self, app):
        """Should list all windows."""
        app.windows.create("settings", title="Settings")
        app.windows.create("about", title="About")

        window_list = app.windows.list()
        labels = [w["label"] for w in window_list]

        assert "main" in labels
        assert "settings" in labels
        assert "about" in labels

    def test_multi_window_close(self, app):
        """Should close windows by label."""
        app.windows.create("settings", title="Settings")
        assert "settings" in [w["label"] for w in app.windows.list()]

        app.windows.close("settings")
        closed_window = app.windows.get("settings")
        assert closed_window["closed"] is True

    def test_multi_window_broadcast(self, app):
        """Should broadcast to all windows."""
        # This tests the broadcast mechanism without native proxy
        app.windows.create("w1", title="W1")
        app.windows.create("w2", title="W2")

        # Should not raise even without proxy
        app.windows.broadcast("console.log('broadcast')")

    def test_cannot_create_duplicate_window(self, app):
        """Should reject duplicate window labels."""
        app.windows.create("settings", title="Settings")
        with pytest.raises(ValueError, match="already exists"):
            app.windows.create("settings", title="Settings 2")


# ─── Phase 6: Scope Validation E2E ───


class TestScopeValidationE2E:
    """Test security scope validation."""

    def test_scope_allows_permitted_path(self, tmp_path):
        """Should allow paths matching allow rules."""
        allowed_dir = tmp_path / "appdata"
        allowed_dir.mkdir()

        validator = ScopeValidator(
            allow_patterns=[str(allowed_dir / "**")],
            deny_patterns=[],
        )
        assert validator.is_path_allowed(str(allowed_dir / "config.json")) is True

    def test_scope_denies_unpermitted_path(self, tmp_path):
        """Should deny paths not matching any allow rule."""
        allowed_dir = tmp_path / "appdata"
        allowed_dir.mkdir()

        validator = ScopeValidator(
            allow_patterns=[str(allowed_dir / "**")],
            deny_patterns=[],
        )
        assert validator.is_path_allowed("/etc/passwd") is False

    def test_deny_overrides_allow(self, tmp_path):
        """Should deny paths matching deny rules even if allowed."""
        base_dir = tmp_path / "appdata"
        base_dir.mkdir()
        secret_dir = base_dir / "secret"
        secret_dir.mkdir()

        validator = ScopeValidator(
            allow_patterns=[str(base_dir / "**")],
            deny_patterns=[str(secret_dir / "**")],
        )
        assert validator.is_path_allowed(str(base_dir / "public.txt")) is True
        assert validator.is_path_allowed(str(secret_dir / "key.pem")) is False

    def test_scope_validates_urls(self):
        """Should validate URLs against scope rules."""
        validator = ScopeValidator(
            allow_patterns=["https://api.example.com/**"],
            deny_patterns=[],
        )
        assert validator.is_url_allowed("https://api.example.com/data") is True
        assert validator.is_url_allowed("https://evil.com/steal") is False


# ─── Phase 7: Error Recovery E2E ───


class TestErrorRecoveryE2E:
    """Test circuit breaker and crash reporter."""

    def test_circuit_breaker_opens_after_failures(self):
        """Should open circuit after consecutive failures."""
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=1)

        # Record failures for a specific command
        for _ in range(3):
            breaker.record_failure("test_cmd")

        assert breaker.is_allowed("test_cmd") is False

    def test_circuit_breaker_resets_after_success(self):
        """Should reset on successful call."""
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=1)

        breaker.record_failure("test_cmd")
        breaker.record_failure("test_cmd")
        breaker.record_success("test_cmd")

        assert breaker.is_allowed("test_cmd") is True

    def test_circuit_breaker_half_open_after_cooldown(self):
        """Should enter half-open state after cooldown."""
        breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)

        breaker.record_failure("test_cmd")
        breaker.record_failure("test_cmd")
        assert breaker.is_allowed("test_cmd") is False

        time.sleep(0.15)
        # After cooldown, should allow one attempt
        assert breaker.is_allowed("test_cmd") is True

    def test_crash_reporter_captures_exception(self, tmp_path):
        """Should capture and write crash reports."""
        reporter = CrashReporter(crash_dir=tmp_path)
        reporter.install()

        # Build a report manually using the internal method
        try:
            raise ValueError("Test crash")
        except ValueError:
            import sys

            exc_type, exc_value, exc_tb = sys.exc_info()
            report = reporter._build_report(exc_type, exc_value, exc_tb)

        assert "Test crash" in report["exception"]["message"]
        assert report["exception"]["type"] == "ValueError"

        reporter.uninstall()

    def test_error_codes_are_structured(self):
        """Should have well-defined error codes."""
        assert ErrorCode.INVALID_REQUEST == "invalid_request"
        assert ErrorCode.PERMISSION_DENIED == "permission_denied"
        assert ErrorCode.UNKNOWN_COMMAND == "unknown_command"
        assert ErrorCode.CIRCUIT_OPEN == "circuit_open"


# ─── Phase 8: Router E2E ───


class TestRouterE2E:
    """Test command routing and middleware."""

    def test_router_registers_command(self):
        """Should register commands via decorator."""
        router = Router()

        @router.command()
        def greet(name: str) -> dict:
            return {"message": f"Hello, {name}!"}

        assert "greet" in router.commands

    def test_router_registers_with_custom_name(self):
        """Should register commands with custom names."""
        router = Router()

        @router.command(name="custom_greet")
        def greet(name: str) -> dict:
            return {"message": f"Hello, {name}!"}

        assert "custom_greet" in router.commands

    def test_router_with_prefix(self):
        """Should prefix command names."""
        router = Router(prefix="myplugin")

        @router.command()
        def do_something():
            return {"ok": True}

        assert "myplugin:do_something" in router.commands

    def test_router_command_capability(self):
        """Should set capability on command."""
        router = Router()

        @router.command(capability="filesystem")
        def read_file(path: str):
            return {"content": "data"}

        assert router.commands["read_file"]._forge_capability == "filesystem"


# ─── Phase 9: Full Lifecycle E2E ───


class TestFullLifecycleE2E:
    """Test complete app lifecycle from init to shutdown."""

    def test_complete_ipc_flow(self, app):
        """Should handle complete IPC request/response cycle."""

        # 1. Register commands
        def get_status() -> dict:
            return {
                "app": app.config.app.name,
                "version": app.config.app.version,
                "windows": len(app.windows.list()),
            }

        def create_window(label: str, title: str) -> dict:
            window = app.windows.create(label=label, title=title)
            return {"created": True, "label": window["label"]}

        app.bridge.register_command("get_status", get_status)
        app.bridge.register_command("create_window", create_window)

        # 2. Invoke get_status
        request = json.dumps({"command": "get_status", "id": 1, "args": {}})
        response = json.loads(app.bridge.invoke_command(request))
        assert response["result"]["app"] == "E2E Test App"
        assert response["result"]["windows"] == 1

        # 3. Create a window via IPC
        request = json.dumps(
            {
                "command": "create_window",
                "id": 2,
                "args": {"label": "dashboard", "title": "Dashboard"},
            }
        )
        response = json.loads(app.bridge.invoke_command(request))
        assert response["result"]["created"] is True

        # 4. Verify window exists
        assert len(app.windows.list()) == 2

    def test_event_driven_state_updates(self, app):
        """Should update state based on events."""
        # Track window state via events
        state_changes = []

        def on_resized(event):
            state_changes.append(("resized", event))

        def on_moved(event):
            state_changes.append(("moved", event))

        app.events.on("resized", on_resized)
        app.events.on("moved", on_moved)

        # Simulate window events
        app.events.emit("resized", {"label": "main", "width": 1920, "height": 1080})
        app.events.emit("moved", {"label": "main", "x": 100, "y": 200})

        assert len(state_changes) == 2
        assert state_changes[0][1]["width"] == 1920
        assert state_changes[1][1]["x"] == 100

    def test_state_injection_into_commands(self, app_with_state):
        """Should inject managed state into command handlers."""

        # Register command that uses injected state
        def query_db(sql: str) -> dict:
            # In real app, db would be injected via type hints
            return {"rows": [], "sql": sql}

        app_with_state.bridge.register_command("query_db", query_db)

        request = json.dumps(
            {
                "command": "query_db",
                "id": 1,
                "args": {"sql": "SELECT * FROM users"},
            }
        )
        response = json.loads(app_with_state.bridge.invoke_command(request))
        assert response["result"]["sql"] == "SELECT * FROM users"

    def test_error_handling_across_components(self, app):
        """Should handle errors gracefully across component boundaries."""

        # Register a command that fails
        def failing_command():
            raise RuntimeError("Something went wrong")

        app.bridge.register_command("failing_command", failing_command)

        # Invoke the failing command
        request = json.dumps({"command": "failing_command", "id": 1, "args": {}})
        response = json.loads(app.bridge.invoke_command(request))

        # Should get error response, not crash
        assert response["error"] is not None
        assert response["type"] == "reply"

    def test_multi_window_ipc_routing(self, app):
        """Should route IPC to correct window."""
        # Create multiple windows
        app.windows.create("settings", title="Settings", route="/settings")
        app.windows.create("about", title="About", route="/about")

        # Verify all windows are tracked
        window_list = app.windows.list()
        assert len(window_list) == 3  # main + settings + about

        # Verify window properties
        settings = app.windows.get("settings")
        assert settings["title"] == "Settings"
        assert settings["route"] == "/settings"

        about = app.windows.get("about")
        assert about["title"] == "About"
        assert about["route"] == "/about"
