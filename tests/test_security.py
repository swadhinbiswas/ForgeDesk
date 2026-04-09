"""Tests for Phase 2: Security & Capability Model hardening."""
import json
import time

import pytest

from forge.bridge import IPCBridge
from forge.config import (
    ForgeConfig,
    SecurityConfig,
    PermissionsConfig,
    FileSystemPermissions,
)


# ─── Helpers ───


class _MockApp:
    """Minimal mock app for bridge tests with configurable security settings."""

    def __init__(
        self,
        *,
        strict_mode: bool = False,
        allowed_commands: list | None = None,
        denied_commands: list | None = None,
        allowed_origins: list | None = None,
        window_scopes: dict | None = None,
        rate_limit: int = 0,
        expose_command_introspection: bool = True,
        permissions: PermissionsConfig | None = None,
    ):
        self.config = ForgeConfig()
        self.config.security = SecurityConfig(
            strict_mode=strict_mode,
            allowed_commands=allowed_commands or [],
            denied_commands=denied_commands or [],
            allowed_origins=allowed_origins or [],
            window_scopes=window_scopes or {},
            rate_limit=rate_limit,
            expose_command_introspection=expose_command_introspection,
        )
        if permissions is not None:
            self.config.permissions = permissions

    def has_capability(self, capability: str, *, window_label: str | None = None) -> bool:
        enabled = bool(getattr(self.config.permissions, capability, False))
        if not enabled:
            return False
        if window_label is None:
            return enabled
        scopes = self.config.security.window_scopes or {}
        if window_label not in scopes:
            return enabled
        allowed = set(scopes.get(window_label, []))
        return capability in allowed or "*" in allowed or "all" in allowed

    def is_origin_allowed(self, origin: str | None) -> bool:
        if not origin:
            return True
        if origin.startswith("forge://"):
            return True
        if self.config.security.strict_mode:
            has_explicit_external = any(
                not a.startswith("forge://") for a in self.config.security.allowed_origins
            )
            if not has_explicit_external:
                return False
        from urllib.parse import urlparse
        parsed_origin = urlparse(origin)
        normalized = (
            f"{parsed_origin.scheme}://{parsed_origin.netloc}"
            if parsed_origin.scheme in {"http", "https"} and parsed_origin.netloc
            else origin
        )
        for allowed in self.config.security.allowed_origins:
            if allowed.startswith("forge://"):
                continue
            parsed_allowed = urlparse(allowed)
            allowed_origin = (
                f"{parsed_allowed.scheme}://{parsed_allowed.netloc}"
                if parsed_allowed.scheme in {"http", "https"} and parsed_allowed.netloc
                else allowed
            )
            if normalized == allowed_origin:
                return True
        return False


def _make_bridge(app: _MockApp | None = None, **kw) -> IPCBridge:
    app = app or _MockApp(**kw)
    bridge = IPCBridge(app)
    bridge.register_command("echo", lambda message="hello": {"echo": message})
    bridge.register_command("greet", lambda name="world": {"greeting": f"Hello, {name}!"})
    return bridge


def _invoke(bridge: IPCBridge, cmd: str, **extra) -> dict:
    payload = {"command": cmd, "id": 1, **extra}
    return json.loads(bridge.invoke_command(json.dumps(payload)))


# ─── Capability Enforcement ───


class TestCapabilityEnforcement:
    def test_command_with_disabled_capability_is_rejected(self):
        app = _MockApp(permissions=PermissionsConfig(clipboard=False))
        bridge = IPCBridge(app)
        bridge.register_command("copy", lambda: {}, capability="clipboard")
        resp = _invoke(bridge, "copy")
        assert resp["error"] is not None
        assert "permission" in resp["error"].lower() or "denied" in resp["error"].lower()

    def test_command_with_enabled_capability_is_allowed(self):
        app = _MockApp(permissions=PermissionsConfig(clipboard=True))
        bridge = IPCBridge(app)
        bridge.register_command("copy", lambda: {"ok": True}, capability="clipboard")
        resp = _invoke(bridge, "copy")
        assert resp["result"] == {"ok": True}

    def test_command_without_capability_is_allowed(self):
        bridge = _make_bridge()
        resp = _invoke(bridge, "echo")
        assert resp["result"]["echo"] == "hello"
        assert resp["error"] is None


