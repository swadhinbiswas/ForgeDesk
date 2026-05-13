from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("release"), dict):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("build"), dict):
        return {"build": payload}
    raise ValueError(f"Unsupported release payload: {path}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _normalize_paths(values: list[str]) -> list[str]:
    return [str(Path(value)) for value in values]


def verify_release_payload(
    payload: dict[str, Any], *, payload_path: Path | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Release payload must be a JSON object")

    build = payload.get("build")
    if not isinstance(build, dict):
        raise ValueError("Build payload missing from release result")

    release = payload.get("release", {})
    if not isinstance(release, dict):
        raise ValueError("Release section must be a JSON object")

    build_artifacts = _normalize_paths([str(path) for path in build.get("artifacts", [])])
    if not build_artifacts:
        raise ValueError("Build payload does not list any artifacts")

    package = build.get("package")
    if not isinstance(package, dict):
        raise ValueError("Package metadata missing from build payload")

    package_manifest_path = package.get("manifest_path")
    package_files = _normalize_paths([str(path) for path in package.get("files", [])])
    if not isinstance(package_manifest_path, str) or not package_manifest_path:
        raise ValueError("Package manifest path missing from build payload")

    package_manifest_file = Path(package_manifest_path)
    if not package_manifest_file.exists():
        raise FileNotFoundError(f"Package manifest not found: {package_manifest_file}")

    package_manifest = _read_json(package_manifest_file)
    package_app = package_manifest.get("app", {})
    if not isinstance(package_app, dict):
        raise ValueError("Package manifest app section must be an object")
    expected_package_artifacts = [path for path in build_artifacts if path not in package_files]
    package_manifest_artifacts = _normalize_paths(
        [str(path) for path in package_manifest.get("artifacts", [])]
    )
    if package_manifest_artifacts != expected_package_artifacts:
        raise ValueError(
            "Package manifest artifacts do not match build artifacts\n"
            f"expected={expected_package_artifacts}\n"
            f"actual={package_manifest_artifacts}"
        )

    release_manifest = release.get("manifest")
    if not isinstance(release_manifest, dict):
        raise ValueError("Release manifest missing from payload")

    release_app = release_manifest.get("app", {})
    if not isinstance(release_app, dict):
        raise ValueError("Release manifest app section must be an object")

    if package_app.get("version") != release_app.get("version"):
        raise ValueError(
            "Package and release manifest versions differ\n"
            f"package={package_app.get('version')!r}\n"
            f"release={release_app.get('version')!r}"
        )
    if package_app.get("app_id") != release_app.get("app_id"):
        raise ValueError(
            "Package and release manifest app IDs differ\n"
            f"package={package_app.get('app_id')!r}\n"
            f"release={release_app.get('app_id')!r}"
        )
    if package_app.get("product_name") != release_app.get("product_name"):
        raise ValueError(
            "Package and release manifest product names differ\n"
            f"package={package_app.get('product_name')!r}\n"
            f"release={release_app.get('product_name')!r}"
        )

    release_manifest_path = release.get("manifest_path")
    if isinstance(release_manifest_path, str) and release_manifest_path:
        release_manifest_file = Path(release_manifest_path)
        if not release_manifest_file.exists():
            raise FileNotFoundError(f"Release manifest not found: {release_manifest_file}")
        disk_release_manifest = _read_json(release_manifest_file)
        if disk_release_manifest != release_manifest:
            raise ValueError(f"Release manifest file content mismatch: {release_manifest_file}")

    package_manifest_in_release = release_manifest.get("packaging")
    if isinstance(package_manifest_in_release, dict):
        manifest_path_from_release = package_manifest_in_release.get("manifest_path")
        if (
            isinstance(manifest_path_from_release, str)
            and Path(manifest_path_from_release) != package_manifest_file
        ):
            raise ValueError(
                "Release manifest packaging.manifest_path does not match package manifest path\n"
                f"package={package_manifest_file}\n"
                f"release={manifest_path_from_release}"
            )

    release_artifacts = release_manifest.get("artifacts", [])
    if not isinstance(release_artifacts, list) or not release_artifacts:
        raise ValueError("Release manifest does not list any artifacts")

    manifest_by_path = {
        str(Path(item.get("path"))): item
        for item in release_artifacts
        if isinstance(item, dict) and item.get("path")
    }

    for artifact_path in build_artifacts:
        path = Path(artifact_path)
        if not path.exists():
            raise FileNotFoundError(f"Release artifact missing: {path}")
        if not path.is_file():
            continue
        entry = manifest_by_path.get(str(path))
        if entry is None:
            raise ValueError(f"Artifact missing from release manifest: {path}")
        digest = _sha256(path)
        if digest != entry.get("sha256"):
            raise ValueError(f"Checksum mismatch for {path}: {digest} != {entry.get('sha256')}")

    version_alignment = release_manifest.get("version_alignment") or release.get(
        "version_alignment"
    )
    if isinstance(version_alignment, dict) and not version_alignment.get("aligned", False):
        mismatches = version_alignment.get("mismatches", [])
        raise ValueError("Version alignment failed:\n" + "\n".join(map(str, mismatches)))

    provenance = release_manifest.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Release provenance missing")
    if not provenance.get("workspace_root"):
        raise ValueError("Release provenance is missing workspace_root")

    package_versions = provenance.get("package_versions", [])
    if not isinstance(package_versions, list):
        raise ValueError("Release provenance package_versions must be a list")

    summary = {
        "ok": True,
        "artifacts": len(release_artifacts),
        "build_artifacts": len(build_artifacts),
        "package_manifest": str(package_manifest_file),
        "release_manifest": str(release_manifest_path)
        if isinstance(release_manifest_path, str)
        else None,
        "provenance": provenance,
    }
    if payload_path is not None:
        summary["payload"] = str(payload_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Forge release artifacts and provenance")
    parser.add_argument("--build-result", required=True)
    args = parser.parse_args()

    payload_path = Path(args.build_result)
    payload = _load_payload(payload_path)
    verify_release_payload(payload, payload_path=payload_path)


if __name__ == "__main__":
    main()
