"""
Tests for Forge Error Recovery (Phase 15).

Tests CircuitBreaker, CrashReporter, and ErrorCode.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge.recovery import CircuitBreaker, CrashReporter, ErrorCode


# ─── ErrorCode Tests ───

class TestErrorCode:

    def test_error_codes_are_strings(self):
        assert str(ErrorCode.INTERNAL_ERROR) == "internal_error"
        assert str(ErrorCode.CIRCUIT_OPEN) == "circuit_open"
        assert str(ErrorCode.PERMISSION_DENIED) == "permission_denied"

    def test_all_codes_unique(self):
        values = [e.value for e in ErrorCode]
        assert len(values) == len(set(values))

    def test_protocol_errors_exist(self):
        assert ErrorCode.INVALID_REQUEST
        assert ErrorCode.MALFORMED_JSON
        assert ErrorCode.REQUEST_TOO_LARGE
        assert ErrorCode.PROTOCOL_MISMATCH

    def test_command_errors_exist(self):
        assert ErrorCode.UNKNOWN_COMMAND
        assert ErrorCode.COMMAND_FAILED
        assert ErrorCode.COMMAND_TIMEOUT
        assert ErrorCode.CIRCUIT_OPEN


# ─── CircuitBreaker Tests ───

class TestCircuitBreakerClosed:

    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.get_state("test_cmd") == "closed"
        assert cb.is_allowed("test_cmd")

    def test_allows_commands_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure("test_cmd")
        assert cb.is_allowed("test_cmd")
        assert cb.get_state("test_cmd") == "closed"

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure("test_cmd")
        cb.record_failure("test_cmd")
        cb.record_success("test_cmd")
        assert cb.get_state("test_cmd") == "closed"
        assert cb.is_allowed("test_cmd")


class TestCircuitBreakerOpen:

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        for _ in range(3):
            cb.record_failure("test_cmd")
        assert cb.get_state("test_cmd") == "open"
        assert not cb.is_allowed("test_cmd")

    def test_blocks_commands_when_open(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        cb.record_failure("test_cmd")
        cb.record_failure("test_cmd")
        assert not cb.is_allowed("test_cmd")

    def test_different_commands_independent(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_a")
        assert not cb.is_allowed("cmd_a")
        assert cb.is_allowed("cmd_b")  # Not affected


class TestCircuitBreakerHalfOpen:

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        cb.record_failure("test_cmd")
        cb.record_failure("test_cmd")
        assert cb.get_state("test_cmd") == "open"

        time.sleep(0.15)
        assert cb.get_state("test_cmd") == "half_open"
        assert cb.is_allowed("test_cmd")

    def test_success_in_half_open_closes(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        cb.record_failure("test_cmd")
        cb.record_failure("test_cmd")
        time.sleep(0.15)

        cb.record_success("test_cmd")
        assert cb.get_state("test_cmd") == "closed"


class TestCircuitBreakerManagement:

    def test_reset_specific_command(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_b")
        cb.record_failure("cmd_b")

        cb.reset("cmd_a")
        assert cb.get_state("cmd_a") == "closed"
        assert cb.get_state("cmd_b") != "closed"

    def test_reset_all(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_b")
        cb.record_failure("cmd_b")

        cb.reset()
        assert cb.get_state("cmd_a") == "closed"
        assert cb.get_state("cmd_b") == "closed"

    def test_snapshot(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure("cmd_a")
        cb.record_failure("cmd_a")

        snap = cb.snapshot()
        assert "cmd_a" in snap
        assert snap["cmd_a"]["failures"] == 2
        assert snap["cmd_a"]["state"] == "open"


# ─── CrashReporter Tests ───

class TestCrashReporter:

    def test_install_and_uninstall(self, tmp_path):
        original = sys.excepthook
        reporter = CrashReporter(crash_dir=tmp_path, app_name="test")
        reporter.install()
        assert sys.excepthook is not original
        reporter.uninstall()
        assert sys.excepthook is original

    def test_build_report(self, tmp_path):
        reporter = CrashReporter(crash_dir=tmp_path, app_name="test-app")
        try:
            raise ValueError("test error")
        except ValueError:
            import traceback
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = reporter._build_report(exc_type, exc_value, exc_tb)

        assert report["app_name"] == "test-app"
        assert report["exception"]["type"] == "ValueError"
        assert "test error" in report["exception"]["message"]
        assert "traceback" in report["exception"]
        assert report["system"]["python_version"]

    def test_write_report(self, tmp_path):
        reporter = CrashReporter(crash_dir=tmp_path, app_name="test")
        report = {
            "app_name": "test",
            "timestamp": "2024-01-01",
            "exception": {"type": "TestError", "message": "fail"},
        }
        path = reporter._write_report(report)
        assert path.exists()
        assert path.suffix == ".json"
        with open(path) as f:
            saved = json.load(f)
        assert saved["app_name"] == "test"

    def test_prune_old_reports(self, tmp_path):
        reporter = CrashReporter(crash_dir=tmp_path, max_reports=3)
        # Create 5 reports
        for i in range(5):
            (tmp_path / f"crash_test_{i:03d}.json").write_text("{}")
            time.sleep(0.01)  # Ensure different mtimes

        reporter._prune_reports()
        remaining = list(tmp_path.glob("crash_*.json"))
        assert len(remaining) == 3

    def test_get_recent_reports(self, tmp_path):
        reporter = CrashReporter(crash_dir=tmp_path)
        for i in range(3):
            report = {"index": i, "app_name": "test"}
            (tmp_path / f"crash_test_{i:03d}.json").write_text(json.dumps(report))
            time.sleep(0.01)

        reports = reporter.get_recent_reports(2)
        assert len(reports) == 2
        assert reports[0]["index"] == 2  # Newest first

    def test_handle_exception_writes_report(self, tmp_path):
        reporter = CrashReporter(crash_dir=tmp_path, app_name="test")
        # Don't actually install (would affect test framework), call directly
        original_hook = reporter._original_hook
        reporter._original_hook = MagicMock()  # Suppress stderr output

        try:
            raise RuntimeError("test crash")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            reporter._handle_exception(exc_type, exc_value, exc_tb)

        reporter._original_hook = original_hook

        reports = list(tmp_path.glob("crash_*.json"))
        assert len(reports) == 1
        with open(reports[0]) as f:
            data = json.load(f)
        assert data["exception"]["type"] == "RuntimeError"
        assert "test crash" in data["exception"]["message"]


# ─── Bridge Circuit Breaker Integration ───

class TestBridgeCircuitBreaker:

    def test_circuit_breaker_on_bridge(self):
        """Bridge should have a circuit breaker instance."""
        from forge.bridge import IPCBridge
        bridge = IPCBridge()
        assert hasattr(bridge, "_circuit_breaker")
        assert isinstance(bridge._circuit_breaker, CircuitBreaker)

    def test_failing_command_triggers_breaker(self):
        """Commands that fail repeatedly should trigger circuit breaker."""
        from forge.bridge import IPCBridge

        def always_fail():
            raise RuntimeError("always fails")

        bridge = IPCBridge(commands={"bad_cmd": always_fail})
        bridge._circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)

        # Fail 3 times
        for _ in range(3):
            msg = json.dumps({"id": 1, "command": "bad_cmd", "args": {}})
            response = bridge.invoke_command(msg)
            data = json.loads(response)
            assert data["error"] is not None

        # 4th call should be circuit_open
        msg = json.dumps({"id": 2, "command": "bad_cmd", "args": {}})
        response = bridge.invoke_command(msg)
        data = json.loads(response)
        assert data["error_code"] == "circuit_open"

    def test_successful_command_resets_breaker(self):
        """Successful commands should reset the failure count."""
        from forge.bridge import IPCBridge

        call_count = 0
        def sometimes_fail():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")
            return "ok"

        bridge = IPCBridge(commands={"flaky_cmd": sometimes_fail})
        bridge._circuit_breaker = CircuitBreaker(failure_threshold=5)

        # Fail twice
        for _ in range(2):
            msg = json.dumps({"id": 1, "command": "flaky_cmd", "args": {}})
            bridge.invoke_command(msg)

        # Succeed
        msg = json.dumps({"id": 2, "command": "flaky_cmd", "args": {}})
        response = bridge.invoke_command(msg)
        data = json.loads(response)
        assert data["result"] == "ok"

        # Circuit should be closed
        assert bridge._circuit_breaker.get_state("flaky_cmd") == "closed"