class TestStrictMode:
    def test_strict_mode_blocks_unlisted_commands(self):
        bridge = _make_bridge(strict_mode=True)
        resp = _invoke(bridge, "echo")
        assert resp["error"] is not None
        assert "not allowed" in resp["error"].lower()

    def test_strict_mode_allows_listed_commands(self):
        bridge = _make_bridge(strict_mode=True, allowed_commands=["echo"])
        resp = _invoke(bridge, "echo")
        assert resp["result"]["echo"] == "hello"

    def test_strict_mode_always_allows_internal_commands(self):
        bridge = _make_bridge(strict_mode=True)
        resp = _invoke(bridge, "__forge_protocol_info")
        assert resp["error"] is None
        assert resp["result"] is not None

    def test_denied_commands_override_allowed(self):
        bridge = _make_bridge(
            allowed_commands=["echo", "greet"],
            denied_commands=["echo"],
        )
        resp = _invoke(bridge, "echo")
        assert resp["error"] is not None
        assert "not allowed" in resp["error"].lower()

    def test_denied_commands_block_even_without_strict(self):
        bridge = _make_bridge(denied_commands=["echo"])
        resp = _invoke(bridge, "echo")
        assert resp["error"] is not None

    def test_non_strict_allows_unlisted_commands(self):
        bridge = _make_bridge(strict_mode=False)
        resp = _invoke(bridge, "echo")
        assert resp["result"]["echo"] == "hello"

    def test_strict_mode_with_allow_list_passes_listed(self):
        bridge = _make_bridge(strict_mode=True, allowed_commands=["echo", "greet"])
        resp_echo = _invoke(bridge, "echo")
        resp_greet = _invoke(bridge, "greet")
        assert resp_echo["error"] is None
        assert resp_greet["error"] is None


# ─── Window Scope Enforcement ───


class TestWindowScopeEnforcement:
    def test_window_scope_allows_listed_capabilities(self):
        app = _MockApp(
            permissions=PermissionsConfig(clipboard=True),
            window_scopes={"settings": ["clipboard"]},
        )
        bridge = IPCBridge(app)
        bridge.register_command("copy", lambda: {"ok": True}, capability="clipboard")
        resp = _invoke(bridge, "copy", meta={"window_label": "settings"})
        assert resp["result"] == {"ok": True}

    def test_window_scope_denies_unlisted_capabilities(self):
        app = _MockApp(
            permissions=PermissionsConfig(clipboard=True, filesystem=True),
            window_scopes={"settings": ["clipboard"]},
        )
        bridge = IPCBridge(app)
        bridge.register_command("read_file", lambda: {}, capability="filesystem")
        resp = _invoke(bridge, "read_file", meta={"window_label": "settings"})
        assert resp["error"] is not None
        assert "scope" in resp["error"].lower() or "denied" in resp["error"].lower()

    def test_window_scope_wildcard_allows_all(self):
        app = _MockApp(
            permissions=PermissionsConfig(clipboard=True, filesystem=True),
            window_scopes={"admin": ["*"]},
        )
        bridge = IPCBridge(app)
        bridge.register_command("read_file", lambda: {"ok": True}, capability="filesystem")
        resp = _invoke(bridge, "read_file", meta={"window_label": "admin"})
        assert resp["result"] == {"ok": True}

    def test_unknown_window_label_uses_global_capability(self):
        app = _MockApp(
            permissions=PermissionsConfig(clipboard=True),
        )
        bridge = IPCBridge(app)
        bridge.register_command("copy", lambda: {"ok": True}, capability="clipboard")
        resp = _invoke(bridge, "copy", meta={"window_label": "unknown_window"})
        assert resp["result"] == {"ok": True}


# ─── Origin Validation ───


class TestOriginValidation:
    def test_forge_protocol_origin_always_allowed(self):
        app = _MockApp(strict_mode=True)
        assert app.is_origin_allowed("forge://app") is True
        assert app.is_origin_allowed("forge://app/index.html") is True

    def test_empty_origin_always_allowed(self):
        app = _MockApp(strict_mode=True)
        assert app.is_origin_allowed(None) is True
        assert app.is_origin_allowed("") is True

    def test_allowed_origin_passes(self):
        app = _MockApp(allowed_origins=["http://localhost:5173"])
        assert app.is_origin_allowed("http://localhost:5173") is True

    def test_disallowed_origin_is_rejected(self):
        app = _MockApp(allowed_origins=["http://localhost:5173"])
        assert app.is_origin_allowed("http://evil.com") is False

    def test_strict_mode_no_external_origins_blocks_http(self):
        app = _MockApp(strict_mode=True)  # No allowed_origins configured
        assert app.is_origin_allowed("http://localhost:5173") is False
        assert app.is_origin_allowed("https://example.com") is False

    def test_strict_mode_with_explicit_origin_allows(self):
        app = _MockApp(strict_mode=True, allowed_origins=["http://localhost:5173"])
        assert app.is_origin_allowed("http://localhost:5173") is True
        assert app.is_origin_allowed("https://evil.com") is False


