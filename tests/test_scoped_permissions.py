"""
Tests for Forge Scoped Permissions (Phase 11).

Tests the ScopeValidator, FileSystemAPI deny lists,
ShellAPI deny_execute, and URL scope enforcement.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from forge.scope import ScopeValidator, expand_scope_path
from forge.config import FileSystemPermissions, ShellPermissions


# ───────────────────────────────────────────────────────────
# ScopeValidator — Path matching
# ───────────────────────────────────────────────────────────

class TestScopeValidatorPaths:
    """Test path-based scope validation."""

    def test_allow_everything_when_no_patterns(self):
        """No patterns → everything allowed (open policy)."""
        validator = ScopeValidator()
        assert validator.is_path_allowed("/any/path/file.txt")
        assert validator.is_path_allowed("/etc/passwd")

    def test_allow_specific_directory(self):
        """Exact directory prefix matching."""
        with tempfile.TemporaryDirectory() as tmp:
            allowed_dir = Path(tmp) / "data"
            allowed_dir.mkdir()
            (allowed_dir / "file.txt").write_text("test")

            validator = ScopeValidator(allow_patterns=[str(allowed_dir)])
            assert validator.is_path_allowed(allowed_dir / "file.txt")
            assert not validator.is_path_allowed(Path(tmp) / "outside.txt")

    def test_deny_overrides_allow(self):
        """Deny patterns must override allow patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            secret_dir = data_dir / "secret"
            secret_dir.mkdir()
            (data_dir / "public.txt").write_text("public")
            (secret_dir / "key.pem").write_text("secret")

            validator = ScopeValidator(
                allow_patterns=[str(data_dir)],
                deny_patterns=[str(secret_dir)],
            )
            assert validator.is_path_allowed(data_dir / "public.txt")
            assert not validator.is_path_allowed(secret_dir / "key.pem")

    def test_deny_glob_pattern(self):
        """Deny patterns with glob wildcards."""
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "project"
            allowed.mkdir()
            (allowed / "config.txt").write_text("ok")
            (allowed / "secret.env").write_text("bad")

            validator = ScopeValidator(
                allow_patterns=[str(allowed)],
                deny_patterns=[str(allowed) + "/*.env"],
            )
            assert validator.is_path_allowed(allowed / "config.txt")
            assert not validator.is_path_allowed(allowed / "secret.env")

    def test_deny_double_star_glob(self):
        """Deny with ** matches recursively."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "src").mkdir(parents=True)
            (project / "node_modules" / "pkg").mkdir(parents=True)
            (project / "src" / "app.py").write_text("ok")
            (project / "node_modules" / "pkg" / "index.js").write_text("nope")

            validator = ScopeValidator(
                allow_patterns=[str(project)],
                deny_patterns=[str(project) + "/node_modules/**"],
            )
            assert validator.is_path_allowed(project / "src" / "app.py")
            assert not validator.is_path_allowed(
                project / "node_modules" / "pkg" / "index.js"
            )

    def test_no_allow_means_deny_all(self):
        """When allow_patterns are defined but path doesn't match, deny."""
        validator = ScopeValidator(allow_patterns=["/allowed/dir"])
        assert not validator.is_path_allowed("/other/dir/file.txt")

    def test_deny_only_blocks_specific_paths(self):
        """Deny without allow means deny list only."""
        validator = ScopeValidator(deny_patterns=["/blocked"])
        assert validator.is_path_allowed("/any/other/path")
        assert not validator.is_path_allowed("/blocked/file.txt")


# ───────────────────────────────────────────────────────────
# ScopeValidator — URL matching
# ───────────────────────────────────────────────────────────

class TestScopeValidatorURLs:
    """Test URL-based scope validation."""

    def test_allow_everything_when_no_patterns(self):
        validator = ScopeValidator()
        assert validator.is_url_allowed("https://example.com")
        assert validator.is_url_allowed("https://evil.com")

    def test_allow_specific_domain(self):
        validator = ScopeValidator(allow_patterns=["https://api.example.com/*"])
        assert validator.is_url_allowed("https://api.example.com/v1/users")
        assert not validator.is_url_allowed("https://evil.com/phish")

    def test_deny_overrides_allow_urls(self):
        validator = ScopeValidator(
            allow_patterns=["https://*.example.com/*"],
            deny_patterns=["https://internal.example.com/*"],
        )
        assert validator.is_url_allowed("https://api.example.com/data")
        assert not validator.is_url_allowed("https://internal.example.com/admin")

    def test_deny_specific_url_pattern(self):
        validator = ScopeValidator(
            deny_patterns=["https://malware.com/*"],
        )
        assert validator.is_url_allowed("https://safe.com")
        assert not validator.is_url_allowed("https://malware.com/payload")


