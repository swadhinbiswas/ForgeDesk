"""
Forge Event System (v2.0).

Provides a thread-safe event emitter/listener pattern for communication
between Python backend and JavaScript frontend.

NoGIL Notes:
    In Python 3.14+ free-threaded mode, threading.Lock still works correctly
    and provides the necessary synchronization. The lock is only held briefly
    during listener list mutations, not during callback execution, so it
    does not become a bottleneck.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

# Type alias for event callbacks
EventCallback = Callable[[Any], None]


class EventEmitter:
    """
    Thread-safe event emitter for Forge applications.

    Supports both synchronous and asynchronous callbacks.
    Events can be emitted from any thread and will be dispatched
    to registered listeners.

    In Python 3.14+ free-threaded mode, multiple threads can emit
    events concurrently without GIL contention. The internal lock
    only protects listener list mutations.
    """

    def __init__(self) -> None:
        """Initialize the event emitter with empty listener registries."""
        self._listeners: Dict[str, List[EventCallback]] = defaultdict(list)
        self._async_listeners: Dict[str, List[Callable[[Any], Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: str, callback: EventCallback) -> None:
        """
        Register a synchronous listener for an event.

        Args:
            event: The event name to listen for.
            callback: Function to call when the event is emitted.
        """
        with self._lock:
            self._listeners[event].append(callback)

    def on_async(self, event: str, callback: Callable[[Any], Any]) -> None:
        """
        Register an asynchronous listener for an event.

        Args:
            event: The event name to listen for.
            callback: Async function to call when the event is emitted.
        """
        with self._lock:
            self._async_listeners[event].append(callback)

    def off(self, event: str, callback: EventCallback) -> None:
        """
        Remove a listener for an event.

        Args:
            event: The event name to remove the listener from.
            callback: The callback function to remove.
        """
        with self._lock:
            if event in self._listeners:
                try:
                    self._listeners[event].remove(callback)
                except ValueError:
                    pass  # Callback not found, ignore

    def off_all(self, event: str | None = None) -> None:
        """
        Remove all listeners for an event or all events.

        Args:
            event: The event name to clear, or None to clear all events.
        """
        with self._lock:
            if event is None:
                self._listeners.clear()
                self._async_listeners.clear()
            else:
                self._listeners.pop(event, None)
                self._async_listeners.pop(event, None)

    def emit(self, event: str, data: Any = None) -> None:
        """
        Emit an event to all registered listeners.

        This method is thread-safe. The lock is only held while copying
        the listener lists, not during callback execution. This means
        callbacks can safely register/unregister listeners without deadlock.

        In Python 3.14+ free-threaded mode, multiple emit() calls from
        different threads run truly in parallel.

        Args:
            event: The event name to emit.
            data: Optional data to pass to the listeners.
        """
        # Copy listener lists under lock (fast), then release lock before executing
        with self._lock:
            sync_callbacks = list(self._listeners.get(event, []))
            async_callbacks = list(self._async_listeners.get(event, []))

        # Call synchronous callbacks (without holding the lock)
        for callback in sync_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in event listener for '{event}': {e}")

        # Schedule asynchronous callbacks
        if async_callbacks:
            try:
                loop = asyncio.get_running_loop()
                for callback in async_callbacks:
                    asyncio.ensure_future(self._call_async_callback(callback, event, data))
            except RuntimeError:
                # No event loop running -- call synchronously as fallback
                for callback in async_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in async event listener for '{event}': {e}")

    async def _call_async_callback(
        self, callback: Callable[[Any], Any], event: str, data: Any
    ) -> None:
        """
        Call an async callback with error handling.

        Args:
            callback: The async callback to invoke.
            event: The event name (for error reporting).
            data: The data to pass to the callback.
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error(f"Error in async event listener for '{event}': {e}")

    def has_listeners(self, event: str) -> bool:
        """
        Check if an event has any registered listeners.

        Args:
            event: The event name to check.

        Returns:
            True if the event has listeners, False otherwise.
        """
        with self._lock:
            return bool(self._listeners.get(event)) or bool(self._async_listeners.get(event))

    def listener_count(self, event: str) -> int:
        """
        Get the number of listeners for an event.

        Args:
            event: The event name to count listeners for.

        Returns:
            The number of registered listeners.
        """
        with self._lock:
            return len(self._listeners.get(event, [])) + len(self._async_listeners.get(event, []))
