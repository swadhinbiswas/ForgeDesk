from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "verify_version_alignment.py"
_spec = spec_from_file_location("verify_version_alignment", SCRIPT_PATH)
assert _spec and _spec.loader
_module = module_from_spec(_spec)
import sys
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
verify_alignment = _module.verify_alignment


def test_verify_alignment_reports_matching_versions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        "\n".join(["[project]", 'version = "2.0.0"']),
        encoding="utf-8",
    )
    (workspace / "package.json").write_text(json.dumps({"version": "2.0.0"}), encoding="utf-8")
    forge_pkg = workspace / "forge"
    forge_pkg.mkdir()
    (forge_pkg / "__init__.py").write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    forge_cli_pkg = workspace / "forge_cli"
    forge_cli_pkg.mkdir()
    (forge_cli_pkg / "__init__.py").write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    api_pkg = workspace / "packages" / "api"
    api_pkg.mkdir(parents=True)
    (api_pkg / "package.json").write_text(json.dumps({"name": "@forgedesk/api", "version": "2.0.0"}), encoding="utf-8")

    summary = verify_alignment(workspace)

    assert summary["aligned"] is True
    assert summary["version"] == "2.0.0"
    assert summary["mismatches"] == []
    assert len(summary["python_versions"]) == 2


def test_verify_alignment_reports_mismatches(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        "\n".join(["[project]", 'version = "2.0.0"']),
        encoding="utf-8",
    )
    (workspace / "package.json").write_text(json.dumps({"version": "2.1.0"}), encoding="utf-8")
    forge_pkg = workspace / "forge"
    forge_pkg.mkdir()
    (forge_pkg / "__init__.py").write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    forge_cli_pkg = workspace / "forge_cli"
    forge_cli_pkg.mkdir()
    (forge_cli_pkg / "__init__.py").write_text('__version__ = "2.1.0"\n', encoding="utf-8")

    summary = verify_alignment(workspace)

    assert summary["aligned"] is False
    assert any("package.json" in mismatch for mismatch in summary["mismatches"])
    assert any("forge_cli/__init__.py" in mismatch for mismatch in summary["mismatches"])