# ───────────────────────────────────────────────────────────
# expand_scope_path
# ───────────────────────────────────────────────────────────

class TestExpandScopePath:
    """Test scope path expansion."""

    def test_expand_tilde(self):
        result = expand_scope_path("~/Documents")
        assert "~" not in result
        assert os.path.isabs(result)

    def test_expand_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_DIR", "/custom/path")
        result = expand_scope_path("$MY_DIR/data")
        assert result == "/custom/path/data"

    def test_relative_pattern_with_base_dir(self):
        base = Path("/project/root")
        result = expand_scope_path("data/files", base_dir=base)
        assert result == str(base / "data" / "files")

    def test_absolute_pattern_unchanged(self):
        result = expand_scope_path("/absolute/path")
        assert result == "/absolute/path"


# ───────────────────────────────────────────────────────────
# FileSystemAPI with deny scopes
# ───────────────────────────────────────────────────────────

class TestFileSystemAPIDenyScopes:
    """Test that FileSystemAPI enforces deny patterns."""

    def test_deny_blocks_read_and_write(self):
        """Denied paths must be blocked for both reads and writes."""
        from forge.api.fs import FileSystemAPI

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            secret_dir = project / "secrets"
            secret_dir.mkdir()
            (secret_dir / "key.pem").write_text("secret-key")
            (project / "public.txt").write_text("accessible")

            permissions = FileSystemPermissions(
                read=[str(project)],
                write=[str(project)],
                deny=[str(secret_dir)],
            )
            fs_api = FileSystemAPI(base_path=project, permissions=permissions)

            # Public file should be readable
            assert fs_api.read("public.txt") == "accessible"

            # Denied dir should block reads
            with pytest.raises(ValueError, match="Access denied"):
                fs_api.read("secrets/key.pem")

            # Denied dir should block writes
            with pytest.raises(ValueError, match="Access denied"):
                fs_api.write("secrets/new.txt", "data")

    def test_deny_blocks_file_in_glob(self):
        """Deny glob patterns block matching files."""
        from forge.api.fs import FileSystemAPI

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "config.toml").write_text("[app]")
            (project / "secrets.env").write_text("TOKEN=abc")

            permissions = FileSystemPermissions(
                read=[str(project)],
                write=[str(project)],
                deny=[str(project) + "/*.env"],
            )
            fs_api = FileSystemAPI(base_path=project, permissions=permissions)

            # .toml should be readable
            assert fs_api.read("config.toml") == "[app]"

            # .env should be denied
            with pytest.raises(ValueError, match="Access denied"):
                fs_api.read("secrets.env")

    def test_write_to_denied_path_raises(self):
        """Write operations to denied paths must raise."""
        from forge.api.fs import FileSystemAPI

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            readonly_dir = project / "readonly"
            readonly_dir.mkdir()

            permissions = FileSystemPermissions(
                read=[str(project)],
                write=[str(project)],
                deny=[str(readonly_dir)],
            )
            fs_api = FileSystemAPI(base_path=project, permissions=permissions)

            with pytest.raises(ValueError, match="Access denied"):
                fs_api.write("readonly/test.txt", "data")

    def test_no_deny_preserves_existing_behavior(self):
        """Without deny patterns, existing allow behavior is unchanged."""
        from forge.api.fs import FileSystemAPI

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "file.txt").write_text("hello")

            permissions = FileSystemPermissions(
                read=[str(project)],
                write=[str(project)],
            )
            fs_api = FileSystemAPI(base_path=project, permissions=permissions)
            assert fs_api.read("file.txt") == "hello"


# ───────────────────────────────────────────────────────────
# ShellAPI deny_execute and URL scopes
# ───────────────────────────────────────────────────────────

