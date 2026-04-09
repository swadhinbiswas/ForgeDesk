from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from forge_cli.main import _release_manifest_payload


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "verify_release_artifacts.py"
_spec = spec_from_file_location("verify_release_artifacts", SCRIPT_PATH)
assert _spec and _spec.loader
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)
verify_release_payload = _module.verify_release_payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_verify_release_payload_validates_package_and_release_manifests(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output_dir = workspace / "dist"
    output_dir.mkdir(parents=True)

    app_bin = output_dir / "forge-app"
    helper_bin = output_dir / "forge-helper"
    package_manifest_file = output_dir / "forge-package.json"
    protocol_manifest_file = output_dir / "forge-protocols.json"
    release_manifest_file = output_dir / "forge-release.json"

    app_bin.write_text("app", encoding="utf-8")
    helper_bin.write_text("helper", encoding="utf-8")

    build_artifacts = [
        str(app_bin),
        str(helper_bin),
        str(package_manifest_file),
        str(protocol_manifest_file),
    ]

    package_manifest = {
        "format_version": 1,
        "target": "desktop",
        "builder": "maturin",
        "app": {"name": "Forge", "version": "2.0.0", "product_name": "Forge", "app_id": "dev.forge.app"},
        "protocol": {"schemes": []},
        "packaging": {"formats": ["dir"], "category": "Utility"},
        "signing": {"enabled": False, "adapter": None, "identity": None, "notarize": False, "timestamp_url": None},
        "output_dir": str(output_dir),
        "artifacts": [str(app_bin), str(helper_bin)],
    }
    package_manifest_file.write_text(json.dumps(package_manifest, indent=2, sort_keys=True), encoding="utf-8")
    protocol_manifest_file.write_text(json.dumps({"app_id": "dev.forge.app", "product_name": "Forge", "schemes": []}, indent=2, sort_keys=True), encoding="utf-8")

    release_manifest = {
        "format_version": 1,
        "forge_version": "2.0.0",
        "generated_at": "2026-03-30T00:00:00+00:00",
        "target": "desktop",
        "app": {"name": "Forge", "version": "2.0.0", "app_id": "dev.forge.app", "product_name": "Forge"},
        "protocol": {"schemes": []},
        "packaging": {"manifest_path": str(package_manifest_file)},
        "signing": {"enabled": False},
        "notarization": {"status": "skipped"},
            "provenance": {"workspace_root": str(workspace), "source_commit": "abc123"},
            "version_alignment": {"aligned": True},
            "provenance": {"workspace_root": str(workspace), "source_commit": "abc123"},
            "version_alignment": {"aligned": True},
        "artifacts": [
            {"path": str(app_bin), "sha256": _sha256(app_bin), "size": app_bin.stat().st_size},
            {"path": str(helper_bin), "sha256": _sha256(helper_bin), "size": helper_bin.stat().st_size},
            {"path": str(package_manifest_file), "sha256": _sha256(package_manifest_file), "size": package_manifest_file.stat().st_size},
            {"path": str(protocol_manifest_file), "sha256": _sha256(protocol_manifest_file), "size": protocol_manifest_file.stat().st_size},
        ],
    }
    release_manifest_file.write_text(json.dumps(release_manifest, indent=2, sort_keys=True), encoding="utf-8")

    payload = {
        "forge_version": "2.0.0",
        "ok": True,
        "target": "desktop",
        "project_dir": str(workspace),
        "config_path": str(workspace / "forge.toml"),
        "validation": {"ok": True, "warnings": [], "errors": []},
        "build": {
            "status": "ok",
            "target": "desktop",
            "builder": "maturin",
            "output_dir": str(output_dir),
            "artifacts": build_artifacts,
            "package": {
                "manifest_path": str(package_manifest_file),
                "files": [str(package_manifest_file), str(protocol_manifest_file)],
            },
            "installers": [],
        },
        "release": {
            "manifest_path": str(release_manifest_file),
            "manifest": release_manifest,
        },
    }

    summary = verify_release_payload(payload)

    assert summary["ok"] is True
    assert summary["artifacts"] == 4
    assert summary["build_artifacts"] == 4
    assert summary["package_manifest"] == str(package_manifest_file)
    assert summary["release_manifest"] == str(release_manifest_file)


def test_release_manifest_payload_uses_project_directory_for_alignment(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    project_dir = workspace / "example"
    project_dir.mkdir(parents=True)

    (workspace / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'version = "2.0.0"',
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "package.json").write_text(
        json.dumps({"version": "2.0.0"}, indent=2),
        encoding="utf-8",
    )
    packages_dir = workspace / "packages" / "api"
    packages_dir.mkdir(parents=True)
    (packages_dir / "package.json").write_text(
        json.dumps({"name": "@forgedesk/api", "version": "2.0.0"}, indent=2),
        encoding="utf-8",
    )

    artifact = project_dir / "artifact.bin"
    artifact.write_bytes(b"artifact")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "forge_cli.main.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="abc123\n"),
    )

    config = SimpleNamespace(
        app=SimpleNamespace(name="Forge", version="2.0.0"),
        packaging=SimpleNamespace(app_id="dev.forge.app", product_name="Forge"),
        protocol=SimpleNamespace(schemes=[]),
    )
    build_result = {"artifacts": [str(artifact)], "package": {"manifest_path": str(project_dir / "forge-package.json")}, "signing": {}, "notarization": {}}

    payload = _release_manifest_payload(config, "desktop", build_result, project_dir=workspace)

