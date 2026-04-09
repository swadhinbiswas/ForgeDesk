"""Tests for Keychain API (21% → 80%+ coverage)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock
import pytest


def _make_app(has_capability: bool = True):
    app = MagicMock()
    app.config.app.name = "TestApp"
    app.has_capability.return_value = has_capability
    return app


class TestKeychainCapability:

    def test_set_password_requires_capability(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app(has_capability=False)
        with patch("forge.api.keychain.forge_core", create=True):
            api = KeychainAPI(app)
        with pytest.raises(PermissionError, match="keychain"):
            api.set_password("key", "secret")

    def test_get_password_requires_capability(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app(has_capability=False)
        with patch("forge.api.keychain.forge_core", create=True):
            api = KeychainAPI(app)
        with pytest.raises(PermissionError, match="keychain"):
            api.get_password("key")

    def test_delete_password_requires_capability(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app(has_capability=False)
        with patch("forge.api.keychain.forge_core", create=True):
            api = KeychainAPI(app)
        with pytest.raises(PermissionError, match="keychain"):
            api.delete_password("key")


class TestKeychainOperations:

    def test_set_password_with_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_core = MagicMock()
        mock_core.KeychainManager.return_value = mock_manager
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            result = api.set_password("key", "secret")
        assert result is True
        mock_manager.set_password.assert_called_once_with("key", "secret")

    def test_get_password_with_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.get_password.return_value = "secret"
        mock_core = MagicMock()
        mock_core.KeychainManager.return_value = mock_manager
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            result = api.get_password("key")
        assert result == "secret"

    def test_delete_password_with_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_core = MagicMock()
        mock_core.KeychainManager.return_value = mock_manager
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            result = api.delete_password("key")
        assert result is True

    def test_set_password_without_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.KeychainManager = None
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            assert api.set_password("key", "s") is False

    def test_get_password_without_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.KeychainManager = None
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            assert api.get_password("key") is None

    def test_delete_password_without_manager(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.KeychainManager = None
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            assert api.delete_password("key") is False

    def test_manager_exception_returns_false(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_manager = MagicMock()
        mock_manager.set_password.side_effect = RuntimeError("fail")
        mock_core = MagicMock()
        mock_core.KeychainManager.return_value = mock_manager
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            assert api.set_password("k", "v") is False

    def test_manager_init_failure(self):
        from forge.api.keychain import KeychainAPI
        app = _make_app()
        mock_core = MagicMock()
        mock_core.KeychainManager.side_effect = RuntimeError("init fail")
        with patch("forge.api.keychain.forge_core", mock_core):
            api = KeychainAPI(app)
            assert api._manager is None
