"""
Tests for Forge Configuration Module.

Tests loading, validation, and error handling for forge.toml configuration.
"""

import pytest
import tempfile
from pathlib import Path

from forge.config import ForgeConfig, ConfigValidationError


class TestForgeConfig:
    """Tests for ForgeConfig class."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading a valid configuration file."""
        config_content = """
[app]
name = "Test App"
version = "1.0.0"
description = "A test application"
authors = ["Test Author"]

[window]
title = "Test Window"
width = 800
height = 600

[build]
entry = "src/main.py"
output_dir = "dist"

[dev]
frontend_dir = "src/frontend"
port = 3000
dev_server_command = "npm run dev"
dev_server_url = "http://127.0.0.1:5173"
dev_server_timeout = 15

[permissions]
filesystem = true
clipboard = false
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)

        assert config.app.name == "Test App"
        assert config.app.version == "1.0.0"
        assert config.window.width == 800
        assert config.window.height == 600
        assert config.dev.port == 3000
        assert config.dev.dev_server_command == "npm run dev"
        assert config.dev.dev_server_url == "http://127.0.0.1:5173"
        assert config.dev.dev_server_timeout == 15
        assert config.permissions.filesystem is True
        assert config.permissions.clipboard is False

    def test_load_missing_file(self) -> None:
        """Test that loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ForgeConfig.from_file("/nonexistent/path/forge.toml")

    def test_load_invalid_toml(self, tmp_path: Path) -> None:
        """Test that invalid TOML raises an error."""
        config_file = tmp_path / "forge.toml"
        config_file.write_text("invalid toml {{{")

        with pytest.raises(Exception):  # tomllib.TOMLDecodeError
            ForgeConfig.from_file(config_file)

    def test_window_width_validation(self, tmp_path: Path) -> None:
        """Test that window width is validated."""
        config_content = """
[window]
width = -100
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_window_width_too_large(self, tmp_path: Path) -> None:
        """Test that excessively large window width is rejected."""
        config_content = """
[window]
width = 99999
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_port_validation(self, tmp_path: Path) -> None:
        """Test that port number is validated."""
        config_content = """
[dev]
port = 99999
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_min_width_greater_than_width(self, tmp_path: Path) -> None:
        """Test that min_width > width raises validation error."""
        config_content = """
[window]
width = 400
height = 300
min_width = 800
min_height = 200
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_find_and_load(self, tmp_path: Path) -> None:
        """Test finding config file by searching parent directories."""
        config_content = """
[app]
name = "Parent Config Test"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        # Create subdirectory
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        # Should find config in parent
        config = ForgeConfig.find_and_load(subdir)
        assert config.app.name == "Parent Config Test"

    def test_find_and_load_not_found(self, tmp_path: Path) -> None:
        """Test that find_and_load raises error when config not found."""
        with pytest.raises(FileNotFoundError):
            ForgeConfig.find_and_load(tmp_path)

    def test_default_values(self, tmp_path: Path) -> None:
        """Test that default values are applied correctly."""
        config_content = """
[app]
name = "Minimal Config"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)

        assert config.app.version == "1.0.0"
        assert config.window.width == 1200
        assert config.window.height == 800
        assert config.dev.hot_reload is True
        assert config.permissions.filesystem is True

    def test_get_base_dir(self, tmp_path: Path) -> None:
        """Test getting the base directory."""
        config_file = tmp_path / "forge.toml"
        config_file.write_text("[app]\nname = 'Test'")

        config = ForgeConfig.from_file(config_file)
        assert config.get_base_dir() == tmp_path

    def test_get_entry_path(self, tmp_path: Path) -> None:
        """Test getting the entry point path."""
        config_content = """
[build]
entry = "src/main.py"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)
        assert config.get_entry_path() == tmp_path / "src" / "main.py"

    def test_get_frontend_path(self, tmp_path: Path) -> None:
        """Test getting the frontend directory path."""
        config_content = """
