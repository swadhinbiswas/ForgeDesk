"""Tests for IPC Envelope Enhancement — correlation_id, timestamp, error_detail."""
import json
import uuid

import pytest


def make_bridge():
    """Create a minimal IPCBridge for testing."""
    from forge.bridge import IPCBridge
    from forge.config import ForgeConfig
    config = ForgeConfig()
    bridge = IPCBridge(config)
    bridge.register_command("echo", lambda message="hello": {"echo": message})
    return bridge


class TestCorrelationId:
    def test_response_echoes_frontend_correlation_id(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 1, "correlation_id": "my-custom-id"})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["correlation_id"] == "my-custom-id"

    def test_response_generates_correlation_id_when_missing(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 2})
        resp = json.loads(bridge.invoke_command(req))
        # Should be a valid UUID
        cid = resp["correlation_id"]
        assert cid is not None
        uuid.UUID(cid)  # Raises ValueError if not valid UUID

    def test_correlation_id_in_error_response(self):
        bridge = make_bridge()
        req = json.dumps({"command": "nonexistent", "id": 3, "correlation_id": "err-track-99"})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["correlation_id"] == "err-track-99"


class TestTimestamp:
    def test_success_response_has_timestamp(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 10})
        resp = json.loads(bridge.invoke_command(req))
        assert "timestamp" in resp
        assert isinstance(resp["timestamp"], float)
        assert resp["timestamp"] > 0

    def test_error_response_has_timestamp(self):
        bridge = make_bridge()
        req = json.dumps({"command": "nonexistent", "id": 11})
        resp = json.loads(bridge.invoke_command(req))
        assert "timestamp" in resp
        assert isinstance(resp["timestamp"], float)
        assert resp["timestamp"] > 0


class TestErrorDetail:
    def test_error_response_contains_error_detail(self):
        bridge = make_bridge()
        req = json.dumps({"command": "nonexistent", "id": 20})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["error_detail"] is not None
        assert resp["error_detail"]["code"] == "unknown_command"
        assert "nonexistent" in resp["error_detail"]["message"]
        assert resp["error_detail"]["source"] == "bridge"

    def test_success_response_has_null_error_detail(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 21})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["error_detail"] is None

    def test_backward_compatible_flat_error_string(self):
        """The flat 'error' field still exists for backward compatibility."""
        bridge = make_bridge()
        req = json.dumps({"command": "nonexistent", "id": 22})
        resp = json.loads(bridge.invoke_command(req))
        assert isinstance(resp["error"], str)
        assert "nonexistent" in resp["error"]


class TestTraceMeta:
    def test_trace_meta_includes_command_version(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 30, "trace": True})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["meta"] is not None
        assert "command_version" in resp["meta"]
        assert resp["meta"]["command_version"] == "1.0"

    def test_no_meta_without_trace(self):
        bridge = make_bridge()
        req = json.dumps({"command": "echo", "id": 31})
        resp = json.loads(bridge.invoke_command(req))
        assert resp["meta"] is None
"""Tests for IPC Envelope Enhancement — correlation_id, timestamp, error_detail."""
