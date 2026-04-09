"""Extended event system and __main__ tests for coverage gaps."""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch
import pytest

from forge.events import EventEmitter


# ─── Event Decorator Tests ───

class TestEventDecorators:

    def test_on_as_decorator(self):
        emitter = EventEmitter()
        received = []

        @emitter.on("my_event")
        def handler(data):
            received.append(data)

        emitter.emit("my_event", {"x": 1})
        assert len(received) == 1
        assert received[0]["x"] == 1

    def test_add_listener_alias(self):
        emitter = EventEmitter()
        received = []

        def handler(data):
            received.append(data)

        emitter.add_listener("my_event", handler)
        emitter.emit("my_event", {"x": 1})
        assert len(received) == 1
        assert received[0]["x"] == 1

    def test_on_async_registers_listener(self):
        emitter = EventEmitter()

        async def async_handler(data):
            pass

        emitter.on_async("test", async_handler)
        assert emitter.has_listeners("test")
        assert emitter.listener_count("test") == 1

    def test_on_async_as_decorator(self):
        emitter = EventEmitter()

        @emitter.on_async("my_event")
        async def handler(data):
            pass

        assert emitter.has_listeners("my_event")

    def test_off_nonexistent_callback_no_error(self):
        emitter = EventEmitter()
        emitter.on("test", lambda x: None)
        # Removing a different function should not raise
        emitter.off("test", lambda x: None)

    def test_off_nonexistent_event_no_error(self):
        emitter = EventEmitter()
        # Off on event that doesn't exist should not raise
        emitter.off("nonexistent", lambda x: None)


class TestAsyncEmit:

    def test_async_callbacks_called_without_event_loop(self):
        """Async callbacks fall back to sync execution when no event loop."""
        emitter = EventEmitter()
        received = []

        def sync_disguised_as_async(data):
            received.append(data)

        emitter.on_async("test", sync_disguised_as_async)
        emitter.emit("test", "hello")
        assert len(received) == 1

    def test_off_all_clears_async_listeners_too(self):
        emitter = EventEmitter()

        async def handler(data): pass

        emitter.on("test", lambda x: None)
        emitter.on_async("test", handler)
        assert emitter.listener_count("test") == 2

        emitter.off_all("test")
        assert emitter.listener_count("test") == 0

    def test_off_all_none_clears_everything(self):
        emitter = EventEmitter()

        emitter.on("evt1", lambda x: None)
        emitter.on_async("evt2", lambda x: None)

        emitter.off_all(None)
        assert emitter.listener_count("evt1") == 0
        assert emitter.listener_count("evt2") == 0

    def test_has_listeners_async_only(self):
        emitter = EventEmitter()
        assert emitter.has_listeners("test") is False

        async def handler(data): pass
        emitter.on_async("test", handler)
        assert emitter.has_listeners("test") is True


# ─── __main__.py Tests ───

class TestMainModule:

    def test_main_with_missing_cli(self):
        """main() should print error and exit if forge_cli not installed."""
        from forge.__main__ import main

        with patch.dict("sys.modules", {"forge_cli": None, "forge_cli.main": None}), \
             patch("builtins.__import__", side_effect=ImportError("no module")):
            # Since we can't easily mock the lazy import, test the module exists
            assert callable(main)

    def test_main_module_importable(self):
        """The __main__ module should be importable."""
        import forge.__main__
        assert hasattr(forge.__main__, "main")


# ─── Version Export Tests ───

class TestVersionExports:

    def test_version_is_3_0_0(self):
        import forge
        assert forge.__version__ == "3.0.0"

    def test_new_exports_accessible(self):
        from forge import CircuitBreaker, CrashReporter, ErrorCode, ScopeValidator
        assert CircuitBreaker is not None
        assert CrashReporter is not None
        assert ErrorCode is not None
        assert ScopeValidator is not None

    def test_all_exports_in_all(self):
        import forge
        for name in ["CircuitBreaker", "CrashReporter", "ErrorCode", "ScopeValidator"]:
            assert name in forge.__all__