[dev]
frontend_dir = "web/app"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)
        assert config.get_frontend_path() == tmp_path / "web" / "app"

    def test_load_updater_config(self, tmp_path: Path) -> None:
        """Test loading updater permissions and config."""
        config_content = """
[permissions]
updater = true

[updater]
enabled = true
endpoint = "https://updates.example.com/manifest.json"
channel = "beta"
check_on_startup = true
allow_downgrade = false
public_key = "test-public-key"
require_signature = true
staging_dir = ".forge-updater-state"
install_dir = "dist/current"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)

        assert config.permissions.updater is True
        assert config.updater.enabled is True
        assert config.updater.endpoint == "https://updates.example.com/manifest.json"
        assert config.updater.channel == "beta"
        assert config.updater.check_on_startup is True
        assert config.updater.allow_downgrade is False
        assert config.updater.public_key == "test-public-key"
        assert config.updater.require_signature is True
        assert config.updater.staging_dir == ".forge-updater-state"
        assert config.updater.install_dir == "dist/current"

    def test_invalid_updater_channel_raises_validation_error(self, tmp_path: Path) -> None:
        """Test that unsupported updater channels are rejected."""
        config_content = """
[updater]
enabled = true
channel = "canary"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_invalid_dev_server_url_raises_validation_error(self, tmp_path: Path) -> None:
        """Test that invalid dev server URLs are rejected."""
        config_content = """
[dev]
dev_server_url = "ws://localhost:5173"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_load_protocol_packaging_and_signing_config(self, tmp_path: Path) -> None:
        """Test protocol handler, packaging, signing, and notification settings."""
        config_content = """
[permissions]
notifications = false

[protocol]
schemes = ["forge", "forge-notes"]

[packaging]
app_id = "dev.forge.notes"
product_name = "Forge Notes"
formats = ["dir", "appimage"]
category = "Utility"

[signing]
enabled = true
adapter = "codesign"
identity = "Developer ID"
verify_command = "codesign --verify"
timestamp_url = "https://timestamp.example.com"
"""
        config_file = tmp_path / "forge.toml"
        config_file.write_text(config_content)

        config = ForgeConfig.from_file(config_file)

        assert config.permissions.notifications is False
        assert config.protocol.schemes == ["forge", "forge-notes"]
        assert config.packaging.app_id == "dev.forge.notes"
        assert config.packaging.formats == ["dir", "appimage"]
        assert config.signing.enabled is True
        assert config.signing.adapter == "codesign"
        assert config.signing.identity == "Developer ID"
        assert config.signing.timestamp_url == "https://timestamp.example.com"

    def test_invalid_protocol_scheme_raises_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[protocol]\nschemes = ["HTTP"]\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_notarize_requires_signing_enabled(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[signing]\nnotarize = true\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_invalid_signing_adapter_raises_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[signing]\nenabled = true\nadapter = "unknown"\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_load_security_and_plugin_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text(
            """
[security]
allowed_commands = ["greet", "version"]
denied_commands = ["delete"]
expose_command_introspection = false
allowed_origins = ["https://app.example.com"]

[security.window_scopes]
main = ["filesystem", "dialogs"]
settings = ["clipboard"]

[plugins]
enabled = true
modules = ["forge_plugins.demo"]
paths = ["plugins"]
"""
        )

        config = ForgeConfig.from_file(config_file)

        assert config.security.allowed_commands == ["greet", "version"]
        assert config.security.denied_commands == ["delete"]
        assert config.security.expose_command_introspection is False
        assert config.security.allowed_origins == ["https://app.example.com"]
        assert config.security.window_scopes == {
            "main": ["filesystem", "dialogs"],
            "settings": ["clipboard"],
        }
        assert config.plugins.enabled is True
        assert config.plugins.modules == ["forge_plugins.demo"]
        assert config.plugins.paths == ["plugins"]

    def test_invalid_security_command_name_raises_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[security]\nallowed_commands = ["bad-command"]\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_overlapping_security_policies_raise_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text(
            '[security]\nallowed_commands = ["greet"]\ndenied_commands = ["greet"]\n'
        )

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_invalid_security_origin_raises_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[security]\nallowed_origins = ["ws://localhost:3000"]\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)

    def test_invalid_window_scope_capability_raises_validation_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "forge.toml"
        config_file.write_text('[security.window_scopes]\nmain = ["invalid"]\n')

        with pytest.raises(ConfigValidationError):
            ForgeConfig.from_file(config_file)