# ─── Filesystem Scoping ───


class TestFilesystemScoping:
    def test_read_within_scope_allowed(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        test_file = tmp_path / "data.txt"
        test_file.write_text("hello")
        fs = FileSystemAPI(
            base_path=tmp_path,
            permissions=FileSystemPermissions(read=[str(tmp_path)], write=[]),
        )
        assert fs.read("data.txt") == "hello"

    def test_read_outside_scope_denied(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        other = tmp_path / "other"
        other.mkdir()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        fs = FileSystemAPI(
            base_path=tmp_path,
            permissions=FileSystemPermissions(read=[str(allowed)], write=[]),
        )
        with pytest.raises(ValueError, match="outside allowed"):
            fs.read("other/secret.txt")

    def test_write_within_scope_allowed(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        fs = FileSystemAPI(
            base_path=tmp_path,
            permissions=FileSystemPermissions(read=[], write=[str(tmp_path)]),
        )
        fs.write("output.txt", "data")
        assert (tmp_path / "output.txt").read_text() == "data"

    def test_write_outside_scope_denied(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        fs = FileSystemAPI(
            base_path=tmp_path,
            permissions=FileSystemPermissions(read=[], write=[str(allowed)]),
        )
        with pytest.raises(ValueError, match="outside allowed"):
            fs.write("secret.txt", "hacked")

    def test_filesystem_true_allows_all_paths(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        (tmp_path / "a.txt").write_text("hi")
        fs = FileSystemAPI(base_path=tmp_path, permissions=True)
        assert fs.read("a.txt") == "hi"
        fs.write("b.txt", "yo")
        assert (tmp_path / "b.txt").read_text() == "yo"

    def test_path_traversal_blocked(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        fs = FileSystemAPI(base_path=tmp_path, permissions=True)
        with pytest.raises(ValueError):
            fs.read("../../etc/passwd")

    def test_symlink_escape_blocked(self, tmp_path):
        from forge.api.fs import FileSystemAPI
        import os
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "data.txt").write_text("sensitive")

        allowed = tmp_path / "allowed"
        allowed.mkdir()
        link = allowed / "escape"
        os.symlink(secret, link)

        fs = FileSystemAPI(
            base_path=tmp_path,
            permissions=FileSystemPermissions(read=[str(allowed)], write=[]),
        )
        # The symlink resolves outside the allowed scope
        with pytest.raises(ValueError, match="outside allowed"):
            fs.read("allowed/escape/data.txt")


# ─── Rate Limiting ───


class TestRateLimiting:
    def test_rate_limit_blocks_excess_calls(self):
        bridge = _make_bridge(rate_limit=5)
        results = []
        for i in range(10):
            resp = _invoke(bridge, "echo")
            results.append(resp)
        # First 5 should succeed, rest should be rate limited
        successes = [r for r in results if r.get("error") is None]
        rate_limited = [r for r in results if "rate limit" in (r.get("error") or "").lower()]
        assert len(successes) == 5
        assert len(rate_limited) == 5

    def test_rate_limit_zero_means_unlimited(self):
        bridge = _make_bridge(rate_limit=0)
        for _ in range(50):
            resp = _invoke(bridge, "echo")
            assert resp["error"] is None

    def test_rate_limit_resets_after_window(self):
        bridge = _make_bridge(rate_limit=3)
        # Exhaust the window
        for _ in range(3):
            _invoke(bridge, "echo")
        # Should be rate limited
        resp = _invoke(bridge, "echo")
        assert resp["error"] is not None
        # Wait for window to expire
        time.sleep(1.1)
        # Should be allowed again
        resp = _invoke(bridge, "echo")
        assert resp["error"] is None


# ─── Introspection Controls ───


class TestIntrospectionControls:
    def test_introspection_disabled_blocks_describe(self):
        bridge = _make_bridge(expose_command_introspection=False)
        resp = _invoke(bridge, "__forge_describe_commands")
        assert resp["error"] is not None
        assert "not allowed" in resp["error"].lower()

    def test_introspection_enabled_allows_describe(self):
        bridge = _make_bridge(expose_command_introspection=True)
        resp = _invoke(bridge, "__forge_describe_commands")
        assert resp["error"] is None
        assert resp["result"] is not None
