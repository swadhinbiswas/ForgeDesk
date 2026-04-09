"""Forge structured logging framework.

Provides a unified logging surface for the Forge framework with:
- Source tagging (python, rust, frontend, ipc)
- Level filtering (debug, info, warn, error, fatal)
- JSON structured log format with timestamps
- File sink with rotation (5MB max, 3 backups)
- Console sink with Rich-formatted colored output
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ─── Log Levels ───

LOG_LEVELS = {
    "debug": 10,
    "info": 20,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "fatal": 50,
}

_LEVEL_STYLE = {
    "debug": "dim white",
    "info": "bold green",
    "warn": "bold yellow",
    "warning": "bold yellow",
    "error": "bold red",
    "fatal": "bold white on red",
}

_LEVEL_ICON = {
    "debug": "⚙",
    "info": "✔",
    "warn": "⚠",
    "warning": "⚠",
    "error": "✖",
    "fatal": "💀",
}

_LEVEL_LABEL = {
    "debug": "debug",
    "info": "info ",
    "warn": "warn ",
    "warning": "warn ",
    "error": "error",
    "fatal": "fatal",
}

_SOURCE_STYLE = {
    "python": "blue",
    "rust": "magenta",
    "frontend": "cyan",
    "ipc": "yellow",
    "system": "dim",
}

_VALID_SOURCES = {"python", "rust", "frontend", "ipc", "system"}


# ─── Log Entry ───


@dataclass(frozen=True, slots=True)
class LogEntry:
    """A single structured log entry."""

    timestamp: str
    level: str
    source: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message,
        }
        if self.context:
            entry["context"] = self.context
        return entry

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ─── File Sink ───


class _FileSink:
    """Rotating file sink for log entries.

    Args:
        log_dir: Directory to write log files into.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated backups to keep.
    """

    def __init__(
        self,
        log_dir: Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
    ) -> None:
        self._log_dir = Path(log_dir)
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        self._current_path: Path | None = None
        self._current_size: int = 0
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _current_file(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self._log_dir / f"forge-{today}.log"
        if self._current_path != path:
            self._current_path = path
            self._current_size = path.stat().st_size if path.exists() else 0
        return path

    def _rotate_if_needed(self, path: Path) -> None:
        if self._current_size < self._max_bytes:
            return
        # Rotate: forge-2026-04-07.log → forge-2026-04-07.log.1, etc.
        for i in range(self._backup_count, 0, -1):
            src = path.with_suffix(f".log.{i - 1}") if i > 1 else path
            dst = path.with_suffix(f".log.{i}")
            if src.exists():
                src.rename(dst)
        self._current_size = 0

    def write(self, entry: LogEntry) -> None:
        path = self._current_file()
        self._rotate_if_needed(path)
        line = entry.to_json() + "\n"
        encoded = line.encode("utf-8")
        with path.open("ab") as f:
            f.write(encoded)
        self._current_size += len(encoded)

    def recent_files(self, count: int = 3) -> list[Path]:
        """Return the most recent log files, newest first."""
        self._ensure_dir()
        files = sorted(self._log_dir.glob("forge-*.log*"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:count]


# ─── Console Sink ───


class _ConsoleSink:
    """Rich-formatted console sink for log entries."""

    def __init__(self) -> None:
        self._console = None

    def _get_console(self):
        if self._console is None:
            try:
                from rich.console import Console
                self._console = Console(stderr=True)
            except ImportError:
                self._console = None
        return self._console

    def write(self, entry: LogEntry) -> None:
        console = self._get_console()
        if console is None:
            # Fallback to plain stderr
            import sys
            print(
                f"[{entry.source}] {entry.level.upper()}: {entry.message}",
                file=sys.stderr,
            )
            if entry.context:
                print(f"  └── {json.dumps(entry.context)}", file=sys.stderr)
            return

        level_style = _LEVEL_STYLE.get(entry.level, "white")
        source_style = _SOURCE_STYLE.get(entry.source, "white")
        icon = _LEVEL_ICON.get(entry.level.lower(), "•")
        label = _LEVEL_LABEL.get(entry.level.lower(), entry.level[:5])
        
        # Parse time nicely
        time_str = entry.timestamp
        if "T" in time_str:
            time_part = time_str.split("T")[1]
            time_short = time_part.split("+")[0][:8]  # HH:MM:SS
        else:
            time_short = time_str
            
        source_tag = f"\\[{entry.source}]"
        
        log_line = (
            f"[{level_style}]{icon} {label}[/] "
            f"[dim]{time_short}[/] "
            f"[{source_style}]{source_tag}[/] "
            f"{entry.message}"
        )
        
        # Render main line
        console.print(log_line)
        
        # Render context beautifully if it exists
        if entry.context:
            from rich.pretty import Pretty
            from rich.padding import Padding
            console.print(Padding(Pretty(entry.context), (0, 0, 0, 14)))


# ─── Logger ───


class ForgeLogger:
    """Unified structured logger for the Forge framework.

    Usage:
        logger = ForgeLogger(log_dir=Path("~/.myapp/logs"))
        logger.info("App started", source="python")
        logger.error("Connection failed", source="rust", context={"url": "..."})
    """

    def __init__(
        self,
        *,
        log_dir: Path | str | None = None,
        level: str = "info",
        enable_console: bool = True,
        enable_file: bool = True,
    ) -> None:
        self._min_level = LOG_LEVELS.get(level.lower(), 20)
        self._file_sink: _FileSink | None = None
        self._console_sink: _ConsoleSink | None = None
        self._entries: list[LogEntry] = []
        self._max_buffer = 1000  # keep last N entries in memory

        if enable_file and log_dir is not None:
            self._file_sink = _FileSink(Path(log_dir))

        if enable_console:
            self._console_sink = _ConsoleSink()

    @property
    def log_dir(self) -> Path | None:
        return self._file_sink._log_dir if self._file_sink else None

    def _should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level.lower(), 0) >= self._min_level

    def _emit(self, level: str, message: str, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry:
        entry = LogEntry(
            timestamp=_utc_now(),
            level=level.lower(),
            source=source if source in _VALID_SOURCES else "system",
            message=message,
            context=context or {},
        )

        # Buffer
        self._entries.append(entry)
        if len(self._entries) > self._max_buffer:
            self._entries = self._entries[-self._max_buffer:]

        # Write to sinks
        if self._file_sink:
            try:
                self._file_sink.write(entry)
            except OSError:
                pass  # Don't crash the app if logging fails

        if self._console_sink:
            self._console_sink.write(entry)

        return entry

    def debug(self, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        if self._should_log("debug"):
            return self._emit("debug", message, source, context)
        return None

    def info(self, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        if self._should_log("info"):
            return self._emit("info", message, source, context)
        return None

    def warn(self, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        if self._should_log("warn"):
            return self._emit("warn", message, source, context)
        return None

    def error(self, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        if self._should_log("error"):
            return self._emit("error", message, source, context)
        return None

    def fatal(self, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        if self._should_log("fatal"):
            return self._emit("fatal", message, source, context)
        return None

    def log(self, level: str, message: str, *, source: str = "python", context: dict[str, Any] | None = None) -> LogEntry | None:
        """Generic log method accepting any level string."""
        if self._should_log(level):
            return self._emit(level, message, source, context)
        return None

    def recent_entries(self, count: int = 50) -> list[dict[str, Any]]:
        """Return the most recent in-memory log entries."""
        return [e.to_dict() for e in self._entries[-count:]]

    def recent_files(self, count: int = 3) -> list[Path]:
        """Return paths to the most recent log files."""
        if self._file_sink:
            return self._file_sink.recent_files(count)
        return []
