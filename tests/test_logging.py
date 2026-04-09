"""Tests for Forge structured logging framework."""

import json
from pathlib import Path

import pytest

from forge.logging import ForgeLogger, LogEntry, LOG_LEVELS, _FileSink


class TestLogEntry:
    def test_entry_to_dict(self):
        entry = LogEntry(
            timestamp="2026-04-07T00:00:00.000Z",
            level="info",
            source="python",
            message="test message",
        )
        d = entry.to_dict()
        assert d["level"] == "info"
        assert d["source"] == "python"
        assert d["message"] == "test message"
        assert "context" not in d  # empty context omitted

    def test_entry_with_context(self):
        entry = LogEntry(
            timestamp="2026-04-07T00:00:00.000Z",
            level="error",
            source="rust",
            message="failed",
            context={"code": 42},
        )
        d = entry.to_dict()
        assert d["context"] == {"code": 42}

    def test_entry_to_json(self):
        entry = LogEntry(
            timestamp="2026-04-07T00:00:00.000Z",
            level="warn",
            source="frontend",
            message="slow render",
        )
        parsed = json.loads(entry.to_json())
        assert parsed["level"] == "warn"
        assert parsed["source"] == "frontend"


class TestLogLevels:
    def test_all_levels_have_numeric_values(self):
        for level in ["debug", "info", "warn", "warning", "error", "fatal"]:
            assert level in LOG_LEVELS
            assert isinstance(LOG_LEVELS[level], int)

    def test_level_ordering(self):
        assert LOG_LEVELS["debug"] < LOG_LEVELS["info"]
        assert LOG_LEVELS["info"] < LOG_LEVELS["warn"]
        assert LOG_LEVELS["warn"] < LOG_LEVELS["error"]
        assert LOG_LEVELS["error"] < LOG_LEVELS["fatal"]


class TestForgeLogger:
    def test_info_logged(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        entry = logger.info("hello")
        assert entry is not None
        assert entry.level == "info"
        assert entry.message == "hello"

    def test_debug_filtered_at_info_level(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        entry = logger.debug("hidden")
        assert entry is None

    def test_debug_logged_at_debug_level(self):
        logger = ForgeLogger(level="debug", enable_console=False, enable_file=False)
        entry = logger.debug("visible")
        assert entry is not None
        assert entry.level == "debug"

    def test_error_logged(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        entry = logger.error("boom", context={"traceback": "..."})
        assert entry is not None
        assert entry.context == {"traceback": "..."}

    def test_invalid_source_normalized(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        entry = logger.info("test", source="unknown_source")
        assert entry is not None
        assert entry.source == "system"

    def test_valid_sources(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        for src in ["python", "rust", "frontend", "ipc", "system"]:
            entry = logger.info("test", source=src)
            assert entry.source == src

    def test_recent_entries(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        for i in range(5):
            logger.info(f"msg {i}")
        entries = logger.recent_entries(3)
        assert len(entries) == 3
        assert entries[-1]["message"] == "msg 4"

    def test_recent_entries_respects_buffer(self):
        logger = ForgeLogger(level="debug", enable_console=False, enable_file=False)
        logger._max_buffer = 10
        for i in range(20):
            logger.debug(f"msg {i}")
        assert len(logger._entries) == 10

    def test_generic_log_method(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        entry = logger.log("warn", "generic warning")
        assert entry is not None
        assert entry.level == "warn"


class TestFileSink:
    def test_write_creates_log_file(self, tmp_path):
        sink = _FileSink(tmp_path)
        entry = LogEntry(
            timestamp="2026-04-07T00:00:00.000Z",
            level="info",
            source="python",
            message="test",
        )
        sink.write(entry)
        files = list(tmp_path.glob("forge-*.log"))
        assert len(files) == 1
        content = files[0].read_text()
        parsed = json.loads(content.strip())
        assert parsed["message"] == "test"

    def test_recent_files(self, tmp_path):
        sink = _FileSink(tmp_path)
        # Create some fake log files
        (tmp_path / "forge-2026-04-05.log").write_text("old")
        (tmp_path / "forge-2026-04-06.log").write_text("newer")
        (tmp_path / "forge-2026-04-07.log").write_text("newest")
        files = sink.recent_files(2)
        assert len(files) == 2

    def test_rotation_triggers_at_max_bytes(self, tmp_path):
        sink = _FileSink(tmp_path, max_bytes=100, backup_count=2)
        entry = LogEntry(
            timestamp="2026-04-07T00:00:00.000Z",
            level="info",
            source="python",
            message="x" * 80,
        )
        # Write enough to exceed max_bytes
        for _ in range(3):
            sink.write(entry)
        # Should have created rotated files
        all_files = list(tmp_path.glob("forge-*"))
        assert len(all_files) >= 2


class TestLoggerWithFile:
    def test_logger_writes_to_file(self, tmp_path):
        logger = ForgeLogger(log_dir=tmp_path, level="info", enable_console=False)
        logger.info("file test")
        files = logger.recent_files()
        assert len(files) >= 1
        content = files[0].read_text()
        assert "file test" in content

    def test_log_dir_property(self, tmp_path):
        logger = ForgeLogger(log_dir=tmp_path, level="info", enable_console=False)
        assert logger.log_dir == tmp_path

    def test_no_log_dir_returns_none(self):
        logger = ForgeLogger(level="info", enable_console=False, enable_file=False)
        assert logger.log_dir is None
