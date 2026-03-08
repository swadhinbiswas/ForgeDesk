"""Supportability primitives for Forge runtime diagnostics."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import threading
import traceback
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from weakref import WeakSet

from .bridge import PROTOCOL_VERSION


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeLogBuffer:
    """Thread-safe in-memory buffer for structured runtime log entries."""

    def __init__(self, capacity: int = 500) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)

    def record(
        self,
        level: str,
        logger_name: str,
        message: str,
        *,
        event: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.add(
            {
                "timestamp": _utc_now(),
                "level": level,
                "logger": logger_name,
                "message": message,
                "event": event,
                "meta": meta or {},
            }
        )

    def snapshot(self, limit: int | None = 100) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._entries)

        if limit is None or limit <= 0:
            return entries
        return entries[-limit:]


class StructuredLogHandler(logging.Handler):
    """Shared log handler that fans structured entries out to active app buffers."""

    def __init__(self, buffers: WeakSet[RuntimeLogBuffer]) -> None:
        super().__init__()
        self._buffers = buffers

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": _utc_now(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "event": getattr(record, "forge_event", None),
                "meta": dict(getattr(record, "forge_meta", {}) or {}),
            }
            for buffer in list(self._buffers):
                buffer.add(dict(entry))
        except Exception:
            self.handleError(record)


_ACTIVE_LOG_BUFFERS: WeakSet[RuntimeLogBuffer] = WeakSet()
_LOG_HANDLER_LOCK = threading.Lock()
_SHARED_LOG_HANDLER: StructuredLogHandler | None = None


def register_runtime_log_buffer(buffer: RuntimeLogBuffer) -> None:
    """Register an app-local log buffer with the shared Forge logger pipeline."""
    global _SHARED_LOG_HANDLER

    with _LOG_HANDLER_LOCK:
        _ACTIVE_LOG_BUFFERS.add(buffer)
        if _SHARED_LOG_HANDLER is None:
            forge_logger = logging.getLogger("forge")
            _SHARED_LOG_HANDLER = StructuredLogHandler(_ACTIVE_LOG_BUFFERS)
            forge_logger.addHandler(_SHARED_LOG_HANDLER)
            if forge_logger.level == logging.NOTSET or forge_logger.level > logging.INFO:
                forge_logger.setLevel(logging.INFO)


class SupportBundleBuilder:
    """Exports a minimal support bundle zip for incident triage."""

    def __init__(self, app: Any, log_buffer: RuntimeLogBuffer) -> None:
        self._app = app
        self._log_buffer = log_buffer

    def export(self, destination: str | Path | None = None) -> str:
        app_name = getattr(self._app.config.app, "name", "forge-app")
        safe_name = app_name.lower().replace(" ", "-")

        if destination is None:
            destination_path = self._app.config.get_output_path() / f"{safe_name}-support-bundle.zip"
        else:
            destination_path = Path(destination)
            if destination_path.suffix.lower() != ".zip":
                destination_path = destination_path / f"{safe_name}-support-bundle.zip"

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        diagnostics = self._app.runtime.diagnostics(include_logs=True, log_limit=None)
        payload = {
            "generated_at": _utc_now(),
            "framework": {
                "protocol": PROTOCOL_VERSION,
            },
            "environment": {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
                "cwd": os.getcwd(),
            },
            "diagnostics": diagnostics,
        }

        with zipfile.ZipFile(destination_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "generated_at": payload["generated_at"],
                        "app": diagnostics.get("app", {}),
                        "protocol": PROTOCOL_VERSION,
                        "has_crash": diagnostics.get("crash") is not None,
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )
            archive.writestr("diagnostics.json", json.dumps(payload, indent=2, sort_keys=True))
            archive.writestr(
                "logs.json",
                json.dumps(self._log_buffer.snapshot(limit=None), indent=2, sort_keys=True),
            )
            archive.writestr(
                "command-registry.json",
                json.dumps(self._app.runtime.commands(), indent=2, sort_keys=True),
            )
            archive.writestr(
                "config.json",
                json.dumps(self._app.runtime.config_snapshot(), indent=2, sort_keys=True),
            )
            last_crash = self._app.runtime.last_crash()
            if last_crash is not None:
                archive.writestr("crash.json", json.dumps(last_crash, indent=2, sort_keys=True))

        return str(destination_path)


class CrashStore:
    """Stores the latest crash snapshot and can install global exception hooks."""

    def __init__(self, on_crash: callable | None = None) -> None:
        self._lock = threading.Lock()
        self._last_crash: dict[str, Any] | None = None
        self._on_crash = on_crash
        self._previous_excepthook = None
        self._previous_threading_excepthook = None

    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._last_crash) if self._last_crash is not None else None

    def clear(self) -> None:
        with self._lock:
            self._last_crash = None

    def capture_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
        *,
        thread_name: str | None = None,
        fatal: bool = True,
    ) -> dict[str, Any]:
        crash = {
            "timestamp": _utc_now(),
            "type": getattr(exc_type, "__name__", str(exc_type)),
            "message": str(exc_value),
            "thread": thread_name,
            "fatal": fatal,
            "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        }
        with self._lock:
            self._last_crash = crash
        if self._on_crash is not None:
            self._on_crash(crash)
        return crash

    def install(self) -> None:
        if self._previous_excepthook is not None:
            return

        self._previous_excepthook = sys.excepthook
        self._previous_threading_excepthook = getattr(threading, "excepthook", None)

        def _handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
            self.capture_exception(exc_type, exc_value, exc_traceback, thread_name="MainThread", fatal=True)
            if self._previous_excepthook is not None:
                self._previous_excepthook(exc_type, exc_value, exc_traceback)

        def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
            self.capture_exception(
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
                thread_name=getattr(args.thread, "name", None),
                fatal=True,
            )
            if self._previous_threading_excepthook is not None:
                self._previous_threading_excepthook(args)

        sys.excepthook = _handle_exception
        if self._previous_threading_excepthook is not None:
            threading.excepthook = _handle_thread_exception

    def uninstall(self) -> None:
        if self._previous_excepthook is not None:
            sys.excepthook = self._previous_excepthook
            self._previous_excepthook = None
        if self._previous_threading_excepthook is not None:
            threading.excepthook = self._previous_threading_excepthook
            self._previous_threading_excepthook = None
