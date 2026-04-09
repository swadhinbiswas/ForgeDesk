"""Tests for SystemAPI, AutostartAPI, and LifecycleAPI (low coverage modules)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest


# ─── SystemAPI Tests ───

class TestSystemAPI:

    def test_get_version(self):
        from forge.api.system import SystemAPI
        api = SystemAPI(app_name="Test", app_version="1.2.3")
        assert api.get_version() == "1.2.3"
        assert api.version() == "1.2.3"

    def test_get_platform(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        plat = api.get_platform()
        assert plat in {"linux", "macos", "windows"} or isinstance(plat, str)
        assert api.platform() == plat

    def test_get_info(self):
        from forge.api.system import SystemAPI
        api = SystemAPI(app_name="TestApp", app_version="2.0.0")
        info = api.get_info()
        assert info["app_name"] == "TestApp"
        assert info["app_version"] == "2.0.0"
        assert "os" in info
        assert "python_version" in info
        assert "architecture" in info
        assert "free_threaded" in info
        assert api.info() == info

    def test_get_env(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        os.environ["FORGE_TEST_VAR"] = "hello"
        assert api.get_env("FORGE_TEST_VAR") == "hello"
        assert api.get_env("NONEXISTENT_VAR_XYZ") is None
        assert api.get_env("NONEXISTENT_VAR_XYZ", "default") == "default"
        del os.environ["FORGE_TEST_VAR"]

    def test_get_cwd(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        cwd = api.get_cwd()
        assert os.path.isdir(cwd)

    def test_exit_app(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        with pytest.raises(SystemExit):
            api.exit_app()

    def test_exit_alias(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        with pytest.raises(SystemExit):
            api.exit()

    def test_open_url(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        with patch("forge.api.system.webbrowser.open") as mock_open:
            api.open_url("https://example.com")
            mock_open.assert_called_once_with("https://example.com")

    def test_open_file_linux(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        with patch.object(api, "get_platform", return_value="linux"), \
             patch("forge.api.system.subprocess.run") as mock_run:
            api.open_file("/tmp/test.txt")
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0][0] == "xdg-open"

    def test_platform_mapping(self):
        from forge.api.system import SystemAPI
        api = SystemAPI()
        with patch("forge.api.system.platform.system", return_value="Darwin"):
            assert api.get_platform() == "macos"
        with patch("forge.api.system.platform.system", return_value="Windows"):
            assert api.get_platform() == "windows"
        with patch("forge.api.system.platform.system", return_value="Linux"):
            assert api.get_platform() == "linux"
        with patch("forge.api.system.platform.system", return_value="FreeBSD"):
            assert api.get_platform() == "freebsd"


# ─── AutostartAPI Tests ───

def _make_app(has_capability: bool = True):
    app = MagicMock()
    app.config.app.name = "TestApp"
    app.has_capability.return_value = has_capability
    return app


class TestAutostartCapability:

    def test_enable_requires_capability(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app(has_capability=False)
        mock_core = MagicMock()
        mock_core.AutoLaunchManager = None
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
        with pytest.raises(PermissionError, match="autostart"):
            api.enable()

    def test_disable_requires_capability(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app(has_capability=False)
        mock_core = MagicMock()
        mock_core.AutoLaunchManager = None
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
        with pytest.raises(PermissionError, match="autostart"):
            api.disable()

    def test_is_enabled_requires_capability(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app(has_capability=False)
        mock_core = MagicMock()
        mock_core.AutoLaunchManager = None
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
        with pytest.raises(PermissionError, match="autostart"):
            api.is_enabled()


class TestAutostartOperations:

    def test_enable_with_manager(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.enable.return_value = True
        mock_core = MagicMock()
        mock_core.AutoLaunchManager.return_value = mock_manager
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api.enable() is True

    def test_disable_with_manager(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.disable.return_value = True
        mock_core = MagicMock()
        mock_core.AutoLaunchManager.return_value = mock_manager
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api.disable() is True

    def test_is_enabled_with_manager(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.is_enabled.return_value = True
        mock_core = MagicMock()
        mock_core.AutoLaunchManager.return_value = mock_manager
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api.is_enabled() is True

    def test_enable_without_manager(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.AutoLaunchManager = None
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api.enable() is False

    def test_enable_manager_exception(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.enable.side_effect = RuntimeError("fail")
        mock_core = MagicMock()
        mock_core.AutoLaunchManager.return_value = mock_manager
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api.enable() is False

    def test_manager_init_failure(self):
        from forge.api.autostart import AutostartAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.AutoLaunchManager.side_effect = RuntimeError("init fail")
        with patch("forge.api.autostart.forge_core", mock_core):
            api = AutostartAPI(app)
            assert api._manager is None


# ─── LifecycleAPI Tests ───

class TestLifecycleCapability:

    def test_single_instance_requires_capability(self):
        from forge.api.lifecycle import LifecycleAPI
        app = _make_app(has_capability=False)
        api = LifecycleAPI(app)
        with pytest.raises(PermissionError, match="lifecycle"):
            api.request_single_instance_lock()

    def test_relaunch_requires_capability(self):
        from forge.api.lifecycle import LifecycleAPI
        app = _make_app(has_capability=False)
        api = LifecycleAPI(app)
        with pytest.raises(PermissionError, match="lifecycle"):
            api.relaunch()


class TestLifecycleOperations:

    def test_single_instance_lock(self):
        from forge.api.lifecycle import LifecycleAPI
        app = _make_app()
        mock_guard = MagicMock()
        mock_guard.is_single.return_value = True
        mock_core = MagicMock()
        mock_core.SingleInstanceGuard.return_value = mock_guard

        mock_core.SingleInstanceGuard.return_value = mock_guard
        
        # Test 1: Successful lock with default name
        app.config.app.name = "TestApp"
        with patch.dict("sys.modules", {"forge": MagicMock(forge_core=mock_core)}):
            api = LifecycleAPI(app)
            assert api.request_single_instance_lock() is True
            mock_core.SingleInstanceGuard.assert_called_with("TestApp")

        # Test 2: Custom name and lock fails (is_single = False)
        mock_guard.is_single.return_value = False
        with patch.dict("sys.modules", {"forge": MagicMock(forge_core=mock_core)}):
            api = LifecycleAPI(app)
            assert api.request_single_instance_lock("MyCustomId") is False
            mock_core.SingleInstanceGuard.assert_called_with("MyCustomId")

    def test_relaunch(self):
        from forge.api.lifecycle import LifecycleAPI
        app = _make_app()
        api = LifecycleAPI(app)
        
        with patch("subprocess.Popen") as mock_popen, \
             patch("sys.exit") as mock_exit:
            api.relaunch()
            mock_popen.assert_called_once()
            mock_exit.assert_called_once_with(0)
