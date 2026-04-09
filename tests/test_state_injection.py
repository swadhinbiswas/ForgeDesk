"""
Tests for Forge State Injection (Phase 13).

Tests that the IPC bridge auto-injects managed state into command
handlers based on:
1. Named 'state' parameter → injects AppState container
2. Type-hinted parameter → injects specific managed instance
3. Multiple type-hinted params → all injected correctly
4. Missing managed type → parameter left unset (caller provides or error)
5. IPC-provided args take priority over injection
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from forge.bridge import IPCBridge
from forge.state import AppState


# ─── Test service classes ───

class Database:
    """Mock database service."""
    def __init__(self, url: str = "sqlite:///:memory:"):
        self.url = url

    def query(self, sql: str) -> list:
        return [{"id": 1, "sql": sql}]


class CacheService:
    """Mock cache service."""
    def __init__(self, ttl: int = 300):
        self.ttl = ttl

    def get(self, key: str) -> str | None:
        return None


class AuthService:
    """Mock auth service."""
    def __init__(self, secret: str = "test-secret"):
        self.secret = secret


# ─── Fixtures ───

@pytest.fixture
def state():
    """Create an AppState with managed services."""
    s = AppState()
    s.manage(Database("sqlite:///test.db"))
    s.manage(CacheService(ttl=60))
    return s


@pytest.fixture
def app_with_state(state):
    """Create a mock app with state container."""
    app = MagicMock()
    app.state = state
    app.config.permissions = MagicMock()
    return app


@pytest.fixture
def bridge(app_with_state):
    """Create a bridge attached to an app with state."""
    return IPCBridge(app=app_with_state)


# ─── Container Injection (named 'state') ───

class TestContainerInjection:

    def test_inject_state_by_name(self, bridge, state):
        """Parameter named 'state' receives the full AppState container."""
        def handler(state):
            return len(state)

        result = bridge._inject_state(handler, {})
        assert result["state"] is state

    def test_inject_state_by_name_with_other_args(self, bridge, state):
        """'state' injection works alongside other IPC args."""
        def handler(name: str, state):
            return f"{name}: {len(state)}"

        result = bridge._inject_state(handler, {"name": "test"})
        assert result["state"] is state
        assert result["name"] == "test"

    def test_state_not_injected_if_provided(self, bridge):
        """IPC-provided 'state' takes priority over injection."""
        def handler(state):
            return state

        custom_state = {"custom": True}
        result = bridge._inject_state(handler, {"state": custom_state})
        assert result["state"] is custom_state


# ─── Typed Injection ───

class TestTypedInjection:

    def test_inject_single_typed(self, bridge):
        """A single type-hinted param gets the managed instance."""
        def handler(db: Database) -> list:
            return db.query("SELECT 1")

        result = bridge._inject_state(handler, {})
        assert isinstance(result["db"], Database)
        assert result["db"].url == "sqlite:///test.db"

    def test_inject_multiple_typed(self, bridge):
        """Multiple type-hinted params all get injected."""
        def handler(db: Database, cache: CacheService) -> dict:
            return {"db": db.url, "ttl": cache.ttl}

        result = bridge._inject_state(handler, {})
        assert isinstance(result["db"], Database)
        assert isinstance(result["cache"], CacheService)
        assert result["cache"].ttl == 60

    def test_typed_with_ipc_args(self, bridge):
        """Typed injection works alongside normal IPC arguments."""
        def handler(user_id: int, db: Database) -> dict:
            return {"user_id": user_id, "url": db.url}

        result = bridge._inject_state(handler, {"user_id": 42})
        assert result["user_id"] == 42
        assert isinstance(result["db"], Database)

    def test_unmanaged_type_not_injected(self, bridge):
        """Types not in AppState are not injected (left for caller)."""
        def handler(auth: AuthService) -> str:
            return auth.secret

        result = bridge._inject_state(handler, {})
        assert "auth" not in result

    def test_appstate_typed_hint(self, bridge, state):
        """Parameter typed as AppState gets the container."""
        def handler(my_state: AppState) -> int:
            return len(my_state)

        result = bridge._inject_state(handler, {})
        assert result["my_state"] is state

    def test_ipc_arg_overrides_typed_injection(self, bridge):
        """IPC-provided args take priority over typed injection."""
        custom_db = Database("sqlite:///override.db")

        def handler(db: Database) -> str:
            return db.url

        result = bridge._inject_state(handler, {"db": custom_db})
        assert result["db"] is custom_db
        assert result["db"].url == "sqlite:///override.db"


# ─── Edge Cases ───

class TestInjectionEdgeCases:

    def test_no_app_returns_args_unchanged(self):
        """Bridge without app should return args unchanged."""
        bridge = IPCBridge(app=None)

        def handler(db: Database) -> str:
            return db.url

        result = bridge._inject_state(handler, {"key": "value"})
        assert result == {"key": "value"}

    def test_no_state_returns_args_unchanged(self):
        """Bridge with app but no state returns args unchanged."""
        app = MagicMock(spec=[])  # No 'state' attribute
        bridge = IPCBridge(app=app)

        def handler(db: Database) -> str:
            return db.url

        result = bridge._inject_state(handler, {"key": "value"})
        assert result == {"key": "value"}

    def test_lambda_without_hints(self, bridge):
        """Lambdas without type hints should not crash."""
        handler = lambda x: x * 2  # noqa: E731

        result = bridge._inject_state(handler, {"x": 5})
        assert result == {"x": 5}

    def test_builtin_function_no_crash(self, bridge):
        """Built-in functions should not crash the injector."""
        result = bridge._inject_state(len, {"obj": [1, 2, 3]})
        # Should return args unchanged since we can't inspect builtins
        assert "obj" in result

    def test_function_with_no_params(self, bridge):
        """Functions with no params return empty args."""
        def handler() -> str:
            return "hello"

        result = bridge._inject_state(handler, {})
        assert result == {}


# ─── Integration: Execute with Injection ───

class TestExecuteWithInjection:

    def test_execute_command_with_typed_injection(self, bridge):
        """Full _execute_command pipeline with typed injection."""
        def get_db_url(db: Database) -> str:
            return db.url

        result = bridge._execute_command(get_db_url, {})
        assert result == "sqlite:///test.db"

    def test_execute_command_with_container_injection(self, bridge, state):
        """Full _execute_command pipeline with container injection."""
        def count_services(state) -> int:
            return len(state)

        result = bridge._execute_command(count_services, {})
        assert result == 2  # Database + CacheService

    def test_execute_mixed_injection_and_args(self, bridge):
        """Full pipeline with both typed injection and IPC args."""
        def query_user(user_id: int, db: Database) -> dict:
            return {"user_id": user_id, "db": db.url}

        result = bridge._execute_command(query_user, {"user_id": 42})
        assert result == {"user_id": 42, "db": "sqlite:///test.db"}
