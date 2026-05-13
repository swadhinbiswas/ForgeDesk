from __future__ import annotations

import argparse
import ast
import json
import tomllib
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_pyproject_version(path: Path) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise ValueError(f"Project version missing in {path}")
    return project["version"]


def _load_python_version(path: Path) -> str | None:
    if not path.exists():
        return None

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        return None
                    return value if isinstance(value, str) else None
    return None


def verify_alignment(workspace_root: Path) -> dict[str, Any]:
    pyproject_path = workspace_root / "pyproject.toml"
    root_package_path = workspace_root / "package.json"
    packages_dir = workspace_root / "packages"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"Missing pyproject.toml in {workspace_root}")

    version = _load_pyproject_version(pyproject_path)
    mismatches: list[str] = []

    python_packages = [
        workspace_root / "forge" / "__init__.py",
        workspace_root / "forge_cli" / "__init__.py",
    ]
    python_versions: list[dict[str, Any]] = []
    for python_file in python_packages:
        python_version = _load_python_version(python_file)
        python_versions.append(
            {
                "path": str(python_file),
                "version": python_version,
            }
        )
        if python_version is not None and python_version != version:
            mismatches.append(f"{python_file}: {python_version!r} != {version!r}")

    if root_package_path.exists():
        root_package = _load_json(root_package_path)
        if root_package.get("version") != version:
            mismatches.append(
                f"root package.json version {root_package.get('version')!r} != {version!r}"
            )

    package_versions: list[dict[str, Any]] = []
    if packages_dir.exists():
        for package_json_path in sorted(packages_dir.glob("*/package.json")):
            package = _load_json(package_json_path)
            package_version = package.get("version")
            package_versions.append(
                {
                    "name": package.get("name") or package_json_path.parent.name,
                    "version": package_version,
                    "path": str(package_json_path),
                }
            )
            if package_version != version:
                mismatches.append(f"{package_json_path}: {package_version!r} != {version!r}")

    return {
        "workspace_root": str(workspace_root),
        "version": version,
        "aligned": not mismatches,
        "mismatches": mismatches,
        "python_versions": python_versions,
        "packages": package_versions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Forge version alignment across package manifests"
    )
    parser.add_argument(
        "--workspace-root", default=str(Path.cwd()), help="Workspace root to validate"
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args()

    summary = verify_alignment(Path(args.workspace_root).resolve())
    if args.json:
        pass
    else:
        if summary["aligned"]:
            pass
        else:
            for _mismatch in summary["mismatches"]:
                pass

    raise SystemExit(0 if summary["aligned"] else 1)


if __name__ == "__main__":
    main()
