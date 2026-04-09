"""Tests for Forge diagnostics and support bundle generation."""

import json
import zipfile
from pathlib import Path

import pytest

from forge.diagnostics import (
    generate_support_bundle,
    _system_info,
    _sanitize_config,
    _load_config_snapshot,
)


class TestSystemInfo:
    def test_contains_required_fields(self):
        info = _system_info()
        assert "os" in info
        assert "python_version" in info
        assert "machine" in info
        assert "forge_core" in info
        assert "collected_at" in info

    def test_forge_core_status(self):
        info = _system_info()
        assert isinstance(info["forge_core"]["available"], bool)
        assert isinstance(info["forge_core"]["detail"], str)


class TestSanitizeConfig:
    def test_redacts_sensitive_fields(self):
        config = {
            "signing": {
                "identity": "my-secret-identity",
                "sign_command": "gpg --sign",
                "enabled": True,
            },
            "updater": {
                "public_key": "base64key...",
                "endpoint": "https://example.com/updates",
                "enabled": True,
            },
        }
        sanitized = _sanitize_config(config)
        assert sanitized["signing"]["identity"] == "***REDACTED***"
        assert sanitized["signing"]["sign_command"] == "***REDACTED***"
        assert sanitized["signing"]["enabled"] is True  # non-sensitive preserved
        assert sanitized["updater"]["public_key"] == "***REDACTED***"
        assert sanitized["updater"]["endpoint"] == "***REDACTED***"
        assert sanitized["updater"]["enabled"] is True

    def test_preserves_non_sensitive_fields(self):
        config = {
            "app": {"name": "MyApp", "version": "1.0.0"},
            "window": {"width": 800, "height": 600},
        }
        sanitized = _sanitize_config(config)
        assert sanitized["app"]["name"] == "MyApp"
        assert sanitized["window"]["width"] == 800

    def test_handles_missing_sections(self):
        config = {"app": {"name": "Test"}}
        sanitized = _sanitize_config(config)
        assert sanitized["app"]["name"] == "Test"

    def test_does_not_redact_empty_values(self):
        config = {
            "signing": {"identity": "", "enabled": False},
        }
        sanitized = _sanitize_config(config)
        # Empty string is falsy, so it won't be redacted
        assert sanitized["signing"]["identity"] == ""


class TestLoadConfigSnapshot:
    def test_missing_config_file(self, tmp_path):
        result = _load_config_snapshot(tmp_path)
        assert "error" in result
        assert "No forge.toml found" in result["error"]

    def test_valid_config_file(self, tmp_path):
        config_path = tmp_path / "forge.toml"
        config_path.write_text('[app]\nname = "TestApp"\nversion = "1.0.0"\n')
        result = _load_config_snapshot(tmp_path)
        assert result["app"]["name"] == "TestApp"


class TestGenerateSupportBundle:
    def test_generates_zip(self, tmp_path):
        output = tmp_path / "bundle.zip"
        result = generate_support_bundle(output, project_dir=tmp_path)
        assert output.exists()
        assert result["size_bytes"] > 0
        assert "system_info.json" in result["contents"]

    def test_includes_system_info(self, tmp_path):
        output = tmp_path / "bundle.zip"
        generate_support_bundle(output)
        with zipfile.ZipFile(output, "r") as zf:
            sys_info = json.loads(zf.read("system_info.json"))
            assert "os" in sys_info
            assert "python_version" in sys_info

    def test_includes_config_snapshot(self, tmp_path):
        config_path = tmp_path / "forge.toml"
        config_path.write_text('[app]\nname = "BundleTest"\nversion = "2.0"\n')
        output = tmp_path / "bundle.zip"
        generate_support_bundle(output, project_dir=tmp_path)
        with zipfile.ZipFile(output, "r") as zf:
            config = json.loads(zf.read("config_snapshot.json"))
            assert config["app"]["name"] == "BundleTest"

    def test_includes_log_files(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "forge-2026-04-07.log").write_text('{"level":"info","message":"test"}')
        output = tmp_path / "bundle.zip"
        result = generate_support_bundle(output, log_dir=log_dir)
        log_entries = [c for c in result["contents"] if c.startswith("recent_logs/")]
        assert len(log_entries) == 1

    def test_includes_extra_files(self, tmp_path):
        extra = tmp_path / "extra.txt"
        extra.write_text("diagnostic data")
        output = tmp_path / "bundle.zip"
        result = generate_support_bundle(output, extra_files=[extra])
        assert "extra/extra.txt" in result["contents"]

    def test_no_project_dir_still_works(self, tmp_path):
        output = tmp_path / "bundle.zip"
        result = generate_support_bundle(output)
        assert output.exists()
        assert "system_info.json" in result["contents"]

    def test_result_metadata(self, tmp_path):
        output = tmp_path / "bundle.zip"
        result = generate_support_bundle(output)
        assert "path" in result
        assert "size_bytes" in result
        assert "contents" in result
        assert "collected_at" in result
