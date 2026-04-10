"""Tests for Forge CLI commands."""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from forge_cli.main import app, _launch_dev_server, _project_payload, _resolve_project_dir, _watch_snapshot


runner = CliRunner()


def _write_project(tmp_path: Path) -> Path:
    frontend_dir = tmp_path / "src" / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "src" / "main.py").write_text("from forge import ForgeApp\napp = ForgeApp()\n", encoding="utf-8")
    (tmp_path / "forge.toml").write_text(
        "\n".join(
            [
                "[app]",
                'name = "CLI Test"',
                'version = "1.2.3"',
                "",
                "[build]",
                'entry = "src/main.py"',
                "",
                "[dev]",
                'frontend_dir = "src/frontend"',
                "",
                "[tool.forge_template]",
                'name = "plain"',
                "schema_version = 1",
                'forge_version_range = ">=2.0.0,<3.0.0"',
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def _write_plugin_project(tmp_path: Path) -> Path:
    project_dir = _write_project(tmp_path)
    plugin_dir = project_dir / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "demo_plugin.py").write_text(
        "\n".join(
            [
                'manifest = {"name": "demo-plugin", "version": "0.1.0", "forge_version": ">=2.0.0,<3.0.0"}',
                '',
                'def register(app):',
                '    return None',
            ]
        ),
        encoding="utf-8",
    )
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\n[plugins]\nenabled = true\npaths = [\"plugins\"]\n",
        encoding="utf-8",
    )
    return project_dir


def test_project_payload_reports_valid_project(tmp_path: Path) -> None:
    project_dir = _write_project(tmp_path)

    payload = _project_payload(project_dir)

    assert payload["exists"] is True
    assert payload["valid"] is True
    assert payload["entry_exists"] is True
    assert payload["frontend_exists"] is True
    assert payload["app"] == {"name": "CLI Test", "version": "1.2.3"}
    assert payload["protocol"] == {"schemes": []}
    assert payload["packaging"]["formats"] == ["dir"]
    assert payload["signing"]["enabled"] is False
    assert payload["security"]["allowed_commands"] == []
    assert payload["plugins"]["enabled"] is False
    assert payload["template"]["valid"] is True
    assert payload["errors"] == []


def test_resolve_project_dir_uses_cwd_relative_path(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "app"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "forge.toml").write_text("[app]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    assert _resolve_project_dir("app") == project_dir.resolve()


def test_resolve_project_dir_falls_back_to_module_root(tmp_path: Path, monkeypatch) -> None:
    module_root = tmp_path / "forge-framework"
    fake_module_file = module_root / "forge_cli" / "main.py"
    fake_module_file.parent.mkdir(parents=True, exist_ok=True)
    fake_module_file.write_text("", encoding="utf-8")

    fallback_project = module_root / ".ci" / "forge_todo"
    fallback_project.mkdir(parents=True, exist_ok=True)
    (fallback_project / "forge.toml").write_text("[app]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    cwd_project = tmp_path / ".ci" / "forge_todo"
    cwd_project.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("forge_cli.main.__file__", str(fake_module_file))
    monkeypatch.chdir(tmp_path)

    assert _resolve_project_dir(".ci/forge_todo") == fallback_project.resolve()


def test_info_supports_json_output(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    monkeypatch.chdir(project_dir)
    result = runner.invoke(app, ["info", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["forge_version"] == "2.0.0"
    assert payload["project"]["app"] == {"name": "CLI Test", "version": "1.2.3"}
    assert payload["project"]["entry_exists"] is True
    assert payload["project"]["template"]["name"] == "plain"


def test_doctor_supports_json_output(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    def fake_doctor_payload(project_path: Path) -> dict[str, object]:
        assert project_path == project_dir
        return {
            "forge_version": "2.0.0",
            "ok": True,
            "environment": {
                "os": "Linux",
                "os_version": "test",
                "machine": "x86_64",
                "checks": {
                    "python": {"status": "ok", "version": "3.14.3", "required": ">=3.14"},
                    "threading": {"status": "ok", "free_threaded": True, "detail": "Free-threaded"},
                    "rust_core": {"status": "ok", "detail": "Available"},
                    "cargo": {"status": "ok", "path": "/usr/bin/cargo"},
                    "rustc": {"status": "ok", "path": "/usr/bin/rustc"},
                    "maturin": {"status": "ok", "path": "/usr/bin/maturin"},
                    "uvicorn": {"status": "ok"},
                    "msgpack": {"status": "ok"},
                    "cryptography": {"status": "ok"},
                },
            },
            "project": {
                "path": str(project_dir),
                "config_path": str(project_dir / "forge.toml"),
                "exists": True,
                "valid": True,
                "errors": [],
                "template": {"present": True, "valid": True, "name": "plain", "schema_version": 1, "forge_version_range": ">=2.0.0,<3.0.0", "errors": []},
                "entry_path": str(project_dir / "src" / "main.py"),
                "frontend_path": str(project_dir / "src" / "frontend"),
                "entry_exists": True,
                "frontend_exists": True,
            },
        }

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._doctor_payload", fake_doctor_payload)
    result = runner.invoke(app, ["doctor", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["project"]["exists"] is True


def test_doctor_returns_nonzero_for_missing_project(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", str(tmp_path), "--output", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["project"]["exists"] is False
    assert "No forge.toml found" in payload["project"]["errors"]


def test_project_payload_reports_invalid_template_contract(tmp_path: Path) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'forge_version_range = ">=2.0.0,<3.0.0"',
            'forge_version_range = ">=3.0.0,<4.0.0"',
        ),
        encoding="utf-8",
    )

    payload = _project_payload(project_dir)

    assert payload["template"]["valid"] is False
    assert any("Template requires Forge" in error for error in payload["errors"])


def test_create_copies_template_contract_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["create", "sample-app", "--template", "plain", "--author", "Forge Tester"],
    )

    assert result.exit_code == 0
    generated = (tmp_path / "sample-app" / "forge.toml").read_text(encoding="utf-8")
    assert "[tool.forge_template]" in generated
    assert 'forge_version_range = ">=2.0.0,<3.0.0"' in generated


def test_create_generates_frontend_workspace_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["create", "workspace-app", "--template", "react", "--author", "Forge Tester"])

    assert result.exit_code == 0
    package_json = json.loads((tmp_path / "workspace-app" / "package.json").read_text(encoding="utf-8"))
    vite_config = (tmp_path / "workspace-app" / "vite.config.mjs").read_text(encoding="utf-8")
    forge_toml = (tmp_path / "workspace-app" / "forge.toml").read_text(encoding="utf-8")

    assert package_json["devDependencies"]["@forgedesk/vite-plugin"] == "^2.0.0"
    assert package_json["dependencies"]["@forgedesk/api"] == "^2.0.0"
    assert "forgeVitePlugin" in vite_config
    assert 'dev_server_command = "npm run dev"' in forge_toml
    assert 'dev_server_url = "http://127.0.0.1:5173"' in forge_toml


def test_create_prompts_for_template_when_not_provided(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("forge_cli.main._setup_python_env", lambda _project_dir: None)

    def fake_prompt(message: str, *args, **kwargs):
        if message == "Choose template":
            return "vue"
        return kwargs.get("default", "")

    monkeypatch.setattr("forge_cli.main.Prompt.ask", fake_prompt)

    result = runner.invoke(
        app,
        ["create", "prompted-app", "--author", "Forge Tester"],
    )

    assert result.exit_code == 0
    package_json = json.loads((tmp_path / "prompted-app" / "package.json").read_text(encoding="utf-8"))
    assert package_json["dependencies"]["vue"]


def test_templates_use_forge_api_package() -> None:
    template_files = [
        Path("forge_cli/templates/plain/src/frontend/main.js"),
        Path("forge_cli/templates/react/src/frontend/App.jsx"),
        Path("forge_cli/templates/vue/src/frontend/App.vue"),
        Path("forge_cli/templates/svelte/src/frontend/App.svelte"),
    ]

    for template_file in template_files:
        content = template_file.read_text(encoding="utf-8")
        assert "@forgedesk/api" in content
        assert "window.__forge__" not in content


def test_watch_snapshot_ignores_output_directory(tmp_path: Path) -> None:
    project_dir = _write_project(tmp_path)
    output_dir = project_dir / "dist"
    output_dir.mkdir()
    (output_dir / "generated.js").write_text("console.log('generated')", encoding="utf-8")
    watched_file = project_dir / "src" / "frontend" / "index.html"

    from forge.config import ForgeConfig

    config = ForgeConfig.from_file(project_dir / "forge.toml")
    snapshot = _watch_snapshot(project_dir, config)

    assert str(watched_file.resolve()) in snapshot
    assert str((output_dir / "generated.js").resolve()) not in snapshot


def test_run_dev_loop_without_hot_reload_waits_for_process(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    from forge.config import ForgeConfig

    config = ForgeConfig.from_file(project_dir / "forge.toml")

    class FakeProcess:
        def wait(self) -> int:
            return 0

    monkeypatch.setattr("forge_cli.main._launch_dev_process", lambda entry, project: FakeProcess())

    result = runner.invoke(app, ["dev", str(project_dir), "--no-hot-reload"])

    assert result.exit_code == 0


def test_launch_dev_server_sets_env_for_app(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            '[dev]\nfrontend_dir = "src/frontend"',
            '[dev]\nfrontend_dir = "src/frontend"\n'
            'dev_server_command = "python -m http.server 4173"\n'
            'dev_server_url = "http://127.0.0.1:4173"',
        ),
        encoding="utf-8",
    )

    from forge.config import ForgeConfig

    config = ForgeConfig.from_file(project_dir / "forge.toml")

    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: int | None = None) -> int:
            return 0

        def kill(self) -> None:
            self.terminated = True

    fake_process = FakeProcess()

    monkeypatch.setattr("forge_cli.main.subprocess.Popen", lambda *args, **kwargs: fake_process)
    monkeypatch.setattr("forge_cli.main._wait_for_http_ready", lambda url, timeout_seconds: None)

    process, env = _launch_dev_server(project_dir, config)

    assert process is fake_process
    assert env == {"FORGE_DEV_SERVER_URL": "http://127.0.0.1:4173"}


def test_build_supports_json_output_for_web_target(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    monkeypatch.chdir(project_dir)
    result = runner.invoke(app, ["build", "--target", "web", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "web"
    assert payload["validation"]["ok"] is True
    assert payload["build"]["builder"] == "static-copy"
    assert payload["build"]["target"] == "web"
    assert any(path.replace("\\", "/").endswith("dist/static/forge.js") for path in payload["build"]["artifacts"])


def test_build_returns_nonzero_json_for_missing_frontend(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    frontend_dir = project_dir / "src" / "frontend"
    for child in frontend_dir.iterdir():
        child.unlink()
    frontend_dir.rmdir()

    monkeypatch.chdir(project_dir)
    result = runner.invoke(app, ["build", "--target", "web", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["validation"]["ok"] is False
    assert any("Frontend directory missing" in error for error in payload["validation"]["errors"])


def test_build_returns_nonzero_json_when_no_desktop_builder_available(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(
        "forge_cli.main._module_available",
        lambda name: False if name == "nuitka" else True,
    )
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: None if name in ("maturin", "nuitka", "nuitka3") else "/usr/bin/tool")

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["validation"]["ok"] is False
    assert any("No supported desktop build tool found" in error for error in payload["validation"]["errors"])


def test_build_json_reports_packaging_and_signing_warnings(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[protocol]\n"
        + 'schemes = ["forge"]\n\n'
        + "[signing]\n"
        + "enabled = true\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", lambda *args, **kwargs: None)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["validation"]["packaging"]["protocol_schemes"] == ["forge"]
    assert any("packaging.app_id should be set" in warning for warning in payload["validation"]["warnings"])
    assert any("signing.enabled is true" in warning for warning in payload["validation"]["warnings"])


def test_build_json_reports_plugin_warning_when_enabled_without_entries(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\n[plugins]\nenabled = true\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", lambda *args, **kwargs: None)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert any("plugins.enabled is true" in warning for warning in payload["validation"]["warnings"])


def test_build_generates_package_descriptors_for_protocol_handlers(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[protocol]\n"
        + 'schemes = ["forge"]\n\n'
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'category = "Utility"\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr(
        "forge_cli.main.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="", stderr=""),
    )

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    package = payload["build"]["package"]
    descriptor_types = {item["type"] for item in package["descriptors"]}
    assert package["manifest_path"].endswith("forge-package.json")
    assert Path(package["manifest_path"]).exists()
    assert "package-manifest" in descriptor_types
    assert "protocol-manifest" in descriptor_types
    if platform.system() == "Linux":
        assert "linux-desktop-entry" in descriptor_types


def test_build_generates_plugin_contract_manifest(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_plugin_project(tmp_path)

    def fake_run(args, **kwargs):
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    package = payload["build"]["package"]
    descriptor_types = {item["type"] for item in package["descriptors"]}
    plugin_manifest = next(item for item in package["descriptors"] if item["type"] == "plugin-manifest")
    plugin_payload = json.loads(Path(plugin_manifest["path"]).read_text(encoding="utf-8"))

    assert "plugin-manifest" in descriptor_types
    assert plugin_payload["enabled"] is True
    assert plugin_payload["contracts"][0]["name"] == "demo-plugin"
    assert plugin_payload["contracts"][0]["valid"] is True


def test_build_executes_sign_and_verify_hooks(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n\n'
        + "[signing]\n"
        + "enabled = true\n"
        + 'sign_command = "python sign.py"\n'
        + 'verify_command = "python verify.py"\n',
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["build"]["signing"]["enabled"] is True
    assert payload["build"]["signing"]["sign"]["status"] == "ok"
    assert payload["build"]["signing"]["verify"]["status"] == "ok"
    assert calls[1] == ["python", "sign.py"]
    assert calls[2] == ["python", "verify.py"]


def test_build_generates_linux_deb_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "deb"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installers = payload["build"]["installers"]
    assert installers[0]["format"] == "deb"
    assert Path(installers[0]["path"]).exists()


def test_build_generates_macos_app_bundle(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "app"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Darwin")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installers = payload["build"]["installers"]
    assert installers[0]["format"] == "app"
    assert Path(installers[0]["path"]).exists()


def test_build_generates_windows_msi_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "msi"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(str(args[0])).name == "wixl":
            output_path = Path(args[args.index("-o") + 1])
            output_path.write_text("msi", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: "/usr/bin/wixl" if name == "wixl" else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Windows")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installers = payload["build"]["installers"]
    assert installers[0]["format"] == "msi"
    assert Path(installers[0]["path"]).exists()


def test_build_generates_linux_appimage_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "appimage"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(args[0]).name == "appimagetool":
            Path(args[-1]).write_text("appimage", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: "/usr/bin/appimagetool" if name == "appimagetool" else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installer = next(item for item in payload["build"]["installers"] if item["format"] == "appimage")
    assert Path(installer["path"]).exists()
    appdir = Path(installer["appdir"])
    root_desktop = appdir / "cli-test.desktop"
    shared_desktop = appdir / "usr" / "share" / "applications" / "cli-test.desktop"
    assert root_desktop.exists()
    assert shared_desktop.exists()
    assert "Icon=cli-test" in root_desktop.read_text(encoding="utf-8")
    assert (appdir / "cli-test.svg").exists()


def test_build_generates_linux_flatpak_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "flatpak"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(args[0]).name == "flatpak":
            Path(args[3]).write_text("flatpak", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in {"flatpak-builder", "flatpak"} else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installer = next(item for item in payload["build"]["installers"] if item["format"] == "flatpak")
    assert Path(installer["path"]).exists()


def test_build_generates_macos_dmg_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "dmg"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(args[0]).name == "hdiutil":
            Path(args[-1]).write_text("dmg", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: "/usr/bin/hdiutil" if name == "hdiutil" else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Darwin")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installer = next(item for item in payload["build"]["installers"] if item["format"] == "dmg")
    assert Path(installer["path"]).exists()


def test_build_generates_windows_nsis_installer(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "nsis"]\n',
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(args[0]).name == "makensis":
            script = Path(args[-1])
            out_file = next(
                line.split('"', 2)[1]
                for line in script.read_text(encoding="utf-8").splitlines()
                if line.startswith("OutFile ")
            )
            Path(out_file).write_text("nsis", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: "/usr/bin/makensis" if name == "makensis" else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Windows")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installer = next(item for item in payload["build"]["installers"] if item["format"] == "nsis")
    assert Path(installer["path"]).exists()


def test_build_generates_windows_nsis_installer_with_fallback_path(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'product_name = "CLI Test"\n'
        + 'formats = ["dir", "nsis"]\n',
        encoding="utf-8",
    )

    nsis_dir = tmp_path / "Program Files (x86)" / "NSIS"
    nsis_dir.mkdir(parents=True, exist_ok=True)
    (nsis_dir / "makensis.exe").write_text("", encoding="utf-8")

    def fake_run(args, **kwargs):
        args = list(args)
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        elif args and Path(str(args[0])).name.lower().startswith("makensis"):
            script = Path(args[-1])
            out_file = next(
                line.split('"', 2)[1]
                for line in script.read_text(encoding="utf-8").splitlines()
                if line.startswith("OutFile ")
            )
            Path(out_file).write_text("nsis", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: None if name == "makensis" else "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Windows")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    installer = next(item for item in payload["build"]["installers"] if item["format"] == "nsis")
    assert Path(installer["path"]).exists()


def test_build_fails_when_appimage_tool_is_missing(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'formats = ["dir", "appimage"]\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool" if name != "appimagetool" else None)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("appimagetool" in error for error in payload["validation"]["errors"])


def test_build_fails_when_flatpak_tools_are_missing(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'formats = ["dir", "flatpak"]\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: None if name in {"flatpak-builder", "flatpak"} else "/usr/bin/tool",
    )

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("flatpak-builder" in error for error in payload["validation"]["errors"])


def test_build_fails_when_dmg_tool_is_missing(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'formats = ["dir", "dmg"]\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Darwin")
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: None if name == "hdiutil" else "/usr/bin/tool")

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("hdiutil" in error for error in payload["validation"]["errors"])


def test_build_fails_when_nsis_tool_is_missing(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n[packaging]\n"
        + 'app_id = "dev.forge.cli"\n'
        + 'formats = ["dir", "nsis"]\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "forge_cli.main._find_packaging_tool",
        lambda name: None if name == "makensis" else "/usr/bin/tool",
    )

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("makensis" in error for error in payload["validation"]["errors"])


def test_build_uses_default_gpg_signing_adapter(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n\n'
        + "[signing]\n"
        + "enabled = true\n"
        + 'identity = "Forge Test Key"\n',
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr(
        "forge_cli.main.shutil.which",
        lambda name: "/usr/bin/gpg" if name == "gpg" else "/usr/bin/tool",
    )
    monkeypatch.setattr("forge_cli.main.platform.system", lambda: "Linux")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["build", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["build"]["signing"]["enabled"] is True
    assert payload["build"]["signing"]["adapter"] == "gpg"
    assert isinstance(payload["build"]["signing"]["sign"], list)
    assert isinstance(payload["build"]["signing"]["verify"], list)
    assert any(command[:2] == ["/usr/bin/gpg", "--batch"] for command in calls[1:])
    assert any(command[:2] == ["/usr/bin/gpg", "--verify"] for command in calls[1:])


def test_release_generates_manifest_json(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    def fake_run(args, **kwargs):
        if list(args)[:2] == ["maturin", "build"]:
            output_dir = Path(args[args.index("--out") + 1])
            (output_dir / "cli_test.whl").write_text("wheel", encoding="utf-8")
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["release", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["build"]["status"] == "ok"
    manifest_path = Path(payload["release"]["manifest_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["format_version"] == 1
    assert manifest["app"]["name"] == "CLI Test"
    assert any(item["path"].endswith(("cli_test.whl", "cli_test.bin")) for item in manifest["artifacts"])


def test_package_command_returns_manifest_json(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)

    def fake_run(args, **kwargs):
        if "-m" in args and "nuitka" in args:
            output_arg = next(str(arg) for arg in args if str(arg).startswith("--output-dir="))
            output_dir = Path(output_arg.split("=", 1)[1])
            (output_dir / "cli_test.bin").write_text("binary", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["package", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["package"]["manifest_path"].endswith("forge-package.json")


def test_sign_command_uses_existing_manifest(tmp_path: Path, monkeypatch) -> None:
    project_dir = _write_project(tmp_path)
    output_dir = project_dir / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "cli_test.bin"
    artifact.write_text("binary", encoding="utf-8")
    manifest_path = output_dir / "forge-package.json"
    manifest_path.write_text(
        json.dumps({"artifacts": [str(artifact)]}, indent=2),
        encoding="utf-8",
    )

    config_path = project_dir / "forge.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "[packaging]\n"
        + 'app_id = "dev.forge.cli"\n\n'
        + "[signing]\n"
        + "enabled = true\n"
        + 'sign_command = "python sign.py"\n'
        + 'verify_command = "python verify.py"\n',
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("forge_cli.main._module_available", lambda name: True)
    monkeypatch.setattr("forge_cli.main.shutil.which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr("forge_cli.main.subprocess.run", fake_run)

    result = runner.invoke(app, ["sign", "--result-format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["sign"]["manifest_path"].endswith("forge-package.json")
    assert payload["sign"]["signing"]["sign"]["status"] == "ok"
    assert calls[0] == ["python", "sign.py"]
    assert calls[1] == ["python", "verify.py"]
