"""
Tests for Forge Production Bundler (Phase 14).

Tests the extracted bundler module: BundleConfig, ValidationResult,
BundlePipeline, and build tool detection.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge_cli.bundler import (
    BundleConfig,
    BundlePipeline,
    ValidationResult,
    detect_build_tool,
    validate_bundle,
)


# ─── Fixtures ───

@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory."""
    # Create entry point
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("import forge")

    # Create frontend
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "index.html").write_text("<html></html>")
    (tmp_path / "frontend" / "forge.js").write_text("// Forge JS")

    return tmp_path


@pytest.fixture
def bundle_config(project_dir):
    """Create a basic BundleConfig."""
    return BundleConfig(
        app_name="Test App",
        entry_point=project_dir / "src" / "main.py",
        frontend_dir=project_dir / "frontend",
        output_dir=project_dir / "dist",
        project_dir=project_dir,
        builder="nuitka",
    )


# ─── BundleConfig Tests ───

class TestBundleConfig:

    def test_safe_app_name(self, bundle_config):
        assert bundle_config.safe_app_name == "test_app"

    def test_safe_app_name_with_spaces(self):
        config = BundleConfig(
            app_name="My Forge App",
            entry_point=Path("/dummy"),
            frontend_dir=Path("/dummy"),
            output_dir=Path("/dummy"),
            project_dir=Path("/dummy"),
        )
        assert config.safe_app_name == "my_forge_app"

    def test_default_target(self, bundle_config):
        assert bundle_config.target == "desktop"

    def test_from_forge_config(self, project_dir):
        """from_forge_config correctly maps ForgeConfig fields."""
        mock_config = MagicMock()
        mock_config.app.name = "MyApp"
        mock_config.build.output_dir = "dist"
        mock_config.build.icon = None
        mock_config.get_entry_path.return_value = project_dir / "src" / "main.py"
        mock_config.get_frontend_path.return_value = project_dir / "frontend"
        mock_config.packaging.formats = ["deb", "appimage"]

        config = BundleConfig.from_forge_config(mock_config, project_dir)
        assert config.app_name == "MyApp"
        assert config.safe_app_name == "myapp"
        assert config.formats == ["deb", "appimage"]


# ─── Validation Tests ───

class TestValidation:

    def test_valid_desktop_project(self, bundle_config):
        result = validate_bundle(bundle_config)
        # May fail on 'available' check since Nuitka isn't installed in test env
        # But entry point and frontend should be fine
        assert "Entry point missing" not in str(result.errors)
        assert "Frontend directory missing" not in str(result.errors)

    def test_invalid_target(self, bundle_config):
        bundle_config.target = "mobile"
        result = validate_bundle(bundle_config)
        assert not result.ok
        assert any("Unsupported build target" in e for e in result.errors)

    def test_missing_entry_point(self, project_dir):
        config = BundleConfig(
            app_name="Test",
            entry_point=project_dir / "nonexistent.py",
            frontend_dir=project_dir / "frontend",
            output_dir=project_dir / "dist",
            project_dir=project_dir,
        )
        result = validate_bundle(config)
        assert not result.ok
        assert any("Entry point missing" in e for e in result.errors)

    def test_missing_frontend(self, project_dir):
        config = BundleConfig(
            app_name="Test",
            entry_point=project_dir / "src" / "main.py",
            frontend_dir=project_dir / "no_frontend",
            output_dir=project_dir / "dist",
            project_dir=project_dir,
        )
        result = validate_bundle(config)
        assert not result.ok
        assert any("Frontend directory missing" in e for e in result.errors)

    def test_missing_icon_warns(self, bundle_config):
        bundle_config.icon = bundle_config.project_dir / "nonexistent.png"
        result = validate_bundle(bundle_config)
        assert any("icon not found" in w for w in result.warnings)

    def test_web_target_skips_entry_check(self, project_dir):
        config = BundleConfig(
            app_name="Test",
            entry_point=project_dir / "nonexistent.py",
            frontend_dir=project_dir / "frontend",
            output_dir=project_dir / "dist",
            project_dir=project_dir,
            target="web",
        )
        result = validate_bundle(config)
        # Web builds don't need entry point
        assert "Entry point missing" not in str(result.errors)


# ─── ValidationResult Tests ───

class TestValidationResult:

    def test_starts_ok(self):
        r = ValidationResult()
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_sets_not_ok(self):
        r = ValidationResult()
        r.add_error("something broke")
        assert not r.ok
        assert "something broke" in r.errors

    def test_add_warning_stays_ok(self):
        r = ValidationResult()
        r.add_warning("mild issue")
        assert r.ok
        assert "mild issue" in r.warnings

    def test_to_dict(self):
        r = ValidationResult()
        r.add_error("error1")
        r.add_warning("warn1")
        d = r.to_dict()
        assert d["ok"] is False
        assert d["errors"] == ["error1"]
        assert d["warnings"] == ["warn1"]


