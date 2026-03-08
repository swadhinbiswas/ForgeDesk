"""
Tests for Forge Event System.
"""

import pytest
import threading
import time

from forge.events import EventEmitter


class TestEventEmitter:
    """Tests for EventEmitter class."""

    def test_on_and_emit(self) -> None:
        """Test registering a listener and emitting an event."""
        emitter = EventEmitter()
        received = []

        def handler(data):
            received.append(data)

        emitter.on("test_event", handler)
        emitter.emit("test_event", {"value": 42})

        assert len(received) == 1
        assert received[0]["value"] == 42

    def test_off(self) -> None:
        """Test removing a listener."""
        emitter = EventEmitter()
        received = []

        def handler(data):
            received.append(data)

        emitter.on("test_event", handler)
        emitter.off("test_event", handler)
        emitter.emit("test_event", {"value": 42})

        assert len(received) == 0

    def test_off_all(self) -> None:
        """Test removing all listeners for an event."""
        emitter = EventEmitter()
        received = []

        def handler1(data):
            received.append(1)

        def handler2(data):
            received.append(2)

        emitter.on("test_event", handler1)
        emitter.on("test_event", handler2)
        emitter.off_all("test_event")
        emitter.emit("test_event", {})

        assert len(received) == 0

    def test_off_all_events(self) -> None:
        """Test removing all listeners for all events."""
        emitter = EventEmitter()
        received = []

        def handler(data):
            received.append(data)

        emitter.on("event1", handler)
        emitter.on("event2", handler)
        emitter.off_all()
        emitter.emit("event1", {})
        emitter.emit("event2", {})

        assert len(received) == 0

    def test_has_listeners(self) -> None:
        """Test checking if an event has listeners."""
        emitter = EventEmitter()

        assert emitter.has_listeners("test") is False

        emitter.on("test", lambda x: None)
        assert emitter.has_listeners("test") is True

    def test_listener_count(self) -> None:
        """Test counting listeners for an event."""
        emitter = EventEmitter()

        assert emitter.listener_count("test") == 0

        emitter.on("test", lambda x: None)
        emitter.on("test", lambda x: None)
        assert emitter.listener_count("test") == 2

    def test_multiple_events(self) -> None:
        """Test emitting multiple different events."""
        emitter = EventEmitter()
        events = []

        emitter.on("event1", lambda d: events.append(("e1", d)))
        emitter.on("event2", lambda d: events.append(("e2", d)))

        emitter.emit("event1", {"a": 1})
        emitter.emit("event2", {"b": 2})
        emitter.emit("event1", {"c": 3})

        assert len(events) == 3
        assert events[0] == ("e1", {"a": 1})
        assert events[1] == ("e2", {"b": 2})
        assert events[2] == ("e1", {"c": 3})

    def test_emit_no_listeners(self) -> None:
        """Test emitting an event with no listeners doesn't crash."""
        emitter = EventEmitter()
        # Should not raise
        emitter.emit("no_listeners", {"data": "test"})

    def test_listener_error_doesnt_crash(self) -> None:
        """Test that a listener error doesn't crash other listeners."""
        emitter = EventEmitter()
        received = []

        def good_handler(data):
            received.append(data)

        def bad_handler(data):
            raise Exception("Oops!")

        emitter.on("test", good_handler)
        emitter.on("test", bad_handler)
        emitter.on("test", good_handler)

        # Should not raise, and good handlers should still be called
        emitter.emit("test", {"value": 1})

        assert len(received) == 2

    def test_thread_safety(self) -> None:
        """Test that emitter is thread-safe."""
        emitter = EventEmitter()
        received = []
        lock = threading.Lock()

        def handler(data):
            with lock:
                received.append(data)

        emitter.on("test", handler)

        def emit_thread():
            for i in range(100):
                emitter.emit("test", {"i": i})

        threads = [threading.Thread(target=emit_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(received) == 500

    def test_emit_with_none_data(self) -> None:
        """Test emitting an event with None data."""
        emitter = EventEmitter()
        received = []

        emitter.on("test", lambda d: received.append(d))
        emitter.emit("test", None)

        assert len(received) == 1
        assert received[0] is None

    def test_emit_no_data(self) -> None:
        """Test emitting an event without data argument."""
        emitter = EventEmitter()
        received = []

        emitter.on("test", lambda d: received.append(d))
        emitter.emit("test")

        assert len(received) == 1
        assert received[0] is None