class TestShellAPIDenyAndURLScopes:
    """Test deny_execute and URL scope enforcement on ShellAPI."""

    def test_deny_execute_blocks_command(self):
        """Commands in deny_execute should be blocked even if in execute list."""
        from forge.api.shell import ShellAPI

        perms = ShellPermissions(
            execute=["ls", "rm", "cat"],
            deny_execute=["rm"],
        )
        api = ShellAPI(base_dir=Path("/tmp"), permissions=perms)

        assert api._is_allowed("ls")
        assert api._is_allowed("cat")
        assert not api._is_allowed("rm")  # deny_execute overrides

    def test_deny_execute_empty_allows_all_in_execute(self):
        """Empty deny_execute doesn't block anything."""
        from forge.api.shell import ShellAPI

        perms = ShellPermissions(
            execute=["ls", "cat"],
            deny_execute=[],
        )
        api = ShellAPI(base_dir=Path("/tmp"), permissions=perms)
        assert api._is_allowed("ls")
        assert api._is_allowed("cat")

    def test_url_scope_blocks_denied_urls(self):
        """shell.open() must reject URLs matching deny_urls."""
        from forge.api.shell import ShellAPI

        perms = ShellPermissions(
            execute=[],
            allow_urls=["https://*.example.com/*"],
            deny_urls=["https://internal.example.com/*"],
        )
        api = ShellAPI(base_dir=Path("/tmp"), permissions=perms)

        # Allowed domain
        assert api._url_scope.is_url_allowed("https://api.example.com/v1")
        # Denied subdomain
        assert not api._url_scope.is_url_allowed("https://internal.example.com/admin")

    def test_url_scope_no_patterns_allows_all(self):
        """No URL patterns → all URLs allowed."""
        from forge.api.shell import ShellAPI

        perms = ShellPermissions(execute=[])
        api = ShellAPI(base_dir=Path("/tmp"), permissions=perms)
        assert api._url_scope.is_url_allowed("https://anything.com")

    def test_open_denied_url_raises(self):
        """shell.open() with a denied URL must raise PermissionError."""
        from forge.api.shell import ShellAPI

        perms = ShellPermissions(
            execute=[],
            allow_urls=["https://safe.com/*"],
            deny_urls=["https://evil.com/*"],
        )
        api = ShellAPI(base_dir=Path("/tmp"), permissions=perms)

        with pytest.raises(PermissionError, match="not allowed"):
            api.open("https://evil.com/payload")

        with pytest.raises(PermissionError, match="not allowed"):
            api.open("https://unknown.com/page")  # not in allow list


# ───────────────────────────────────────────────────────────
# Config parsing of new fields
# ───────────────────────────────────────────────────────────

class TestConfigParsesNewFields:
    """Test that forge.toml parsing handles new deny/URL fields."""

    def test_filesystem_deny_parsed(self, tmp_path):
        """[permissions.filesystem.deny] is parsed into FileSystemPermissions."""
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[permissions.filesystem]
read = ["./data"]
write = ["./data"]
deny = ["./data/secrets"]
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        fs_perms = config.permissions.filesystem
        assert hasattr(fs_perms, 'deny')
        assert fs_perms.deny == ["./data/secrets"]

    def test_shell_deny_execute_parsed(self, tmp_path):
        """[permissions.shell.deny_execute] is parsed."""
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[permissions.shell]
execute = ["ls", "cat", "rm"]
deny_execute = ["rm"]
allow_urls = ["https://api.example.com/*"]
deny_urls = ["https://internal.example.com/*"]
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        shell_perms = config.permissions.shell
        assert shell_perms.execute == ["ls", "cat", "rm"]
        assert shell_perms.deny_execute == ["rm"]
        assert shell_perms.allow_urls == ["https://api.example.com/*"]
        assert shell_perms.deny_urls == ["https://internal.example.com/*"]

    def test_missing_new_fields_default_empty(self, tmp_path):
        """Old-style config without new fields defaults to empty lists."""
        config_toml = tmp_path / "forge.toml"
        config_toml.write_text("""
[app]
name = "Test"

[permissions.filesystem]
read = ["./data"]
write = ["./data"]

[permissions.shell]
execute = ["ls"]
""")
        from forge.config import load_config
        config = load_config(str(config_toml))
        
        fs_perms = config.permissions.filesystem
        assert fs_perms.deny == []
        
        shell_perms = config.permissions.shell
        assert shell_perms.deny_execute == []
        assert shell_perms.allow_urls == []
        assert shell_perms.deny_urls == []