# ─── Build Tool Detection ───

class TestDetectBuildTool:

    def test_no_tools_available(self, project_dir):
        with patch("shutil.which", return_value=None), \
             patch("forge_cli.bundler._module_available", return_value=False):
            result = detect_build_tool(project_dir)
            assert not result["available"]
            assert result["name"] == "nuitka"

    def test_nuitka_available(self, project_dir):
        with patch("shutil.which", return_value=None), \
             patch("forge_cli.bundler._module_available", return_value=True):
            result = detect_build_tool(project_dir)
            assert result["available"]
            assert result["name"] == "nuitka"
            assert result["mode"] == "python"

    def test_maturin_with_cargo(self, project_dir):
        (project_dir / "Cargo.toml").write_text("[package]\nname = 'test'")
        with patch("shutil.which", return_value="/usr/bin/maturin"):
            result = detect_build_tool(project_dir)
            assert result["available"]
            assert result["name"] == "maturin"
            assert result["mode"] == "hybrid"

    def test_cargo_without_maturin(self, project_dir):
        (project_dir / "Cargo.toml").write_text("[package]\nname = 'test'")
        with patch("shutil.which", return_value=None), \
             patch("forge_cli.bundler._module_available", return_value=False):
            result = detect_build_tool(project_dir)
            assert not result["available"]
            assert result["name"] == "maturin"  # Suggests maturin since Cargo.toml exists


# ─── BundlePipeline Tests ───

class TestBundlePipeline:

    def test_validate(self, bundle_config):
        pipeline = BundlePipeline(bundle_config)
        result = pipeline.validate()
        assert isinstance(result, ValidationResult)

    def test_bundle_frontend_copies_assets(self, bundle_config):
        pipeline = BundlePipeline(bundle_config)
        result = pipeline.bundle_frontend()
        assert result["status"] == "ok"
        assert (bundle_config.output_dir / "frontend" / "index.html").exists()
        assert (bundle_config.output_dir / "frontend" / "forge.js").exists()

    def test_bundle_frontend_web_target(self, bundle_config):
        bundle_config.target = "web"
        pipeline = BundlePipeline(bundle_config)
        result = pipeline.bundle_frontend()
        assert result["status"] == "ok"
        assert (bundle_config.output_dir / "static" / "index.html").exists()

    def test_bundle_frontend_no_dir(self, project_dir):
        config = BundleConfig(
            app_name="Test",
            entry_point=project_dir / "src" / "main.py",
            frontend_dir=project_dir / "no_frontend",
            output_dir=project_dir / "dist",
            project_dir=project_dir,
        )
        pipeline = BundlePipeline(config)
        result = pipeline.bundle_frontend()
        assert result["status"] == "skipped"

    def test_bundle_sidecars(self, bundle_config):
        # Create a sidecar directory
        bin_dir = bundle_config.project_dir / "bin"
        bin_dir.mkdir()
        (bin_dir / "helper").write_text("#!/bin/sh\necho ok")

        pipeline = BundlePipeline(bundle_config)
        result = pipeline.bundle_sidecars()
        assert result["status"] == "ok"
        assert (bundle_config.output_dir / "bin" / "helper").exists()

    def test_bundle_sidecars_no_bin(self, bundle_config):
        pipeline = BundlePipeline(bundle_config)
        result = pipeline.bundle_sidecars()
        assert result["status"] == "skipped"

    def test_get_summary(self, bundle_config):
        pipeline = BundlePipeline(bundle_config)
        pipeline.bundle_frontend()
        summary = pipeline.get_summary()
        assert summary["status"] == "ok"
        assert summary["target"] == "desktop"
        assert summary["app_name"] == "Test App"
        assert summary["safe_name"] == "test_app"
        assert len(summary["artifacts"]) > 0

    def test_frontend_replaces_existing(self, bundle_config):
        """Bundling frontend replaces existing output directory cleanly."""
        # First build
        pipeline = BundlePipeline(bundle_config)
        pipeline.bundle_frontend()
        
        # Add a stale file
        (bundle_config.output_dir / "frontend" / "stale.txt").write_text("old")

        # Rebuild should clean it
        pipeline2 = BundlePipeline(bundle_config)
        pipeline2.bundle_frontend()
        assert not (bundle_config.output_dir / "frontend" / "stale.txt").exists()
