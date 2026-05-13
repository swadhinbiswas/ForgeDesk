"""
Tests for the Forge Command Router.

Verifies that the decoupled routing system correctly manages IPC command registration
and correctly preserves capability and version metadata without relying on global state.
"""

from unittest.mock import MagicMock

from forge.app import ForgeApp
from forge.router import Router


def test_router_initialization():
    """Test that a Router initializes gracefully with or without a prefix."""
    r1 = Router()
    assert r1.prefix == ""
    assert r1.commands == {}

    r2 = Router(prefix="plugin")
    assert r2.prefix == "plugin"


def test_router_command_basic_registration():
    """Test standard command registration on a router."""
    router = Router()

    @router.command()
    def my_command():
        return "ok"

    assert "my_command" in router.commands
    func = router.commands["my_command"]

    assert func() == "ok"
    assert getattr(func, "_forge_version", None) == "1.0"
    assert not hasattr(func, "_forge_capability")


def test_router_command_custom_name():
    """Test command registration with an explicit name override."""
    router = Router()

    @router.command(name="custom_api_call")
    def original_function_name():
        pass

    assert "custom_api_call" in router.commands
    assert "original_function_name" not in router.commands


def test_router_command_prefix_namespace():
    """Test that commands get prefixed when a router has a namespace."""
    router = Router(prefix="sys")

    @router.command()
    def ping():
        pass

    @router.command(name="info")
    def get_info():
        pass

    assert "sys:ping" in router.commands
    assert "sys:info" in router.commands


def test_router_capability_metadata():
    """Test that capability metadata is correctly attached."""
    router = Router()

    @router.command(capability="filesystem")
    def read_file():
        pass

    func = router.commands["read_file"]
    assert getattr(func, "_forge_capability", None) == "filesystem"


def test_router_version_metadata():
    """Test that version metadata is correctly attached."""
    router = Router()

    @router.command(version="2.0")
    def next_gen_api():
        pass

    func = router.commands["next_gen_api"]
    assert getattr(func, "_forge_version", None) == "2.0"


def test_app_include_router():
    """Test that ForgeApp correctly merges commands from a Router."""
    app = ForgeApp.__new__(ForgeApp)

    # Mock the bridge so we can track registrations natively
    app.bridge = MagicMock()

    router = Router(prefix="math")

    @router.command()
    def add(a, b):
        return a + b

    @router.command()
    def subtract(a, b):
        return a - b

    # Include the router into the app
    app.include_router(router)

    # Prove bridge.register_command was called for both router endpoints
    app.bridge.register_command.assert_any_call(
        "math:add", router.commands["math:add"], capability=None, version="1.0", internal=False
    )
    app.bridge.register_command.assert_any_call(
        "math:subtract",
        router.commands["math:subtract"],
        capability=None,
        version="1.0",
        internal=False,
    )

    assert app.bridge.register_command.call_count == 2
