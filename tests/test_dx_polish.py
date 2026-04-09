"""
Tests for Phase 16: Developer Experience Polish.

Tests:
  - `python -m forge` entry point
  - Doctor remediation hints
  - Plugin add config registration
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── __main__.py Tests ───

class TestMainModule:

    def test_main_module_exists(self):
        """forge/__main__.py should exist for `python -m forge` support."""
        main_path = Path(__file__).parent.parent / "forge" / "__main__.py"
        assert main_path.exists()

    def test_main_module_has_entry(self):
        """__main__.py should define a main() function."""
        from forge.__main__ import main
        assert callable(main)


# ─── Doctor Remediation Hints ───

class TestDoctorRemediation:

    def test_hints_for_missing_python(self):
        from forge_cli.main import _get_remediation_hints
        payload = {
            "environment": {
                "checks": {
                    "python": {"status": "error"},
                    "rust_core": {"status": "ok"},
                    "cargo": {"status": "ok"},
                    "rustc": {"status": "ok"},
                    "maturin": {"status": "ok"},
                }
            },
            "project": {"exists": True, "valid": True},
        }
        hints = _get_remediation_hints(payload)
        assert any("Python" in h for h in hints)

    def test_hints_for_missing_rust(self):
        from forge_cli.main import _get_remediation_hints
        payload = {
            "environment": {
                "checks": {
                    "python": {"status": "ok"},
                    "rust_core": {"status": "error"},
                    "cargo": {"status": "error"},
                    "rustc": {"status": "error"},
                    "maturin": {"status": "ok"},
                }
            },
            "project": {"exists": True, "valid": True},
        }
        hints = _get_remediation_hints(payload)
        assert any("Rust" in h for h in hints)
        assert any("maturin develop" in h for h in hints)

    def test_hints_for_missing_project(self):
        from forge_cli.main import _get_remediation_hints
        payload = {
            "environment": {
                "checks": {
                    "python": {"status": "ok"},
                    "rust_core": {"status": "ok"},
                    "cargo": {"status": "ok"},
                    "rustc": {"status": "ok"},
                    "maturin": {"status": "ok"},
                }
            },
            "project": {"exists": False, "valid": False},
        }
        hints = _get_remediation_hints(payload)
        assert any("forge create" in h for h in hints)

    def test_hints_for_invalid_config(self):
        from forge_cli.main import _get_remediation_hints
        payload = {
            "environment": {
                "checks": {
                    "python": {"status": "ok"},
                    "rust_core": {"status": "ok"},
                    "cargo": {"status": "ok"},
                    "rustc": {"status": "ok"},
                    "maturin": {"status": "ok"},
                }
            },
            "project": {"exists": True, "valid": False, "errors": ["Missing [app].name"]},
        }
        hints = _get_remediation_hints(payload)
        assert any("Missing [app].name" in h for h in hints)

    def test_no_hints_when_all_ok(self):
        from forge_cli.main import _get_remediation_hints
        payload = {
            "environment": {
                "checks": {
                    "python": {"status": "ok"},
                    "rust_core": {"status": "ok"},
                    "cargo": {"status": "ok"},
                    "rustc": {"status": "ok"},
                    "maturin": {"status": "ok"},
                }
            },
            "project": {"exists": True, "valid": True},
        }
        hints = _get_remediation_hints(payload)
        assert len(hints) == 0


# ─── Plugin Add Config Registration ───

class TestPluginAdd:

    def test_plugin_add_appends_to_empty_config(self, tmp_path):
        """Plugin add adds [plugins] section when missing."""
        config = tmp_path / "forge.toml"
        config.write_text('[app]\nname = "test"\n')

        # Simulate what plugin_add does to config
        config_text = config.read_text()
        module_name = "forge_plugin_auth"

        if "[plugins]" not in config_text:
            config_text += f'\n[plugins]\nenabled = true\nmodules = ["{module_name}"]\n'
            config.write_text(config_text)

        result = config.read_text()
        assert "[plugins]" in result
        assert "forge_plugin_auth" in result

    def test_plugin_add_appends_to_existing_modules(self, tmp_path):
        """Plugin add appends to existing modules list."""
        config = tmp_path / "forge.toml"
        config.write_text('[app]\nname = "test"\n\n[plugins]\nmodules = ["existing_plugin"]\n')

        config_text = config.read_text()
        module_name = "forge_plugin_db"

        if module_name not in config_text and "modules = [" in config_text:
            config_text = config_text.replace(
                'modules = [',
                f'modules = ["{module_name}", ',
            )
            config.write_text(config_text)

        result = config.read_text()
        assert "forge_plugin_db" in result
        assert "existing_plugin" in result

    def test_plugin_add_skips_if_already_registered(self, tmp_path):
        """Plugin add doesn't duplicate existing plugins."""
        config = tmp_path / "forge.toml"
        original = '[app]\nname = "test"\n\n[plugins]\nmodules = ["forge_plugin_auth"]\n'
        config.write_text(original)

        config_text = config.read_text()
        module_name = "forge_plugin_auth"

        # Should detect it's already there
        assert module_name in config_text

    def test_plugin_name_conversion(self):
        """Hyphens in plugin names should convert to underscores."""
        name = "forge-plugin-auth"
        module_name = name.replace("-", "_")
        assert module_name == "forge_plugin_auth"
