from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_workspace_package_json_is_valid() -> None:
    package_json = _read_json(ROOT / "package.json")

    assert package_json["private"] is True
    assert package_json["workspaces"] == ["packages/*"]


def test_api_package_exposes_runtime_bindings() -> None:
    package_json = _read_json(ROOT / "packages" / "api" / "package.json")
    source = (ROOT / "packages" / "api" / "index.js").read_text(encoding="utf-8")
    typings = (ROOT / "packages" / "api" / "index.d.ts").read_text(encoding="utf-8")

    assert package_json["name"] == "@forgedesk/api"
    assert package_json["exports"]["."]["default"] == "./index.js"
    assert "export function getForge()" in source
    assert "export const forge" in source
    assert "export interface ForgeApi" in typings


def test_cli_wrapper_bootstraps_python_runtime() -> None:
    package_json = _read_json(ROOT / "packages" / "cli" / "package.json")
    wrapper = (ROOT / "packages" / "cli" / "bin" / "forge.js").read_text(encoding="utf-8")

    assert package_json["name"] == "@forgedesk/cli"
    assert package_json["bin"]["forge"] == "./bin/forge.js"
    assert "forge_cli.main" in wrapper
    assert "pip install forge-framework" in wrapper


def test_create_forge_app_scaffolder_targets_create_command() -> None:
    package_json = _read_json(ROOT / "packages" / "create-forge-app" / "package.json")
    wrapper = (ROOT / "packages" / "create-forge-app" / "bin" / "create-forge-app.js").read_text(encoding="utf-8")

    assert package_json["name"] == "@forgedesk/create-forge-app"
    assert package_json["bin"]["create-forge-app"] == "./bin/create-forge-app.js"
    assert '"create"' in wrapper
    assert "forge_cli.main" in wrapper


def test_vite_plugin_package_exports_plugin() -> None:
    package_json = _read_json(ROOT / "packages" / "vite-plugin" / "package.json")
    source = (ROOT / "packages" / "vite-plugin" / "index.js").read_text(encoding="utf-8")

    assert package_json["name"] == "@forgedesk/vite-plugin"
    assert "export function forgeVitePlugin" in source
    assert "transformIndexHtml" in source
