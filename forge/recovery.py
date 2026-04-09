"""
Forge Error Recovery — Circuit breaker and crash reporting.

Production apps must never crash silently. This module provides:

1. **CircuitBreaker** — Temporarily disables commands that fail consecutively,
   preventing cascading failures. After a cooldown period, the command is
   re-enabled (half-open state) and tested with the next call.

2. **CrashReporter** — Captures unhandled exceptions, generates structured
   crash reports with context, and writes them to disk for post-mortem analysis.

3. **ErrorCode** — Enumeration of structured error codes for consistent
   frontend error handling across the IPC bridge.
"""

from __future__ import annotations

import json
import logging
import platform
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── Structured Error Codes ───

class ErrorCode(str, Enum):
    """Structured error codes for the IPC bridge.

    These codes are sent to the frontend alongside error messages,
    enabling programmatic error handling without string parsing.
    """

    # Protocol errors
    INVALID_REQUEST = "invalid_request"
    MALFORMED_JSON = "malformed_json"
    REQUEST_TOO_LARGE = "request_too_large"
    PROTOCOL_MISMATCH = "protocol_mismatch"

    # Auth / Permission errors
    PERMISSION_DENIED = "permission_denied"
    ORIGIN_NOT_ALLOWED = "origin_not_allowed"
    COMMAND_NOT_ALLOWED = "command_not_allowed"
    WINDOW_SCOPE_DENIED = "window_scope_denied"

    # Command errors
    UNKNOWN_COMMAND = "unknown_command"
    COMMAND_FAILED = "command_failed"
    COMMAND_TIMEOUT = "command_timeout"
    CIRCUIT_OPEN = "circuit_open"

    # Internal errors
    INTERNAL_ERROR = "internal_error"
    STATE_NOT_FOUND = "state_not_found"
    RATE_LIMITED = "rate_limited"

    def __str__(self) -> str:
        return self.value


# ─── Circuit Breaker ───

class CircuitBreaker:
    """Circuit breaker for IPC commands.

    Tracks consecutive failures per command. When a command exceeds
    ``failure_threshold`` consecutive failures, it enters the **open**
    state and all subsequent calls are rejected immediately for
    ``cooldown_seconds``. After cooldown, the circuit enters **half-open**
    state and allows one test call through.

    Thread-safe: all state mutations are protected by a lock.

    Args:
        failure_threshold: Number of consecutive failures before opening.
        cooldown_seconds: Seconds to wait before allowing a test call.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._open_since: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_allowed(self, command_name: str) -> bool:
        """Check whether a command is allowed to execute.

        Returns:
            True if the command can proceed (closed or half-open),
            False if the circuit is open and cooldown hasn't elapsed.
        """
        with self._lock:
            failures = self._failures.get(command_name, 0)
            if failures < self._threshold:
                return True

            # Circuit is open — check cooldown
            opened_at = self._open_since.get(command_name, 0.0)
            elapsed = time.monotonic() - opened_at
            if elapsed >= self._cooldown:
                # Half-open: allow one test call
                return True

            return False

    def record_success(self, command_name: str) -> None:
        """Record a successful command execution (resets the failure count)."""
        with self._lock:
            self._failures.pop(command_name, None)
            self._open_since.pop(command_name, None)

    def record_failure(self, command_name: str) -> None:
        """Record a failed command execution."""
        with self._lock:
            count = self._failures.get(command_name, 0) + 1
            self._failures[command_name] = count
            if count >= self._threshold and command_name not in self._open_since:
                self._open_since[command_name] = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN for command '%s' after %d consecutive failures",
                    command_name,
                    count,
                )

    def get_state(self, command_name: str) -> str:
        """Get the circuit state for a command.

        Returns:
            'closed' — normal operation
            'open' — command is disabled
            'half_open' — cooldown elapsed, awaiting test call
        """
        with self._lock:
            failures = self._failures.get(command_name, 0)
            if failures < self._threshold:
                return "closed"

            opened_at = self._open_since.get(command_name, 0.0)
            elapsed = time.monotonic() - opened_at
            if elapsed >= self._cooldown:
                return "half_open"

            return "open"

    def reset(self, command_name: Optional[str] = None) -> None:
        """Reset circuit breaker state.

        Args:
            command_name: Specific command to reset, or None for all.
        """
        with self._lock:
            if command_name is not None:
                self._failures.pop(command_name, None)
                self._open_since.pop(command_name, None)
            else:
                self._failures.clear()
                self._open_since.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a diagnostic snapshot of all tracked commands."""
        with self._lock:
            result = {}
            for cmd in set(list(self._failures.keys()) + list(self._open_since.keys())):
                failures = self._failures.get(cmd, 0)
                opened_at = self._open_since.get(cmd)
                state = "closed"
                if failures >= self._threshold:
                    if opened_at and (time.monotonic() - opened_at) < self._cooldown:
                        state = "open"
                    else:
                        state = "half_open"
                result[cmd] = {
                    "failures": failures,
                    "state": state,
                    "threshold": self._threshold,
                }
            return result


