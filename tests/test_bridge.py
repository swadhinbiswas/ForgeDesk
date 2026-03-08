"""
Tests for Forge IPC Bridge.

Includes security tests for command validation and input sanitization.
"""

import json
import pytest
from unittest.mock import MagicMock

from forge.bridge import IPCBridge, PROTOCOL_VERSION, command, requires_capability


class TestIPCBridgeSecurity:
    """Security tests for IPCBridge."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock ForgeApp."""
        return MagicMock()

    @pytest.fixture
    def bridge(self, mock_app: MagicMock) -> IPCBridge:
        """Create an IPCBridge instance."""
        return IPCBridge(mock_app, {})

    def test_valid_command_name(self, bridge: IPCBridge) -> None:
        """Test that valid command names are accepted."""
        assert bridge._validate_command_name("greet") is True
        assert bridge._validate_command_name("get_system_info") is True
        assert bridge._validate_command_name("_private") is True
        assert bridge._validate_command_name("cmd123") is True

    def test_invalid_command_names(self, bridge: IPCBridge) -> None:
        """Test that invalid command names are rejected."""
        assert bridge._validate_command_name("") is False
        assert bridge._validate_command_name("123start") is False
        assert bridge._validate_command_name("cmd-name") is False
        assert bridge._validate_command_name("cmd.name") is False
        assert bridge._validate_command_name("cmd name") is False
        assert bridge._validate_command_name("cmd;name") is False
        assert bridge._validate_command_name("cmd$name") is False

    def test_command_name_too_long(self, bridge: IPCBridge) -> None:
        """Test that excessively long command names are rejected."""
        long_name = "a" * 101
        assert bridge._validate_command_name(long_name) is False

    def test_non_string_command_name(self, bridge: IPCBridge) -> None:
        """Test that non-string command names are rejected."""
        assert bridge._validate_command_name(123) is False
        assert bridge._validate_command_name(None) is False
        assert bridge._validate_command_name(["list"]) is False

    def test_sanitize_error_removes_paths(self, bridge: IPCBridge) -> None:
        """Test that error sanitization removes path information."""
        import os
        error_msg = f"Error accessing {os.getcwd()}/secret/file.txt"
        sanitized = bridge._sanitize_error(Exception(error_msg))
        assert os.getcwd() not in sanitized

    def test_sanitize_error_limits_length(self, bridge: IPCBridge) -> None:
        """Test that error sanitization limits message length."""
        long_error = "a" * 1000
        sanitized = bridge._sanitize_error(Exception(long_error))
        assert len(sanitized) <= 503  # 500 + "..."

    def test_invoke_invalid_json(self, bridge: IPCBridge) -> None:
        """Test that invalid JSON is rejected."""
        result = bridge.invoke_command("not valid json")
        response = json.loads(result)
        assert "error" in response
        assert response["id"] is None
        assert response["type"] == "reply"
        assert response["protocol"] == PROTOCOL_VERSION
        assert response["error_code"] == "invalid_request"

    def test_invoke_missing_command(self, bridge: IPCBridge) -> None:
        """Test that missing command field is rejected."""
        result = bridge.invoke_command('{"args": {}, "id": 1}')
        response = json.loads(result)
        assert "error" in response
        assert "Missing" in response["error"]

    def test_invoke_invalid_command_name(self, bridge: IPCBridge) -> None:
        """Test that invalid command names are rejected."""
        request = json.dumps({
            "command": "../../../etc/passwd",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "error" in response
        assert "Invalid command name" in response["error"]

    def test_invoke_unknown_command(self, bridge: IPCBridge) -> None:
        """Test that unknown commands return an error."""
        request = json.dumps({
            "command": "nonexistent_command",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "error" in response
        assert "Unknown command" in response["error"]
        assert response["error_code"] == "unknown_command"

    def test_invoke_unsupported_protocol(self, bridge: IPCBridge) -> None:
        """Test that unsupported protocol versions are rejected."""
        request = json.dumps({
            "protocol": "9.9",
            "command": "test",
            "args": {},
            "id": 7,
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert response["error_code"] == "unsupported_protocol"
        assert "Unsupported protocol version" in response["error"]

    def test_invoke_args_not_dict(self, bridge: IPCBridge) -> None:
        """Test that non-dict args are rejected."""
        request = json.dumps({
            "command": "test",
            "args": "not a dict",
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "error" in response

    def test_invoke_request_too_large(self, bridge: IPCBridge) -> None:
        """Test that excessively large requests are rejected."""
        large_request = json.dumps({
            "command": "test",
            "args": {"data": "x" * (11 * 1024 * 1024)},  # 11MB
            "id": 1
        })
        result = bridge.invoke_command(large_request)
        response = json.loads(result)
        assert "error" in response
        assert "too large" in response["error"].lower()

    def test_invoke_valid_request(self, bridge: IPCBridge) -> None:
        """Test that valid requests work correctly."""
        # Register a test command
        bridge._commands["test_cmd"] = lambda x: x * 2

        request = json.dumps({
            "command": "test_cmd",
            "args": {"x": 5},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "result" in response
        assert response["result"] == 10
        assert response["id"] == 1
        assert response["type"] == "reply"
        assert response["protocol"] == PROTOCOL_VERSION
        assert response["error_code"] is None
        assert response["meta"] is None

    def test_invoke_trace_includes_timing_metadata(self, bridge: IPCBridge) -> None:
        """Test that traced requests include timing metadata in replies."""
        bridge._commands["test_cmd"] = lambda x: x * 2

        request = json.dumps(
            {"command": "test_cmd", "args": {"x": 5}, "id": 11, "trace": True}
        )
        result = bridge.invoke_command(request)
        response = json.loads(result)

        assert response["error"] is None
        assert response["meta"] is not None
        assert response["meta"]["command"] == "test_cmd"
        assert response["meta"]["duration_ms"] >= 0

    def test_invoke_trace_error_includes_timing_metadata(self, bridge: IPCBridge) -> None:
        """Test that traced failures also include timing metadata."""
        request = json.dumps(
            {"command": "missing_cmd", "args": {}, "id": 12, "trace": True}
        )
        result = bridge.invoke_command(request)
        response = json.loads(result)

        assert response["error_code"] == "unknown_command"
        assert response["meta"] is not None
        assert response["meta"]["command"] == "missing_cmd"
        assert response["meta"]["duration_ms"] >= 0

    def test_invoke_command_error(self, bridge: IPCBridge) -> None:
        """Test that command errors are handled gracefully."""
        def failing_cmd():
            raise ValueError("Something went wrong")

        bridge._commands["failing"] = failing_cmd

        request = json.dumps({
            "command": "failing",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "error" in response
        assert response["id"] == 1

    def test_invoke_type_error_sanitized(self, bridge: IPCBridge) -> None:
        """Test that type errors don't expose internal details."""
        def typed_cmd(x: int):
            return x + 1

        bridge._commands["typed"] = typed_cmd

        # Call with wrong type
        request = json.dumps({
            "command": "typed",
            "args": {"x": "not an int"},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert "error" in response
        # Should not expose stack trace
        assert "Traceback" not in response["error"]


class TestIPCBridgeWithApp:
    """Integration tests for IPCBridge with ForgeApp."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create a mock ForgeApp."""
        return MagicMock()

    def test_command_with_no_args(self, mock_app: MagicMock) -> None:
        """Test invoking a command with no arguments."""
        bridge = IPCBridge(mock_app, {"get_time": lambda: "12:00"})

        request = json.dumps({
            "command": "get_time",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert response["result"] == "12:00"

    def test_command_with_multiple_args(self, mock_app: MagicMock) -> None:
        """Test invoking a command with multiple arguments."""
        bridge = IPCBridge(mock_app, {
            "add": lambda a, b: a + b
        })

        request = json.dumps({
            "command": "add",
            "args": {"a": 10, "b": 20},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert response["result"] == 30

    def test_command_returns_dict(self, mock_app: MagicMock) -> None:
        """Test invoking a command that returns a dict."""
        bridge = IPCBridge(mock_app, {
            "get_info": lambda: {"os": "linux", "version": "1.0"}
        })

        request = json.dumps({
            "command": "get_info",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert response["result"]["os"] == "linux"

    def test_command_returns_none(self, mock_app: MagicMock) -> None:
        """Test invoking a command that returns None."""
        bridge = IPCBridge(mock_app, {
            "do_nothing": lambda: None
        })

        request = json.dumps({
            "command": "do_nothing",
            "args": {},
            "id": 1
        })
        result = bridge.invoke_command(request)
        response = json.loads(result)
        assert response["result"] is None

    def test_capability_gated_command_denied(self, mock_app: MagicMock) -> None:
        """Test that capability-gated commands are denied when disabled."""
        mock_app.has_capability.return_value = False

        @requires_capability("clipboard")
        def clipboard_secret() -> str:
            return "secret"

        bridge = IPCBridge(mock_app, {"clipboard_secret": clipboard_secret})
        request = json.dumps({"command": "clipboard_secret", "args": {}, "id": 2})

        result = bridge.invoke_command(request)
        response = json.loads(result)

        assert response["result"] is None
        assert "Permission denied" in response["error"]
        assert "clipboard" in response["error"]

    def test_capability_gated_command_allowed(self, mock_app: MagicMock) -> None:
        """Test that capability-gated commands execute when enabled."""
        mock_app.has_capability.return_value = True

        @command(capability="clipboard")
        def clipboard_secret() -> str:
            return "secret"

        bridge = IPCBridge(mock_app, {"clipboard_secret": clipboard_secret})
        request = json.dumps({"command": "clipboard_secret", "args": {}, "id": 3})

        result = bridge.invoke_command(request)
        response = json.loads(result)

        assert response["error"] is None
        assert response["result"] == "secret"

    def test_command_registry_exposes_metadata(self, mock_app: MagicMock) -> None:
        """Test that the bridge exposes command metadata for IPC introspection."""

        @command(capability="clipboard", version="1.2")
        def clipboard_secret() -> str:
            return "secret"

        bridge = IPCBridge(mock_app, {"clipboard_secret": clipboard_secret})
        registry = bridge.get_command_registry()

        assert registry == [
            {
                "name": "__forge_describe_commands",
                "capability": None,
                "version": PROTOCOL_VERSION,
                "internal": True,
            },
            {
                "name": "__forge_protocol_info",
                "capability": None,
                "version": PROTOCOL_VERSION,
                "internal": True,
            },
            {
                "name": "clipboard_secret",
                "capability": "clipboard",
                "version": "1.2",
                "internal": False,
            }
        ]

    def test_internal_describe_commands_command(self, mock_app: MagicMock) -> None:
        """Test the built-in command registry introspection command."""
        bridge = IPCBridge(mock_app, {"hello": lambda: "world"})

        result = bridge.invoke_command(
            json.dumps({"command": "__forge_describe_commands", "args": {}, "id": 4})
        )
        response = json.loads(result)

        assert response["error"] is None
        assert response["result"]["protocol"] == PROTOCOL_VERSION
        assert any(item["name"] == "hello" for item in response["result"]["commands"])

    def test_internal_protocol_info_command(self, mock_app: MagicMock) -> None:
        """Test the built-in protocol support introspection command."""
        bridge = IPCBridge(mock_app, {})

        result = bridge.invoke_command(
            json.dumps({"command": "__forge_protocol_info", "args": {}, "id": 5})
        )
        response = json.loads(result)

        assert response["error"] is None
        assert response["result"]["current"] == PROTOCOL_VERSION
        assert PROTOCOL_VERSION in response["result"]["supported"]
