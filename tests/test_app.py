"""
Tests for ForgeApp public API behavior.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from forge.api.updater import canonical_manifest_bytes
from forge.app import ForgeApp


def _write_config(tmp_path: Path, permissions: str = "") -> Path:
    frontend_dir = tmp_path / "src" / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    config_file = tmp_path / "forge.toml"
    config_file.write_text(
        "\n".join(
            [
                "[app]",
                'name = "Test App"',
                "",
                "[build]",
                'entry = "src/main.py"',
                "",
                "[dev]",
                'frontend_dir = "src/frontend"',
                "",
                permissions,
            ]
        ),
        encoding="utf-8",
    )
    return config_file


class TestForgeApp:
    """Tests for ForgeApp public application surface."""

    class _FakeWindowProxy:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...]]] = []

        def evaluate_script(self, label: str, script: str) -> None:
            self.calls.append(("evaluate_script", (label, script)))

        def load_url(self, label: str, url: str) -> None:
            self.calls.append(("load_url", (label, url)))

        def reload(self) -> None:
            self.calls.append(("reload", ()))

        def go_back(self) -> None:
            self.calls.append(("go_back", ()))

        def go_forward(self) -> None:
            self.calls.append(("go_forward", ()))

        def open_devtools(self) -> None:
            self.calls.append(("open_devtools", ()))

        def close_devtools(self) -> None:
            self.calls.append(("close_devtools", ()))

        def set_title(self, title: str) -> None:
            self.calls.append(("set_title", (title,)))

        def set_size(self, width: float, height: float) -> None:
            self.calls.append(("set_size", (width, height)))

        def set_position(self, x: float, y: float) -> None:
            self.calls.append(("set_position", (x, y)))

        def set_fullscreen(self, enabled: bool) -> None:
            self.calls.append(("set_fullscreen", (enabled,)))

        def set_always_on_top(self, enabled: bool) -> None:
            self.calls.append(("set_always_on_top", (enabled,)))

        def set_vibrancy(self, label: str, vibrancy: str | None) -> None:
            self.calls.append(("set_vibrancy", (label, vibrancy)))

        def set_visible(self, visible: bool) -> None:
            self.calls.append(("set_visible", (visible,)))

        def focus(self) -> None:
            self.calls.append(("focus", ()))

        def set_minimized(self, minimized: bool) -> None:
            self.calls.append(("set_minimized", (minimized,)))

        def set_maximized(self, maximized: bool) -> None:
            self.calls.append(("set_maximized", (maximized,)))

        def set_menu(self, menu_json: str) -> None:
            self.calls.append(("set_menu", (menu_json,)))

        def create_window(self, descriptor_json: str) -> None:
            self.calls.append(("create_window", (descriptor_json,)))

        def close_window_label(self, label: str) -> None:
            self.calls.append(("close_window_label", (label,)))

        def close(self) -> None:
            self.calls.append(("close", ()))

    def test_app_command_decorator_registers_without_parentheses(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        @app.command
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "greet", "args": {"name": "Forge"}, "id": 1})
            )
        )

        assert response["error"] is None
        assert response["result"] == "Hello, Forge!"

    def test_security_policy_denies_non_allowlisted_command(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="[security]\nallowed_commands = [\"greet\"]\n",
        )
        app = ForgeApp(str(config_path))

        @app.command
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        @app.command
        def echo(value: str) -> str:
            return value

        allowed = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "greet", "args": {"name": "Forge"}, "id": 200})
            )
        )
        denied = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "echo", "args": {"value": "blocked"}, "id": 201})
            )
        )

        assert allowed["error"] is None
        assert denied["error"] == "Command not allowed by security policy: 'echo'"

    def test_security_policy_hides_command_introspection(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="[security]\nexpose_command_introspection = false\n",
        )
        app = ForgeApp(str(config_path))

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_describe_commands", "args": {}, "id": 202})
            )
        )

        assert response["error"] == "Command not allowed by security policy: '__forge_describe_commands'"

    def test_security_policy_denies_untrusted_origin(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions='[security]\nallowed_origins = ["https://app.example.com"]\n',
        )
        app = ForgeApp(str(config_path))

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "version",
                        "args": {},
                        "id": 2021,
                        "meta": {"origin": "https://evil.example.com"},
                    }
                )
            )
        )

        assert response["result"] is None
        assert "Origin not allowed" in response["error"]

    def test_security_policy_denies_window_scoped_capability(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "clipboard = true",
                    "",
                    "[security.window_scopes]",
                    'main = ["filesystem"]',
                    'settings = ["clipboard"]',
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        @app.command(capability="clipboard")
        def clipboard_secret() -> str:
            return "secret"

        denied = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "clipboard_secret",
                        "args": {},
                        "id": 2022,
                        "meta": {"window_label": "main"},
                    }
                )
            )
        )
        allowed = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "clipboard_secret",
                        "args": {},
                        "id": 2023,
                        "meta": {"window_label": "settings"},
                    }
                )
            )
        )

        assert denied["result"] is None
        assert "Window scope denied" in denied["error"]
        assert allowed["error"] is None
        assert allowed["result"] == "secret"

    def test_plugin_module_registers_command_and_runtime_metadata(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "demo_plugin.py").write_text(
            "\n".join(
                [
                    'manifest = {"name": "demo-plugin", "version": "0.1.0"}',
                    '',
                    'def register(app):',
                    '    @app.command("plugin_hello")',
                    '    def plugin_hello(name: str = "Forge") -> str:',
                    '        return f"Plugin says hi to {name}"',
                ]
            ),
            encoding="utf-8",
        )
        config_path = _write_config(
            tmp_path,
            permissions='[plugins]\nenabled = true\npaths = ["plugins"]\n',
        )

        app = ForgeApp(str(config_path))

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "plugin_hello", "args": {"name": "Forge"}, "id": 203})
            )
        )
        plugins = app.runtime.diagnostics(include_logs=False)["plugins"]

        assert response["error"] is None
        assert response["result"] == "Plugin says hi to Forge"
        assert plugins["loaded"] == 1
        assert plugins["plugins"][0]["name"] == "demo-plugin"

    def test_app_command_decorator_registers_custom_name(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        @app.command("say_hi")
        def greet(name: str) -> str:
            return f"Hi, {name}!"

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "say_hi", "args": {"name": "Forge"}, "id": 2})
            )
        )

        assert response["error"] is None
        assert response["result"] == "Hi, Forge!"

    def test_built_in_apis_are_exposed_on_app_instance(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        assert app.fs is not None
        assert app.system is not None
        assert app.menu is not None
        assert app.dialog is not None
        assert app.clipboard is not None
        assert app.runtime is not None

        response = json.loads(app.bridge.invoke_command(json.dumps({"command": "version", "args": {}, "id": 4})))
        assert response["error"] is None
        assert response["result"] == "1.0.0"

        response = json.loads(app.bridge.invoke_command(json.dumps({"command": "list", "args": {"path": "."}, "id": 5})))
        assert response["error"] is None
        assert isinstance(response["result"], list)

        response = json.loads(app.bridge.invoke_command(json.dumps({"command": "open", "args": {}, "id": 6})))
        assert response["error"] is None
        assert response["result"]["action"] == "open_file"

        response = json.loads(app.bridge.invoke_command(json.dumps({"command": "clipboard_read", "args": {}, "id": 7})))
        assert response["error"] is None
        assert response["result"]["action"] == "clipboard_read"

    def test_menu_api_manages_menu_state_and_emits_events(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        received: list[tuple[str, object]] = []

        app.events.on("menu:changed", lambda payload: received.append(("changed", payload)))
        app.events.on("menu:select", lambda payload: received.append(("select", payload)))

        menu = app.menu.set(
            [
                {
                    "id": "file",
                    "label": "File",
                    "submenu": [
                        {"id": "file.open", "label": "Open", "enabled": True},
                        {"id": "file.pin", "label": "Pin", "checked": False},
                    ],
                }
            ]
        )
        disabled = app.menu.disable("file.open")
        checked = app.menu.check("file.pin")
        triggered = app.menu.trigger("file.open", {"source": "test"})

        assert menu[0]["submenu"][0]["id"] == "file.open"
        assert disabled["enabled"] is False
        assert checked["checked"] is True
        assert triggered == {
            "id": "file.open",
            "label": "Open",
            "role": None,
            "payload": {"source": "test"},
        }
        assert received[-1] == ("select", triggered)

        response = json.loads(
            app.bridge.invoke_command(json.dumps({"command": "menu_get", "args": {}, "id": 52}))
        )
        assert response["error"] is None
        assert response["result"][0]["submenu"][1]["checked"] is True

    def test_menu_api_rejects_duplicate_item_ids(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        try:
            app.menu.set(
                [
                    {"id": "dup", "label": "One"},
                    {"id": "dup", "label": "Two"},
                ]
            )
        except ValueError as exc:
            assert "Duplicate menu item id" in str(exc)
        else:
            raise AssertionError("Expected ValueError for duplicate menu item ids")

    def test_menu_changes_sync_to_native_proxy(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)
        app.menu.set(
            [
                {
                    "id": "file",
                    "label": "File",
                    "submenu": [
                        {"id": "file.open", "label": "Open"},
                        {"id": "file.pin", "label": "Pin", "type": "checkbox", "checked": True},
                    ],
                }
            ]
        )

        menu_calls = [args[0] for name, args in proxy.calls if name == "set_menu"]
        assert menu_calls
        native_menu = json.loads(menu_calls[-1])
        assert native_menu[0]["submenu"][1]["checkable"] is True
        assert native_menu[0]["submenu"][1]["checked"] is True

    def test_native_menu_selection_updates_state_and_emits_menu_event(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        received: list[dict[str, object]] = []

        app.events.on("menu:select", lambda payload: received.append(payload))
        app.menu.set(
            [
                {
                    "id": "file",
                    "label": "File",
                    "submenu": [
                        {"id": "file.pin", "label": "Pin", "type": "checkbox", "checked": False}
                    ],
                }
            ]
        )

        app._on_window_event(
            "menu_selected",
            json.dumps({"id": "file.pin", "label": "Pin", "checked": True}),
        )

        item = app.menu.get()[0]["submenu"][0]
        assert item["checked"] is True
        assert received[-1]["id"] == "file.pin"
        assert received[-1]["checked"] is True

    def test_tray_api_tracks_state_and_emits_events(self, tmp_path: Path, monkeypatch) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "system_tray = true",
                ]
            ),
        )
        app = ForgeApp(str(config_path))
        icon_path = tmp_path / "tray.png"
        icon_path.write_bytes(b"fake-icon")
        received: list[dict[str, object]] = []

        app.events.on("tray:select", lambda payload: received.append(payload))

        def fake_create_tray() -> None:
            app.tray._backend_name = "fake"
            app.tray._backend_available = True
            app.tray._icon = object()

        monkeypatch.setattr(app.tray, "_create_tray", fake_create_tray)
        monkeypatch.setattr(app.tray, "_destroy_tray", lambda: None)

        assert app.tray.set_icon(str(icon_path)) == str(icon_path)
        menu = app.tray.set_menu(
            [
                {"label": "Open", "action": "open"},
                {"separator": True},
                {"label": "Pin", "action": "pin", "checkable": True, "checked": True},
            ]
        )
        shown = app.tray.show()
        triggered = app.tray.trigger("open", {"source": "test"})
        hidden = app.tray.hide()

        assert menu[2]["checkable"] is True
        assert shown is True
        assert hidden is True
        assert triggered == {"action": "open", "payload": {"source": "test"}}
        assert received[-1] == triggered

        diagnostics = app.runtime.diagnostics(include_logs=False)
        assert diagnostics["tray"]["backend"] == "fake"
        assert diagnostics["tray"]["visible"] is False

    def test_tray_bridge_commands_return_state(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "system_tray = true",
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "tray_set_menu",
                        "args": {"items": [{"label": "Open", "action": "open"}]},
                        "id": 61,
                    }
                )
            )
        )
        assert response["error"] is None
        assert response["result"][0]["action"] == "open"

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "tray_trigger",
                        "args": {"action": "open", "payload": {"source": "bridge"}},
                        "id": 62,
                    }
                )
            )
        )
        assert response["error"] is None
        assert response["result"] == {"action": "open", "payload": {"source": "bridge"}}

        response = json.loads(
            app.bridge.invoke_command(json.dumps({"command": "tray_state", "args": {}, "id": 63}))
        )
        assert response["error"] is None
        assert response["result"]["menu"][0]["label"] == "Open"

    def test_notification_api_records_delivery_and_emits_event(self, tmp_path: Path, monkeypatch) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        received: list[dict[str, object]] = []

        app.events.on("notification:sent", lambda payload: received.append(payload))
        monkeypatch.setattr(
            app.notifications,
            "_resolve_backend",
            lambda: ("notify-send", "/usr/bin/notify-send"),
        )
        monkeypatch.setattr("forge.api.notification.subprocess.run", lambda *args, **kwargs: None)

        result = app.notifications.notify("Build complete", "Artifacts are ready")

        assert result["delivered"] is True
        assert result["backend"] == "notify-send"
        assert app.notifications.state()["sent_count"] == 1
        assert received[-1]["title"] == "Build complete"

    def test_deep_link_api_dispatches_and_tracks_state(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        config_path.write_text(
            config_path.read_text(encoding="utf-8") + "\n[protocol]\nschemes = [\"forge\"]\n",
            encoding="utf-8",
        )
        app = ForgeApp(str(config_path))
        received: list[dict[str, object]] = []

        app.events.on("deep-link", lambda payload: received.append(payload))

        result = app.deep_links.open("forge://notes/open?id=123")

        assert result["scheme"] == "forge"
        assert result["host"] == "notes"
        assert app.deep_links.protocols()["schemes"] == ["forge"]
        assert app.deep_links.state()["last_url"] == "forge://notes/open?id=123"
        assert received[-1]["url"] == "forge://notes/open?id=123"

    def test_disabled_api_raises_permission_error(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "filesystem = false",
                    "clipboard = false",
                    "dialogs = false",
                    "system_tray = false",
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        try:
            app.fs.read("notes.txt")
        except PermissionError as exc:
            assert "filesystem" in str(exc)
        else:
            raise AssertionError("Expected PermissionError for disabled filesystem API")

        response = json.loads(
            app.bridge.invoke_command(json.dumps({"command": "read", "args": {"path": "x"}, "id": 3}))
        )
        assert response["error"] is not None
        assert "Unknown command" in response["error"]

    def test_custom_capability_gated_command_is_denied_when_permission_disabled(
        self, tmp_path: Path
    ) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "filesystem = true",
                    "clipboard = false",
                    "dialogs = true",
                    "system_tray = false",
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        @app.command(capability="clipboard")
        def clipboard_secret() -> str:
            return "secret"

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "clipboard_secret", "args": {}, "id": 8})
            )
        )

        assert response["result"] is None
        assert "Permission denied" in response["error"]
        assert "clipboard" in response["error"]

    def test_internal_introspection_commands_are_available(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        describe = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_describe_commands", "args": {}, "id": 9})
            )
        )
        assert describe["error"] is None
        assert describe["result"]["protocol"] == "1.0"
        assert any(item["name"] == "version" for item in describe["result"]["commands"])

        protocol = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_protocol_info", "args": {}, "id": 10})
            )
        )
        assert protocol["error"] is None
        assert protocol["result"]["current"] == "1.0"

        command_names = {item["name"] for item in describe["result"]["commands"]}
        assert "__forge_window_set_title" in command_names
        assert "__forge_window_close" in command_names
        assert "__forge_runtime_diagnostics" in command_names
        assert "__forge_runtime_health" in command_names
        assert "__forge_runtime_navigate" in command_names
        assert "__forge_runtime_export_support_bundle" in command_names

    def test_runtime_api_reports_health_and_diagnostics(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        health = app.runtime.health()
        diagnostics = app.runtime.diagnostics()

        assert health["ok"] is True
        assert health["window_ready"] is False
        assert health["frontend_exists"] is True
        assert health["command_count"] >= 1
        assert diagnostics["app"] == {"name": "Test App", "version": "1.0.0"}
        assert diagnostics["protocol"]["current"] == "1.0"
        assert diagnostics["permissions"]["filesystem"] is True
        assert diagnostics["permissions"]["updater"] is False
        assert diagnostics["window"]["title"] == "Forge App"
        assert any(item["name"] == "__forge_runtime_health" for item in diagnostics["commands"])
        assert isinstance(diagnostics["logs"], list)
        assert diagnostics["runtime"]["state"]["url"] == "forge://app/index.html"
        assert diagnostics["crash"] is None
        assert diagnostics["config"]["app"]["name"] == "Test App"
        assert diagnostics["config"]["updater"]["enabled"] is False
        assert diagnostics["updater"]["configured"] is False

    def test_internal_runtime_ipc_commands_are_available(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        health = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_health", "args": {}, "id": 29})
            )
        )
        diagnostics = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_diagnostics", "args": {}, "id": 30})
            )
        )
        commands = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_commands", "args": {}, "id": 31})
            )
        )
        protocol = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_protocol", "args": {}, "id": 32})
            )
        )
        state = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_get_state", "args": {}, "id": 33})
            )
        )
        logs = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_logs", "args": {"limit": 5}, "id": 34})
            )
        )
        last_crash = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_runtime_last_crash", "args": {}, "id": 42})
            )
        )

        assert health["error"] is None
        assert health["result"]["ok"] is True
        assert diagnostics["error"] is None
        assert diagnostics["result"]["app"]["name"] == "Test App"
        assert commands["error"] is None
        assert any(item["name"] == "__forge_runtime_diagnostics" for item in commands["result"])
        assert protocol["error"] is None
        assert protocol["result"]["current"] == "1.0"
        assert state["error"] is None
        assert state["result"]["url"] == "forge://app/index.html"
        assert logs["error"] is None
        assert isinstance(logs["result"], list)
        assert last_crash["error"] is None
        assert last_crash["result"] is None

    def test_runtime_captures_last_crash_snapshot(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            app._record_crash(type(exc), exc, exc.__traceback__, thread_name="test-thread", fatal=True)

        last_crash = app.runtime.last_crash()
        diagnostics = app.runtime.diagnostics()

        assert last_crash is not None
        assert last_crash["type"] == "RuntimeError"
        assert last_crash["message"] == "boom"
        assert last_crash["thread"] == "test-thread"
        assert last_crash["fatal"] is True
        assert "RuntimeError: boom" in last_crash["traceback"]
        assert diagnostics["crash"]["message"] == "boom"
        assert diagnostics["health"]["last_crash"] is True

    def test_runtime_controls_drive_native_proxy_and_state(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)

        app.runtime.navigate("https://example.com")
        app.runtime.reload()
        app.runtime.go_back()
        app.runtime.go_forward()
        app.runtime.open_devtools()
        toggled = app.runtime.toggle_devtools()

        assert toggled is False
        assert app.runtime.state() == {
            "url": "https://example.com",
            "devtools_open": False,
        }
        assert [call for call in proxy.calls if call[0] != "evaluate_script"][:6] == [
            ("load_url", ("main", "https://example.com")),
            ("reload", ()),
            ("go_back", ()),
            ("go_forward", ()),
            ("open_devtools", ()),
            ("close_devtools", ()),
        ]

    def test_window_ready_navigates_to_configured_dev_server(self, tmp_path: Path, monkeypatch) -> None:
        config_path = _write_config(tmp_path)
        monkeypatch.setenv("FORGE_DEV_SERVER_URL", "http://127.0.0.1:4173")
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)

        assert ("load_url", ("main", "http://127.0.0.1:4173")) in proxy.calls
        assert app.runtime.state()["url"] == "http://127.0.0.1:4173"

    def test_runtime_control_ipc_commands_and_support_bundle_export(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()
        app._on_window_ready(proxy)

        bundle_path = tmp_path / "artifacts" / "bundle.zip"
        for payload in [
            {"command": "__forge_runtime_navigate", "args": {"url": "https://forge.dev"}, "id": 35},
            {"command": "__forge_runtime_reload", "args": {}, "id": 36},
            {"command": "__forge_runtime_go_back", "args": {}, "id": 37},
            {"command": "__forge_runtime_go_forward", "args": {}, "id": 38},
            {"command": "__forge_runtime_open_devtools", "args": {}, "id": 39},
            {"command": "__forge_runtime_close_devtools", "args": {}, "id": 40},
        ]:
            response = json.loads(app.bridge.invoke_command(json.dumps(payload)))
            assert response["error"] is None
            assert response["result"] is True

        exported = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "__forge_runtime_export_support_bundle",
                        "args": {"destination": str(bundle_path)},
                        "id": 41,
                    }
                )
            )
        )

        assert exported["error"] is None
        assert Path(exported["result"]).exists()
        with zipfile.ZipFile(exported["result"], "r") as archive:
            payload = json.loads(archive.read("diagnostics.json").decode("utf-8"))
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            logs = json.loads(archive.read("logs.json").decode("utf-8"))
            config = json.loads(archive.read("config.json").decode("utf-8"))
            registry = json.loads(archive.read("command-registry.json").decode("utf-8"))

        assert payload["diagnostics"]["runtime"]["state"]["url"] == "https://forge.dev"
        assert isinstance(payload["diagnostics"]["logs"], list)
        assert manifest["app"]["name"] == "Test App"
        assert manifest["has_crash"] is False
        assert isinstance(logs, list)
        assert config["app"]["name"] == "Test App"
        assert any(item["name"] == "__forge_runtime_export_support_bundle" for item in registry)

    def test_support_bundle_includes_crash_snapshot_when_present(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        try:
            raise ValueError("support-bundle-crash")
        except ValueError as exc:
            app._record_crash(type(exc), exc, exc.__traceback__, thread_name="bundle-thread", fatal=False)

        bundle_path = Path(app.runtime.export_support_bundle(tmp_path / "crash-bundle.zip"))
        with zipfile.ZipFile(bundle_path, "r") as archive:
            crash_payload = json.loads(archive.read("crash.json").decode("utf-8"))

        assert crash_payload["type"] == "ValueError"
        assert crash_payload["message"] == "support-bundle-crash"
        assert crash_payload["fatal"] is False

    def test_updater_api_registers_and_checks_local_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "release-manifest.json"
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "updater = true",
                    "",
                    "[updater]",
                    "enabled = true",
                    'endpoint = "https://updates.example.com/manifest.json"',
                    'channel = "beta"',
                    "check_on_startup = true",
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        manifest = app.updater.generate_manifest(
            version="1.2.0",
            url="https://downloads.example.com/test-app-1.2.0.tar.gz",
            destination=str(manifest_path),
            channel="beta",
            checksum="sha256:abc123",
            notes="Bug fixes",
        )
        check = app.updater.check(str(manifest_path))
        config_response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "updater_config", "args": {}, "id": 43})
            )
        )

        assert manifest_path.exists()
        assert manifest["release"]["version"] == "1.2.0"
        assert check["update_available"] is True
        assert check["channel"] == "beta"
        assert check["artifact"]["checksum"] == "sha256:abc123"
        assert config_response["error"] is None
        assert config_response["result"] == {
            "enabled": True,
            "endpoint": "https://updates.example.com/manifest.json",
            "channel": "beta",
            "check_on_startup": True,
            "allow_downgrade": False,
            "public_key": None,
            "require_signature": True,
            "staging_dir": ".forge-updater",
            "install_dir": None,
        }
        assert app.runtime.config_snapshot()["updater"]["channel"] == "beta"
        assert app.runtime.diagnostics()["updater"]["configured"] is True

    def test_updater_verify_download_and_apply_signed_archive(self, tmp_path: Path) -> None:
        install_dir = tmp_path / "installed-app"
        install_dir.mkdir()
        (install_dir / "app.txt").write_text("old version", encoding="utf-8")

        payload_dir = tmp_path / "payload" / "release"
        payload_dir.mkdir(parents=True)
        (payload_dir / "app.txt").write_text("new version", encoding="utf-8")
        (payload_dir / "notes.txt").write_text("release notes", encoding="utf-8")

        archive_path = tmp_path / "release.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(payload_dir / "app.txt", arcname="release/app.txt")
            archive.write(payload_dir / "notes.txt", arcname="release/notes.txt")

        checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        private_key = Ed25519PrivateKey.generate()
        public_key = base64.b64encode(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("utf-8")

        manifest_path = tmp_path / "signed-manifest.json"
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[permissions]",
                    "updater = true",
                    "",
                    "[updater]",
                    "enabled = true",
                    f'endpoint = "{manifest_path.as_posix()}"',
                    f'public_key = "{public_key}"',
                    'channel = "stable"',
                    "require_signature = true",
                    'staging_dir = ".forge-updater-state"',
                    f'install_dir = "{install_dir.as_posix()}"',
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        manifest = app.updater.generate_manifest(
            version="1.2.0",
            url=str(archive_path),
            destination=str(manifest_path),
            checksum=f"sha256:{checksum}",
            notes="Signed update",
        )
        manifest["release"]["signature"] = base64.b64encode(
            private_key.sign(canonical_manifest_bytes(manifest))
        ).decode("utf-8")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        verify_result = app.updater.verify(str(manifest_path))
        download_result = app.updater.download(str(manifest_path))
        apply_result = app.updater.apply(download_path=download_result["path"])
        update_result = app.updater.update(str(manifest_path))

        assert verify_result["verified"] is True
        assert download_result["checksum"]["verified"] is True
        assert Path(download_result["path"]).exists()
        assert apply_result["applied"] is True
        assert Path(apply_result["backup_dir"]).exists()
        assert (install_dir / "app.txt").read_text(encoding="utf-8") == "new version"
        assert (install_dir / "notes.txt").read_text(encoding="utf-8") == "release notes"
        assert (Path(apply_result["backup_dir"]) / "app.txt").read_text(encoding="utf-8") == "old version"
        assert update_result["updated"] is True
        assert update_result["check"]["signature_verified"] is True

        verify_response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "updater_verify", "args": {"manifest_url": str(manifest_path)}, "id": 45})
            )
        )
        assert verify_response["error"] is None
        assert verify_response["result"]["verified"] is True

    def test_updater_api_is_unavailable_without_permission(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            permissions="\n".join(
                [
                    "[updater]",
                    "enabled = true",
                ]
            ),
        )
        app = ForgeApp(str(config_path))

        try:
            app.updater.current_version()
        except PermissionError as exc:
            assert "updater" in str(exc)
        else:
            raise AssertionError("Expected PermissionError for disabled updater API")

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "updater_current_version", "args": {}, "id": 44})
            )
        )
        assert response["error"] is not None
        assert "Unknown command" in response["error"]

    def test_window_api_updates_initial_config_before_runtime_ready(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        app.window.set_title("Renamed App")
        app.window.set_position(44, 55)
        app.window.set_size(1440, 900)
        app.window.set_fullscreen(True)
        app.window.set_always_on_top(True)

        assert app.config.window.title == "Renamed App"
        assert app.config.window.width == 1440
        assert app.config.window.height == 900
        assert app.window.position() == {"x": 44, "y": 55}
        assert app.config.window.fullscreen is True
        assert app.config.window.always_on_top is True
        assert app.window.is_ready is False

    def test_window_api_dispatches_runtime_commands_once_proxy_is_ready(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)

        app.window.set_title("Live Title")
        app.window.set_position(99, 123)
        app.window.set_size(1024, 768)
        app.window.set_fullscreen(True)
        app.window.set_always_on_top(True)
        app.window.show()
        app.window.hide()
        app.window.focus()
        app.window.minimize()
        app.window.unminimize()
        app.window.maximize()
        app.window.unmaximize()
        app.window.close()

        assert app.window.is_ready is True
        runtime_calls = [call for call in proxy.calls if call[0] != "evaluate_script"]
        assert runtime_calls == [
            ("set_title", ("Live Title",)),
            ("set_position", (99.0, 123.0)),
            ("set_size", (1024.0, 768.0)),
            ("set_fullscreen", (True,)),
            ("set_always_on_top", (True,)),
            ("set_visible", (True,)),
            ("set_visible", (False,)),
            ("focus", ()),
            ("set_minimized", (True,)),
            ("set_minimized", (False,)),
            ("set_maximized", (True,)),
            ("set_maximized", (False,)),
            ("close", ()),
        ]

    def test_window_runtime_only_operations_fail_before_window_is_ready(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        try:
            app.window.show()
        except RuntimeError as exc:
            assert "not ready" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError when window runtime is unavailable")

    def test_internal_window_ipc_commands_drive_window_runtime(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)

        for payload in [
            {"command": "__forge_window_set_title", "args": {"title": "Bridge Title"}, "id": 11},
            {"command": "__forge_window_set_position", "args": {"x": 222, "y": 333}, "id": 111},
            {"command": "__forge_window_set_size", "args": {"width": 1280, "height": 720}, "id": 12},
            {"command": "__forge_window_set_fullscreen", "args": {"enabled": True}, "id": 13},
            {"command": "__forge_window_set_always_on_top", "args": {"enabled": True}, "id": 14},
            {"command": "__forge_window_show", "args": {}, "id": 15},
            {"command": "__forge_window_hide", "args": {}, "id": 16},
            {"command": "__forge_window_focus", "args": {}, "id": 17},
            {"command": "__forge_window_minimize", "args": {}, "id": 18},
            {"command": "__forge_window_unminimize", "args": {}, "id": 19},
            {"command": "__forge_window_maximize", "args": {}, "id": 20},
            {"command": "__forge_window_unmaximize", "args": {}, "id": 21},
            {"command": "__forge_window_set_vibrancy", "args": {"effect": "sidebar"}, "id": 99},
            {"command": "__forge_window_close", "args": {}, "id": 22},
        ]:
            response = json.loads(app.bridge.invoke_command(json.dumps(payload)))
            assert response["error"] is None
            assert response["result"] is True

        runtime_calls = [call for call in proxy.calls if call[0] != "evaluate_script"]
        assert runtime_calls == [
            ("set_title", ("Bridge Title",)),
            ("set_position", (222.0, 333.0)),
            ("set_size", (1280.0, 720.0)),
            ("set_fullscreen", (True,)),
            ("set_always_on_top", (True,)),
            ("set_visible", (True,)),
            ("set_visible", (False,)),
            ("focus", ()),
            ("set_minimized", (True,)),
            ("set_minimized", (False,)),
            ("set_maximized", (True,)),
            ("set_maximized", (False,)),
            ("set_vibrancy", ("main", "sidebar")),
            ("close", ()),
        ]

    def test_window_state_query_tracks_runtime_changes(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)
        app.window.set_title("Tracked Title")
        app.window.set_size(1111, 777)
        app.window.set_fullscreen(True)
        app.window.set_always_on_top(True)
        app._on_window_event("moved", json.dumps({"x": 12, "y": 34}))
        app._on_window_event("focused", json.dumps({"focused": True}))

        response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_get_state", "args": {}, "id": 23})
            )
        )

        assert response["error"] is None
        assert response["result"] == {
            "title": "Tracked Title",
            "width": 1111,
            "height": 777,
            "fullscreen": True,
            "always_on_top": True,
            "visible": True,
            "focused": True,
            "minimized": False,
            "maximized": False,
            "x": 12,
            "y": 34,
            "closed": False,
        }

        position_response = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_get_position", "args": {}, "id": 24})
            )
        )
        assert position_response["error"] is None
        assert position_response["result"] == {"x": 12, "y": 34}

    def test_window_state_boolean_queries(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)
        app.window.hide()
        app.window.focus()
        app.window.minimize()
        app.window.unminimize()
        app.window.maximize()

        visible = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_is_visible", "args": {}, "id": 25})
            )
        )
        focused = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_is_focused", "args": {}, "id": 26})
            )
        )
        minimized = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_is_minimized", "args": {}, "id": 27})
            )
        )
        maximized = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_window_is_maximized", "args": {}, "id": 28})
            )
        )

        assert visible["result"] is False
        assert focused["result"] is True
        assert minimized["result"] is False
        assert maximized["result"] is True

    def test_native_window_events_emit_to_python_and_js(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()
        received: list[tuple[str, object]] = []

        app.events.on("window:resized", lambda payload: received.append(("resized", payload)))
        app.events.on("window:focused", lambda payload: received.append(("focused", payload)))

        app._on_window_ready(proxy)
        app._on_window_event("resized", json.dumps({"width": 1600, "height": 900}))
        app._on_window_event("focused", json.dumps({"focused": True}))

        assert received == [
            ("resized", {"width": 1600, "height": 900}),
            ("focused", {"focused": True}),
        ]
        assert any(
            call[0] == "evaluate_script" and "window:resized" in call[1][1]
            for call in proxy.calls
        )
        assert any(
            call[0] == "evaluate_script" and "window:focused" in call[1][1]
            for call in proxy.calls
        )

    def test_multiwindow_registry_tracks_managed_windows(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        proxy = self._FakeWindowProxy()

        app._on_window_ready(proxy)
        created = app.windows.create(label="settings", route="/settings", width=900, height=640)

        assert created["label"] == "settings"
        assert created["backend"] == "native"
        assert any(window["label"] == "main" for window in app.windows.list())
        assert app.windows.get("settings")["route"] == "/settings"
        assert any(
            call[0] == "create_window" and '"label": "settings"' in call[1][0]
            for call in proxy.calls
        )

        assert app.windows.close("settings") is True
        assert app.windows.get("settings")["closed"] is True
        assert ("close_window_label", ("settings",)) in proxy.calls

    def test_multiwindow_ipc_commands_expose_registry(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))

        current = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_windows_current", "args": {}, "id": 31})
            )
        )
        created = json.loads(
            app.bridge.invoke_command(
                json.dumps(
                    {
                        "command": "__forge_window_create",
                        "args": {"label": "about", "route": "/about"},
                        "id": 32,
                    }
                )
            )
        )
        listed = json.loads(
            app.bridge.invoke_command(
                json.dumps({"command": "__forge_windows_list", "args": {}, "id": 33})
            )
        )

        assert current["result"]["label"] == "main"
        assert created["result"]["label"] == "about"
        assert any(item["label"] == "about" for item in listed["result"])

    def test_run_uses_positional_native_window_args(self, tmp_path: Path, monkeypatch) -> None:
        config_path = _write_config(tmp_path)
        app = ForgeApp(str(config_path))
        captured: dict[str, object] = {}

        class FakeNativeWindow:
            def __init__(self, *args) -> None:
                captured["args"] = args

            def set_ipc_callback(self, callback) -> None:
                captured["ipc_callback"] = callback

            def set_ready_callback(self, callback) -> None:
                captured["ready_callback"] = callback

            def set_window_event_callback(self, callback) -> None:
                captured["window_event_callback"] = callback

            def run(self) -> None:
                captured["ran"] = True

        monkeypatch.setitem(sys.modules, "forge.forge_core", types.SimpleNamespace(NativeWindow=FakeNativeWindow))

        app.run()

        assert captured["args"] == (
            "Forge App",
            str(tmp_path / "src" / "frontend"),
            1200.0,
            800.0,
            False,
            True,
            True,
            False,
            False,
            400.0,
            300.0,
            None,
            None,
            None,
        )
        assert captured["ran"] is True
