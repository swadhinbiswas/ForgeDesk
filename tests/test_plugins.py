"""Tests for Forge plugin system — loading, capabilities, lifecycle, and dependencies."""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from forge.plugins import PluginManager, PluginRecord, _check_version_constraint, _version_key


# ─── Helpers ───


def _make_mock_app(capabilities: set[str] | None = None) -> MagicMock:
    """Create a mock ForgeApp with configurable capabilities."""
    app = MagicMock()
    caps = capabilities or {"fs", "clipboard", "shell", "dialog", "notification", "updater", "global_shortcut", "screen"}

    def has_capability(cap: str) -> bool:
        return cap in caps

    app.has_capability = has_capability
    app.config.config_path = None
    return app


def _make_config(enabled: bool = True, modules: list[str] | None = None, paths: list[str] | None = None) -> MagicMock:
    config = MagicMock()
    config.enabled = enabled
    config.modules = modules or []
    config.paths = paths or []
    return config


def _make_plugin_file(tmp_path: Path, name: str, content: str) -> Path:
    plugin_file = tmp_path / f"{name}.py"
    plugin_file.write_text(textwrap.dedent(content))
    return plugin_file


# ─── PluginRecord ───


class TestPluginRecord:
    def test_snapshot_basic(self):
        record = PluginRecord(name="test", module="test_module")
        snap = record.snapshot()
        assert snap["name"] == "test"
        assert snap["loaded"] is False
        assert snap["capabilities"] == []

    def test_snapshot_with_capabilities(self):
        record = PluginRecord(
            name="test",
            module="mod",
            loaded=True,
            capabilities=["fs", "clipboard"],
            has_on_ready=True,
        )
        snap = record.snapshot()
        assert snap["capabilities"] == ["fs", "clipboard"]
        assert snap["has_on_ready"] is True
        assert snap["has_on_shutdown"] is False


# ─── Version Checking ───


class TestVersionChecking:
    def test_version_key_parsing(self):
        assert _version_key("1.2.3") == (1, 2, 3)
        assert _version_key("0.1.0") == (0, 1, 0)
        assert _version_key("10.20.30") == (10, 20, 30)

    def test_gte_constraint(self):
        assert _check_version_constraint(">=0.1.0", "0.1.0") is True
        assert _check_version_constraint(">=0.1.0", "0.2.0") is True
        assert _check_version_constraint(">=0.2.0", "0.1.0") is False

    def test_gt_constraint(self):
        assert _check_version_constraint(">0.1.0", "0.2.0") is True
        assert _check_version_constraint(">0.1.0", "0.1.0") is False

    def test_lte_constraint(self):
        assert _check_version_constraint("<=1.0.0", "0.9.0") is True
        assert _check_version_constraint("<=1.0.0", "1.0.0") is True
        assert _check_version_constraint("<=1.0.0", "1.0.1") is False

    def test_eq_constraint(self):
        assert _check_version_constraint("==1.0.0", "1.0.0") is True
        assert _check_version_constraint("==1.0.0", "1.0.1") is False

    def test_bare_version_treated_as_gte(self):
        assert _check_version_constraint("0.1.0", "0.1.0") is True
        assert _check_version_constraint("0.1.0", "0.2.0") is True


# ─── Plugin Loading ___