# ─── Crash Reporter ───

class CrashReporter:
    """Captures and persists crash reports for post-mortem analysis.

    Installs a global exception hook via ``sys.excepthook`` that
    captures unhandled exceptions and writes structured JSON crash
    reports to the configured directory.

    Args:
        crash_dir: Directory to write crash report files.
        app_name: Application name for report metadata.
        max_reports: Maximum number of crash reports to keep (oldest deleted first).
    """

    def __init__(
        self,
        crash_dir: Path,
        app_name: str = "forge-app",
        max_reports: int = 10,
    ) -> None:
        self._crash_dir = Path(crash_dir)
        self._app_name = app_name
        self._max_reports = max_reports
        self._original_hook = sys.excepthook
        self._reports: list[dict[str, Any]] = []

    def install(self) -> None:
        """Install the crash reporter as the global exception hook."""
        self._crash_dir.mkdir(parents=True, exist_ok=True)
        sys.excepthook = self._handle_exception
        logger.debug("CrashReporter installed for '%s'", self._app_name)

    def uninstall(self) -> None:
        """Restore the original exception hook."""
        sys.excepthook = self._original_hook

    def _handle_exception(
        self,
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        """Global exception handler that captures crash reports."""
        report = self._build_report(exc_type, exc_value, exc_tb)
        self._reports.append(report)

        # Write to disk
        try:
            report_path = self._write_report(report)
            logger.critical(
                "Crash report written to: %s",
                report_path,
            )
        except Exception as write_err:
            logger.error("Failed to write crash report: %s", write_err)

        # Prune old reports
        self._prune_reports()

        # Call original hook (prints traceback to stderr)
        self._original_hook(exc_type, exc_value, exc_tb)

    def _build_report(
        self,
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Any,
    ) -> dict[str, Any]:
        """Build a structured crash report."""
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)

        return {
            "app_name": self._app_name,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "exception": {
                "type": exc_type.__name__,
                "module": exc_type.__module__,
                "message": str(exc_value),
                "traceback": "".join(tb_lines),
            },
            "system": {
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "python_impl": platform.python_implementation(),
                "machine": platform.machine(),
            },
            "process": {
                "argv": sys.argv[:],
                "executable": sys.executable,
                "pid": _safe_getpid(),
            },
        }

    def _write_report(self, report: dict[str, Any]) -> Path:
        """Write a crash report to disk and return the file path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"crash_{self._app_name}_{ts}.json"
        report_path = self._crash_dir / filename

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        return report_path

    def _prune_reports(self) -> None:
        """Delete oldest reports if over max_reports."""
        reports = sorted(
            self._crash_dir.glob("crash_*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(reports) > self._max_reports:
            oldest = reports.pop(0)
            try:
                oldest.unlink()
            except Exception:
                pass

    def get_recent_reports(self, count: int = 5) -> list[dict[str, Any]]:
        """Load the most recent crash reports from disk.

        Args:
            count: Number of reports to load.

        Returns:
            List of crash report dicts, newest first.
        """
        files = sorted(
            self._crash_dir.glob("crash_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:count]

        reports = []
        for f in files:
            try:
                with open(f) as fh:
                    reports.append(json.load(fh))
            except Exception:
                pass
        return reports


def _safe_getpid() -> int:
    """Get PID safely (works in all contexts)."""
    import os
    return os.getpid()
