"""Tests for forge.state — Thread-safe typed state management."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from forge.state import AppState


# ─── Test Types ───

class Database:
    """Mock database for testing."""
    def __init__(self, url: str):
        self.url = url

    def __repr__(self) -> str:
        return f"Database({self.url!r})"


class CacheService:
    """Mock cache service."""
    def __init__(self, ttl: int = 300):
        self.ttl = ttl


class Logger:
    """Mock logger."""
    pass


# ─── Basic Operations ───

class TestAppStateBasics:
    def test_manage_and_get(self):
        state = AppState()
        db = Database("sqlite:///test.db")
        state.manage(db)
        assert state.get(Database) is db

    def test_manage_multiple_types(self):
        state = AppState()
        db = Database("sqlite:///test.db")
        cache = CacheService(ttl=60)
        state.manage(db)
        state.manage(cache)
        assert state.get(Database) is db
        assert state.get(CacheService) is cache

    def test_get_missing_raises_key_error(self):
        state = AppState()
        with pytest.raises(KeyError, match="No managed state of type Database"):
            state.get(Database)

    def test_manage_duplicate_raises_value_error(self):
        state = AppState()
        state.manage(Database("first"))
        with pytest.raises(ValueError, match="already managed"):
            state.manage(Database("second"))

    def test_manage_none_raises_type_error(self):
        state = AppState()
        with pytest.raises(TypeError, match="Cannot manage None"):
            state.manage(None)

    def test_try_get_returns_none(self):
        state = AppState()
        assert state.try_get(Database) is None

    def test_try_get_returns_instance(self):
        state = AppState()
        db = Database("test")
        state.manage(db)
        assert state.try_get(Database) is db

    def test_has(self):
        state = AppState()
        assert not state.has(Database)
        state.manage(Database("test"))
        assert state.has(Database)

    def test_remove(self):
        state = AppState()
        db = Database("test")
        state.manage(db)
        removed = state.remove(Database)
        assert removed is db
        assert not state.has(Database)

    def test_remove_missing_returns_none(self):
        state = AppState()
        assert state.remove(Database) is None

    def test_clear(self):
        state = AppState()
        state.manage(Database("a"))
        state.manage(CacheService())
        assert len(state) == 2
        state.clear()
        assert len(state) == 0

    def test_len(self):
        state = AppState()
        assert len(state) == 0
        state.manage(Database("test"))
        assert len(state) == 1
        state.manage(CacheService())
        assert len(state) == 2

    def test_repr(self):
        state = AppState()
        assert repr(state) == "AppState([])"
        state.manage(Database("test"))
        assert "Database" in repr(state)

    def test_snapshot(self):
        state = AppState()
        db = Database("sqlite:///test.db")
        state.manage(db)
        snap = state.snapshot()
        assert "Database" in snap
        assert "sqlite:///test.db" in snap["Database"]


# ─── Thread Safety ───

class TestAppStateThreadSafety:
    def test_concurrent_manage_different_types(self):
        """Multiple threads managing different types should not race."""
        state = AppState()
        types_and_instances = [
            (type(f"Type{i}", (), {}), type(f"Type{i}", (), {})())
            for i in range(20)
        ]

        barrier = threading.Barrier(20)

        def manage_one(cls, instance):
            barrier.wait()
            state.manage(instance)

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [
                pool.submit(manage_one, cls, inst)
                for cls, inst in types_and_instances
            ]
            for f in futures:
                f.result()

        assert len(state) == 20

    def test_concurrent_get(self):
        """Multiple threads getting the same type concurrently."""
        state = AppState()
        db = Database("sqlite:///test.db")
        state.manage(db)

        results = []
        barrier = threading.Barrier(50)

        def get_db():
            barrier.wait()
            result = state.get(Database)
            results.append(result)

        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = [pool.submit(get_db) for _ in range(50)]
            for f in futures:
                f.result()

        assert len(results) == 50
        assert all(r is db for r in results)

    def test_concurrent_has_and_get(self):
        """Mixed has() and get() calls should be thread-safe."""
        state = AppState()
        state.manage(Database("test"))

        errors = []
        barrier = threading.Barrier(100)

        def mixed_ops(i):
            barrier.wait()
            try:
                if i % 2 == 0:
                    assert state.has(Database)
                else:
                    db = state.get(Database)
                    assert db.url == "test"
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=100) as pool:
            futures = [pool.submit(mixed_ops, i) for i in range(100)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errors: {errors}"


# ─── Bridge Integration ───

class TestAppStateInjection:
    def test_state_injected_into_command(self):
        """Commands with a 'state' parameter should receive AppState."""
        from forge.bridge import IPCBridge
        import json

        class MockApp:
            def __init__(self):
                self.state = AppState()
                self.config = None

        app = MockApp()
        db = Database("sqlite:///inject.db")
        app.state.manage(db)

        bridge = IPCBridge(app)

        captured = {}

        def my_command(name: str, state: AppState) -> str:
            captured["state"] = state
            captured["db"] = state.get(Database)
            return f"Hello, {name}!"

        bridge.register_command("my_command", my_command)

        result_json = bridge.invoke_command(json.dumps({
            "id": "test-1",
            "command": "my_command",
            "args": {"name": "Alice"},
        }))

        result = json.loads(result_json)
        assert result["error"] is None
        assert result["result"] == "Hello, Alice!"
        assert captured["state"] is app.state
        assert captured["db"].url == "sqlite:///inject.db"

    def test_no_state_no_injection(self):
        """Commands without 'state' parameter should work normally."""
        from forge.bridge import IPCBridge
        import json

        class MockApp:
            def __init__(self):
                self.state = AppState()
                self.config = None

        app = MockApp()
        bridge = IPCBridge(app)

        def simple_command(name: str) -> str:
            return f"Hi, {name}!"

        bridge.register_command("simple_command", simple_command)

        result_json = bridge.invoke_command(json.dumps({
            "id": "test-2",
            "command": "simple_command",
            "args": {"name": "Bob"},
        }))

        result = json.loads(result_json)
        assert result["error"] is None
        assert result["result"] == "Hi, Bob!"