class TestPluginLoading:
    def test_disabled_returns_empty(self):
        app = _make_mock_app()
        config = _make_config(enabled=False)
        pm = PluginManager(app, config)
        assert pm.load_all() == []
        assert pm.enabled is False

    def test_load_from_file(self, tmp_path):
        plugin_file = _make_plugin_file(tmp_path, "hello_plugin", """
            __forge_plugin__ = {"name": "hello", "version": "1.0.0"}

            def register(app):
                app._hello_registered = True
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(plugin_file)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert len(result) == 1
        assert result[0]["name"] == "hello"
        assert result[0]["loaded"] is True

    def test_load_from_directory(self, tmp_path):
        _make_plugin_file(tmp_path, "plugin_a", """
            __forge_plugin__ = {"name": "plugin-a"}
            def register(app): pass
        """)
        _make_plugin_file(tmp_path, "plugin_b", """
            __forge_plugin__ = {"name": "plugin-b"}
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "plugin-a" in names
        assert "plugin-b" in names

    def test_load_missing_register_fails(self, tmp_path):
        plugin_file = _make_plugin_file(tmp_path, "bad_plugin", """
            __forge_plugin__ = {"name": "bad"}
            # Missing register() function
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(plugin_file)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert len(result) == 1
        assert result[0]["loaded"] is False
        assert "must define register" in result[0]["error"]

    def test_load_missing_path(self):
        app = _make_mock_app()
        config = _make_config(paths=["/nonexistent/plugin.py"])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert len(result) == 1
        assert result[0]["loaded"] is False
        assert "not found" in result[0]["error"]

    def test_summary(self, tmp_path):
        _make_plugin_file(tmp_path, "good", """
            __forge_plugin__ = {"name": "good"}
            def register(app): pass
        """)
        _make_plugin_file(tmp_path, "bad", """
            __forge_plugin__ = {"name": "bad"}
            # no register
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        summary = pm.summary()
        assert summary["enabled"] is True
        assert summary["loaded"] == 1
        assert summary["failed"] == 1

    def test_get_plugin(self, tmp_path):
        _make_plugin_file(tmp_path, "finder", """
            __forge_plugin__ = {"name": "finder", "version": "2.0"}
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        found = pm.get_plugin("finder")
        assert found is not None
        assert found["version"] == "2.0"
        assert pm.get_plugin("nonexistent") is None


# ─── Capability Enforcement ───


class TestCapabilityEnforcement:
    def test_plugin_with_granted_capabilities(self, tmp_path):
        _make_plugin_file(tmp_path, "fs_plugin", """
            __forge_plugin__ = {
                "name": "fs-helper",
                "capabilities": ["fs"],
            }
            def register(app): pass
        """)
        app = _make_mock_app(capabilities={"fs"})
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is True
        assert result[0]["capabilities"] == ["fs"]

    def test_plugin_denied_capability(self, tmp_path):
        _make_plugin_file(tmp_path, "sneaky", """
            __forge_plugin__ = {
                "name": "sneaky",
                "capabilities": ["shell"],
            }
            def register(app): pass
        """)
        app = _make_mock_app(capabilities={"fs"})  # no shell!
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is False
        assert "capability" in result[0]["error"].lower()

    def test_plugin_multiple_capabilities_partial_deny(self, tmp_path):
        _make_plugin_file(tmp_path, "multi", """
            __forge_plugin__ = {
                "name": "multi",
                "capabilities": ["fs", "clipboard", "shell"],
            }
            def register(app): pass
        """)
        app = _make_mock_app(capabilities={"fs", "clipboard"})  # no shell
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is False


# ─── Lifecycle Hooks ───


class TestLifecycleHooks:
    def test_on_ready_called(self, tmp_path):
        _make_plugin_file(tmp_path, "lifecycle", """
            __forge_plugin__ = {"name": "lifecycle"}
            ready_called = False

            def register(app): pass

            def on_ready(app):
                global ready_called
                ready_called = True
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        assert pm._records[0].has_on_ready is True
        pm.on_ready()
        assert pm._ready_called is True

    def test_on_shutdown_called(self, tmp_path):
        _make_plugin_file(tmp_path, "shutdowner", """
            __forge_plugin__ = {"name": "shutdowner"}
            def register(app): pass
            def on_shutdown(app):
                app._shutdown_marker = True
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        assert pm._records[0].has_on_shutdown is True
        pm.on_shutdown()
        assert pm._shutdown_called is True

    def test_on_ready_idempotent(self, tmp_path):
        _make_plugin_file(tmp_path, "idem", """
            __forge_plugin__ = {"name": "idem"}
            call_count = 0
            def register(app): pass
            def on_ready(app):
                global call_count
                call_count += 1
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        pm.on_ready()
        pm.on_ready()  # should be no-op
        assert pm._ready_called is True

    def test_on_ready_error_does_not_crash(self, tmp_path):
        _make_plugin_file(tmp_path, "crasher", """
            __forge_plugin__ = {"name": "crasher"}
            def register(app): pass
            def on_ready(app):
                raise ValueError("boom")
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        pm.load_all()
        # Should not raise
        pm.on_ready()
        assert pm._ready_called is True

    def test_lifecycle_flags_in_snapshot(self, tmp_path):
        _make_plugin_file(tmp_path, "flags", """
            __forge_plugin__ = {"name": "flags"}
            def register(app): pass
            def on_ready(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["has_on_ready"] is True
        assert result[0]["has_on_shutdown"] is False


# ─── Version Constraints ───


class TestVersionConstraints:
    def test_compatible_version(self, tmp_path):
        _make_plugin_file(tmp_path, "compat", """
            __forge_plugin__ = {
                "name": "compat",
                "forge_version": ">=0.1.0",
            }
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is True

    def test_incompatible_version(self, tmp_path):
        _make_plugin_file(tmp_path, "future", """
            __forge_plugin__ = {
                "name": "future",
                "forge_version": ">=99.0.0",
            }
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is False
        assert "version" in result[0]["error"].lower()


# ─── Namespace & Dependencies ───


class TestNamespaceAndDependencies:
    def test_duplicate_name_rejected(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        _make_plugin_file(dir_a, "dup", """
            __forge_plugin__ = {"name": "duplicate"}
            def register(app): pass
        """)
        _make_plugin_file(dir_b, "dup2", """
            __forge_plugin__ = {"name": "duplicate"}
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(dir_a), str(dir_b)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        loaded = [r for r in result if r["loaded"]]
        failed = [r for r in result if not r["loaded"]]
        assert len(loaded) == 1
        assert len(failed) == 1
        assert "collision" in failed[0]["error"].lower()

    def test_missing_dependency_warned(self, tmp_path):
        _make_plugin_file(tmp_path, "dependent", """
            __forge_plugin__ = {
                "name": "dependent",
                "depends": ["missing-plugin"],
            }
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is True  # still loads
        assert result[0]["error"] is not None  # but warns
        assert "missing dependency" in result[0]["error"]

    def test_satisfied_dependency(self, tmp_path):
        _make_plugin_file(tmp_path, "base", """
            __forge_plugin__ = {"name": "base"}
            def register(app): pass
        """)
        _make_plugin_file(tmp_path, "child", """
            __forge_plugin__ = {
                "name": "child",
                "depends": ["base"],
            }
            def register(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        loaded = [r for r in result if r["loaded"]]
        assert len(loaded) == 2
        child = next(r for r in result if r["name"] == "child")
        assert child["error"] is None  # dependency satisfied

    def test_using_setup_instead_of_register(self, tmp_path):
        _make_plugin_file(tmp_path, "setuponly", """
            __forge_plugin__ = {"name": "setup-style"}
            def setup(app): pass
        """)
        app = _make_mock_app()
        config = _make_config(paths=[str(tmp_path)])
        pm = PluginManager(app, config)
        result = pm.load_all()
        assert result[0]["loaded"] is True
