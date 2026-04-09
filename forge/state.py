"""
Forge State Management — Thread-safe typed state container.

NoGIL-Safe Design:
    In Python 3.14+ free-threaded mode, the GIL no longer protects dict
    mutations. This module uses threading.Lock to ensure thread-safe
    access to the managed state store.

Usage:
    # In app setup:
    app.state.manage(Database("sqlite:///app.db"))
    app.state.manage(CacheService(ttl=300))

    # Typed injection (preferred — Tauri-style DX):
    @app.command
    def get_users(db: Database) -> list:
        return db.query("SELECT * FROM users")

    # Container injection (access any managed type):
    @app.command
    def get_users(state: AppState) -> list:
        db = state.get(Database)
        return db.query("SELECT * FROM users")

    # Manual access:
    db = app.state.get(Database)
    cache = app.state.try_get(CacheService)  # Returns None if not managed
"""

from __future__ import annotations

import threading
from typing import Any, TypeVar

T = TypeVar("T")


class AppState:
    """Thread-safe typed state container for Forge applications.

    Equivalent to Tauri's `app.manage()` + `State<T>` injection.

    Each type can only be managed once. Attempting to manage the same
    type twice raises ValueError.

    Thread-safety:
        All operations are protected by a threading.Lock. This is
        critical for NoGIL Python 3.14+ where dict mutations are
        not implicitly serialized.
    """

    def __init__(self) -> None:
        """Initialize empty state store."""
        self._store: dict[type, object] = {}
        self._lock = threading.Lock()

    def manage(self, instance: Any) -> None:
        """Register a typed state object.

        Args:
            instance: The object to manage. Its type is used as the key.

        Raises:
            ValueError: If state of the same type is already managed.
            TypeError: If instance is None.
        """
        if instance is None:
            raise TypeError("Cannot manage None as state")
        key = type(instance)
        with self._lock:
            if key in self._store:
                raise ValueError(
                    f"State of type {key.__name__} is already managed. "
                    f"Each type can only be managed once."
                )
            self._store[key] = instance

    def get(self, state_type: type) -> Any:
        """Retrieve managed state by type.

        Args:
            state_type: The type to look up.

        Returns:
            The managed instance of the given type.

        Raises:
            KeyError: If no state of the given type is managed.
        """
        with self._lock:
            obj = self._store.get(state_type)
        if obj is None:
            raise KeyError(
                f"No managed state of type {state_type.__name__}. "
                f"Did you forget to call app.state.manage(...)?"
            )
        return obj

    def try_get(self, state_type: type) -> Any | None:
        """Retrieve managed state or None if not found.

        Args:
            state_type: The type to look up.

        Returns:
            The managed instance, or None.
        """
        with self._lock:
            return self._store.get(state_type)

    def has(self, state_type: type) -> bool:
        """Check if a type is managed.

        Args:
            state_type: The type to check.

        Returns:
            True if the type is managed.
        """
        with self._lock:
            return state_type in self._store

    def remove(self, state_type: type) -> Any | None:
        """Remove and return managed state by type.

        Args:
            state_type: The type to remove.

        Returns:
            The removed instance, or None if not found.
        """
        with self._lock:
            return self._store.pop(state_type, None)

    def clear(self) -> None:
        """Remove all managed state."""
        with self._lock:
            self._store.clear()

    def snapshot(self) -> dict[str, str]:
        """Return a diagnostic snapshot of managed state types.

        Returns:
            Dict mapping type names to their repr.
        """
        with self._lock:
            return {
                key.__name__: repr(val)
                for key, val in self._store.items()
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __repr__(self) -> str:
        with self._lock:
            types = ", ".join(k.__name__ for k in self._store)
        return f"AppState([{types}])"
