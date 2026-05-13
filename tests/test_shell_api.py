import sys
from pathlib import Path

import pytest

from forge.app import ForgeApp


def _write_config(tmp_path: Path, permissions: dict) -> Path:
    config_file = tmp_path / "forge.toml"

    # Simple dict to TOML string function for our test needs
    def to_toml(d: dict, prefix="") -> str:
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"[{prefix}{k}]")
                lines.append(to_toml(v, f"{prefix}{k}."))
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{k} = []")
                else:
                    items = ", ".join(f'"{i}"' if isinstance(i, str) else str(i) for i in v)
                    lines.append(f"{k} = [{items}]")
            elif isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            else:
                lines.append(f"{k} = {v}")
        return "\n".join(lines)

    config = {"app": {"name": "Test"}, "permissions": permissions}

    config_file.write_text(to_toml(config))
    return config_file


class TestShellAPI:
    def test_shell_disabled_by_default(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, {})
        app = ForgeApp(str(config_path))

        with pytest.raises(PermissionError, match="not allowed|disabled"):
            app.shell.execute("echo", ["hello"])

        with pytest.raises(PermissionError, match="not allowed|disabled"):
            app.shell.open("https://example.com")

        with pytest.raises(PermissionError, match="not allowed|disabled"):
            app.shell.sidecar("test_bin")

    def test_shell_execute_allowed(self, tmp_path: Path) -> None:
        cmd = "cmd" if sys.platform == "win32" else "echo"
        config_path = _write_config(tmp_path, {"shell": {"execute": [cmd]}})
        app = ForgeApp(str(config_path))

        result = app.shell.execute(cmd, ["hello"])
        assert result["code"] == 0
        assert "hello" in result["stdout"]

    def test_shell_execute_denied(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, {"shell": {"execute": ["git"]}})
        app = ForgeApp(str(config_path))

        with pytest.raises(PermissionError, match="not allowed|disabled"):
            app.shell.execute("echo", ["hello"])

    def test_shell_open_allowed_when_shell_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = _write_config(tmp_path, {"shell": {"execute": ["git"]}})
        app = ForgeApp(str(config_path))

        opened_paths = []

        # mock Popen to prevent actual opening
        import os
        import subprocess

        if sys.platform == "win32":
            monkeypatch.setattr(os, "startfile", lambda p: opened_paths.append(p))
        else:

            class MockPopen:
                def __init__(self, args, **kwargs):
                    opened_paths.append(args[1])

            monkeypatch.setattr(subprocess, "Popen", MockPopen)

        app.shell.open("https://example.com")

        assert "https://example.com" in opened_paths

    def test_shell_global_true_allow_all(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, {"shell": True})
        app = ForgeApp(str(config_path))

        cmd = "cmd" if sys.platform == "win32" else "echo"
        result = app.shell.execute(cmd, ["hello globally allowed"])
        assert result["code"] == 0
        assert "hello globally allowed" in result["stdout"]

    def test_sidecar_execution_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cmd_name = "test_bin"
        config_path = _write_config(tmp_path, {"shell": {"sidecars": [cmd_name]}})

        # Create a fake binary
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        ext = ".exe" if sys.platform == "win32" else ""
        bin_path = bin_dir / f"{cmd_name}{ext}"
        bin_path.write_text("fake binary")

        app = ForgeApp(str(config_path))

        class MockResult:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        called_cmd = []
        import subprocess

        def mock_run(cmd, *args, **kwargs):
            called_cmd.extend(cmd)
            return MockResult("sidecar works", "", 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = app.shell.sidecar(cmd_name, ["arg1", "arg2"])

        assert result["code"] == 0
        assert "sidecar works" in result["stdout"]
        assert called_cmd[0] == str(bin_path)
        assert called_cmd[1:] == ["arg1", "arg2"]

    def test_sidecar_execution_denied(self, tmp_path: Path) -> None:
        cmd_name = "test_bin"
        config_path = _write_config(tmp_path, {"shell": {"sidecars": ["other_bin"]}})

        app = ForgeApp(str(config_path))

        with pytest.raises(PermissionError, match="not allowed"):
            app.shell.sidecar(cmd_name, ["arg1"])

    def test_sidecar_execution_not_found(self, tmp_path: Path) -> None:
        cmd_name = "test_bin"
        config_path = _write_config(tmp_path, {"shell": {"sidecars": [cmd_name]}})

        app = ForgeApp(str(config_path))

        with pytest.raises(FileNotFoundError, match="not found"):
            app.shell.sidecar(cmd_name, ["arg1"])
