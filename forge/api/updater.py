"""Forge updater verification, download, and apply flow."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from forge.bridge import command


_ALLOWED_CHANNELS = {"stable", "beta", "nightly"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _version_key(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", version)]
    return tuple(parts or [0])


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Return canonical bytes for manifest signature generation and verification."""
    manifest_copy = json.loads(json.dumps(manifest))
    release = manifest_copy.get("release")
    if isinstance(release, dict):
        release.pop("signature", None)
    return json.dumps(manifest_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "forge-app"


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _checksum_parts(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    if ":" in value:
        algorithm, digest = value.split(":", 1)
        return algorithm.lower(), digest.lower()
    return "sha256", value.lower()


def _compute_checksum(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_public_key(public_key: str) -> Ed25519PublicKey:
    key_candidate = public_key.strip()
    key_path = Path(key_candidate)
    if key_path.exists() and key_path.is_file():
        key_candidate = key_path.read_text(encoding="utf-8").strip()

    if "BEGIN PUBLIC KEY" in key_candidate:
        loaded = serialization.load_pem_public_key(key_candidate.encode("utf-8"))
        if not isinstance(loaded, Ed25519PublicKey):
            raise ValueError("Updater public key must be an Ed25519 public key")
        return loaded

    try:
        raw = base64.b64decode(key_candidate)
    except Exception as exc:  # pragma: no cover - defensive parsing branch
        raise ValueError("Updater public key must be PEM or base64-encoded Ed25519 bytes") from exc
    return Ed25519PublicKey.from_public_bytes(raw)


def _extract_safe_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            if not _is_relative_to(member_path, destination.resolve()):
                raise ValueError("Zip archive contains an invalid path outside the destination")
        archive.extractall(destination)


def _extract_safe_tar(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive.getmembers():
            member_path = (destination / member.name).resolve()
            if not _is_relative_to(member_path, destination.resolve()):
                raise ValueError("Tar archive contains an invalid path outside the destination")
        archive.extractall(destination, filter="data")


class UpdaterAPI:
    """Configuration-driven updater metadata and manifest helper API."""

    __forge_capability__ = "updater"

    def __init__(self, app_name: str, current_version: str, config: Any, base_dir: Path) -> None:
        self._app_name = app_name
        self._current_version = current_version
        self._config = config
        self._base_dir = Path(base_dir).resolve()
        self._state_dir = (self._base_dir / self._config.staging_dir).resolve()
        self._downloads_dir = self._state_dir / "downloads"
        self._extracts_dir = self._state_dir / "extracts"
        self._backups_dir = self._state_dir / "backups"
        self._metadata_dir = self._state_dir / "metadata"

    @command("updater_current_version", capability="updater")
    def current_version(self) -> str:
        """Return the current app version used by the updater."""
        return self._current_version

    @command("updater_channels", capability="updater")
    def channels(self) -> list[str]:
        """Return supported update channels."""
        return sorted(_ALLOWED_CHANNELS)

    @command("updater_config", capability="updater")
    def config(self) -> dict[str, Any]:
        """Return effective updater configuration."""
        return {
            "enabled": bool(self._config.enabled),
            "endpoint": self._config.endpoint,
            "channel": self._config.channel,
            "check_on_startup": bool(self._config.check_on_startup),
            "allow_downgrade": bool(self._config.allow_downgrade),
            "public_key": self._config.public_key,
            "require_signature": bool(self._config.require_signature),
            "staging_dir": self._config.staging_dir,
            "install_dir": self._config.install_dir,
        }

    @command("updater_manifest_schema", capability="updater")
    def manifest_schema(self) -> dict[str, Any]:
        """Return the updater release manifest schema descriptor."""
        return {
            "schema_version": "1",
            "required": ["schema_version", "app", "release"],
            "release_fields": [
                "version",
                "channel",
                "published_at",
                "notes",
                "signature",
                "signature_algorithm",
                "artifacts",
            ],
            "artifact_fields": ["platform", "url", "checksum", "kind", "target"],
            "signature": {
                "algorithm": "ed25519",
                "encoding": "base64",
                "covers": "canonical manifest JSON without release.signature",
            },
        }

    @command("updater_generate_manifest", capability="updater")
    def generate_manifest(
        self,
        version: str,
        url: str,
        destination: str | None = None,
        channel: str | None = None,
        notes: str | None = None,
        signature: str | None = None,
        checksum: str | None = None,
        platform: str = "any",
        published_at: str | None = None,
        kind: str = "archive",
        target: str | None = None,
    ) -> dict[str, Any]:
        """Generate a release manifest and optionally write it to disk."""
        release_channel = channel or self._config.channel
        manifest = {
            "schema_version": "1",
            "generated_at": _utc_now(),
            "app": {
                "name": self._app_name,
                "version": self._current_version,
            },
            "release": {
                "version": version,
                "channel": release_channel,
                "published_at": published_at or _utc_now(),
                "notes": notes or "",
                "signature": signature,
                "signature_algorithm": "ed25519",
                "artifacts": [
                    {
                        "platform": platform,
                        "url": url,
                        "checksum": checksum,
                        "kind": kind,
                        "target": target,
                    }
                ],
            },
        }

        if destination is not None:
            destination_path = Path(destination)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        return manifest

    @command("updater_check", capability="updater")
    def check(
        self,
        manifest_url: str | None = None,
        current_version: str | None = None,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Resolve and evaluate a release manifest against the current version."""
        source = manifest_url or self._config.endpoint
        if not source:
            raise ValueError("No updater manifest endpoint configured")

        manifest = self._load_manifest(source)
        release = manifest["release"]
        latest_version = str(release["version"])
        active_version = current_version or self._current_version
        update_available = self._is_update_available(active_version, latest_version)
        selected_artifact = self._select_artifact(manifest)
        verification = self._verify_manifest(manifest, public_key=public_key)

        return {
            "current_version": active_version,
            "latest_version": latest_version,
            "update_available": update_available,
            "channel": release.get("channel", self._config.channel),
            "endpoint": source,
            "notes": release.get("notes", ""),
            "published_at": release.get("published_at"),
            "signature": release.get("signature"),
            "artifact": selected_artifact,
            "signature_verified": verification["verified"],
            "verification": verification,
            "manifest": manifest,
        }

    @command("updater_verify", capability="updater")
    def verify(
        self,
        manifest_url: str | None = None,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Verify a manifest signature against the configured Ed25519 public key."""
        source = manifest_url or self._config.endpoint
        if not source:
            raise ValueError("No updater manifest endpoint configured")
        manifest = self._load_manifest(source)
        result = self._verify_manifest(manifest, public_key=public_key)
        result["endpoint"] = source
        return result

    @command("updater_download", capability="updater")
    def download(
        self,
        manifest_url: str | None = None,
        destination: str | None = None,
        artifact_url: str | None = None,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Download the selected update artifact after manifest verification."""
        manifest: dict[str, Any] | None = None
        selected_artifact: dict[str, Any] | None = None
        verification: dict[str, Any] = {
            "verified": False,
            "reason": "artifact_url_override",
            "algorithm": "ed25519",
            "public_key_configured": bool(public_key or self._config.public_key),
        }

        if artifact_url is None:
            source = manifest_url or self._config.endpoint
            if not source:
                raise ValueError("No updater manifest endpoint configured")
            manifest = self._load_manifest(source)
            selected_artifact = self._select_artifact(manifest)
            if selected_artifact is None:
                raise ValueError("No compatible updater artifact found for this platform")
            artifact_url = str(selected_artifact["url"])
            verification = self._verify_manifest(manifest, public_key=public_key)
            self._enforce_signature_requirement(verification)

        destination_path = self._default_download_path(artifact_url, destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        bytes_downloaded = self._download_artifact(artifact_url, destination_path)

        checksum = selected_artifact.get("checksum") if selected_artifact else None
        checksum_result = self._verify_checksum(destination_path, checksum)
        if checksum_result["expected"] and not checksum_result["verified"]:
            destination_path.unlink(missing_ok=True)
            raise ValueError("Downloaded updater artifact checksum verification failed")

        result = {
            "path": str(destination_path),
            "artifact": selected_artifact,
            "bytes_downloaded": bytes_downloaded,
            "checksum": checksum_result,
            "signature_verified": verification["verified"],
            "verification": verification,
            "manifest": manifest,
        }
        self._write_metadata("last-download.json", result)
        return result

    @command("updater_apply", capability="updater")
    def apply(
        self,
        download_path: str | None = None,
        manifest_url: str | None = None,
        install_dir: str | None = None,
        backup_dir: str | None = None,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Apply a downloaded update artifact with backup and rollback safety."""
        download_result: dict[str, Any] | None = None
        if download_path is None:
            download_result = self.download(manifest_url=manifest_url, public_key=public_key)
            download_path = str(download_result["path"])

        artifact_path = Path(download_path).resolve()
        if not artifact_path.exists():
            raise FileNotFoundError(f"Updater artifact not found: {artifact_path}")

        install_path = self._resolve_install_dir(install_dir)
        backup_path = self._resolve_backup_dir(backup_dir)
        extracted_path = self._extract_artifact(artifact_path)
        source_root = self._resolve_extracted_root(extracted_path)
        ignored_names = self._ignored_install_names(install_path)

        had_existing_install = install_path.exists() and any(install_path.iterdir())
        backup_created = False

        try:
            if had_existing_install:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.copytree(
                    install_path,
                    backup_path,
                    ignore=shutil.ignore_patterns(*sorted(ignored_names)),
                )
                backup_created = True
            install_path.mkdir(parents=True, exist_ok=True)
            self._sync_tree(source_root, install_path, ignored_names=ignored_names)
        except Exception:
            if backup_created:
                self._restore_backup(backup_path, install_path, ignored_names)
            raise

        release_version = None
        if download_result and isinstance(download_result.get("manifest"), dict):
            release_version = download_result["manifest"].get("release", {}).get("version")

        result = {
            "applied": True,
            "path": str(artifact_path),
            "install_dir": str(install_path),
            "backup_dir": str(backup_path) if backup_created else None,
            "extracted_dir": str(extracted_path),
            "version": release_version,
        }
        self._write_metadata("last-apply.json", result)
        return result

    @command("updater_update", capability="updater")
    def update(
        self,
        manifest_url: str | None = None,
        install_dir: str | None = None,
        destination: str | None = None,
        public_key: str | None = None,
    ) -> dict[str, Any]:
        """Check, download, and apply an update when one is available."""
        check_result = self.check(manifest_url=manifest_url, public_key=public_key)
        if not check_result["update_available"]:
            return {
                "updated": False,
                "reason": "no_update_available",
                "check": check_result,
            }

        download_result = self.download(
            manifest_url=manifest_url,
            destination=destination,
            public_key=public_key,
        )
        apply_result = self.apply(
            download_path=download_result["path"],
            manifest_url=manifest_url,
            install_dir=install_dir,
            public_key=public_key,
        )
        return {
            "updated": True,
            "check": check_result,
            "download": download_result,
            "apply": apply_result,
        }

    def _load_manifest(self, source: str) -> dict[str, Any]:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            with urlopen(source) as response:  # noqa: S310 - updater endpoint is explicit config
                payload = response.read().decode("utf-8")
        elif parsed.scheme == "file":
            payload = Path(parsed.path).read_text(encoding="utf-8")
        else:
            payload = Path(source).read_text(encoding="utf-8")

        manifest = json.loads(payload)
        self._validate_manifest(manifest)
        return manifest

    def _validate_manifest(self, manifest: dict[str, Any]) -> None:
        if not isinstance(manifest, dict):
            raise ValueError("Updater manifest must be a JSON object")
        if manifest.get("schema_version") != "1":
            raise ValueError("Unsupported updater manifest schema version")
        if not isinstance(manifest.get("app"), dict):
            raise ValueError("Updater manifest is missing an app section")
        release = manifest.get("release")
        if not isinstance(release, dict):
            raise ValueError("Updater manifest is missing a release section")
        if not release.get("version"):
            raise ValueError("Updater manifest release.version is required")
        if manifest.get("app", {}).get("name") not in {None, self._app_name}:
            raise ValueError("Updater manifest app.name does not match the current application")
        channel = release.get("channel", self._config.channel)
        if channel not in _ALLOWED_CHANNELS:
            raise ValueError(f"Unsupported update channel: {channel}")
        artifacts = release.get("artifacts")
        if artifacts is not None and not isinstance(artifacts, list):
            raise ValueError("Updater manifest release.artifacts must be a list")
        for artifact in artifacts or []:
            if not isinstance(artifact, dict):
                raise ValueError("Updater manifest artifacts must be objects")
            if not artifact.get("url"):
                raise ValueError("Updater manifest artifacts require a url")

    def _verify_manifest(self, manifest: dict[str, Any], public_key: str | None = None) -> dict[str, Any]:
        signature = manifest.get("release", {}).get("signature")
        configured_key = public_key or self._config.public_key
        result = {
            "verified": False,
            "reason": None,
            "algorithm": manifest.get("release", {}).get("signature_algorithm", "ed25519"),
            "public_key_configured": bool(configured_key),
        }

        if not signature and not configured_key:
            result["reason"] = "unsigned_manifest"
            return result
        if not signature:
            result["reason"] = "missing_signature"
            return result
        if not configured_key:
            result["reason"] = "missing_public_key"
            return result

        public = _load_public_key(configured_key)
        try:
            public.verify(base64.b64decode(signature), canonical_manifest_bytes(manifest))
        except InvalidSignature:
            result["reason"] = "invalid_signature"
            return result
        except Exception as exc:
            result["reason"] = f"verification_error:{exc}"
            return result

        result["verified"] = True
        result["reason"] = "verified"
        return result

    def _enforce_signature_requirement(self, verification: dict[str, Any]) -> None:
        if self._config.require_signature and not verification.get("verified"):
            raise ValueError(
                f"Updater manifest signature verification failed: {verification.get('reason')}"
            )

    def _select_artifact(self, manifest: dict[str, Any]) -> dict[str, Any] | None:
        artifacts = list(manifest.get("release", {}).get("artifacts") or [])
        if not artifacts:
            return None

        import platform

        system = platform.system().lower()
        aliases = {
            "darwin": {"darwin", "macos", "mac", "universal", "any"},
            "windows": {"windows", "win32", "any"},
            "linux": {"linux", "any"},
        }
        accepted = aliases.get(system, {system, "any"})
        for artifact in artifacts:
            artifact_platform = str(artifact.get("platform", "any")).lower()
            if artifact_platform in accepted:
                return artifact
        return artifacts[0]

    def _default_download_path(self, artifact_url: str, destination: str | None = None) -> Path:
        if destination is not None:
            return Path(destination).resolve()

        parsed = urlparse(artifact_url)
        name = Path(parsed.path or artifact_url).name or "update.bin"
        return (self._downloads_dir / name).resolve()

    def _download_artifact(self, source: str, destination: Path) -> int:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            with urlopen(source) as response, destination.open("wb") as output:  # noqa: S310
                total = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
                    total += len(chunk)
                return total

        source_path = Path(parsed.path if parsed.scheme == "file" else source).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Updater artifact not found: {source_path}")
        shutil.copy2(source_path, destination)
        return destination.stat().st_size

    def _verify_checksum(self, artifact_path: Path, checksum: str | None) -> dict[str, Any]:
        algorithm, expected = _checksum_parts(checksum)
        if not algorithm or not expected:
            return {
                "algorithm": algorithm,
                "expected": expected,
                "actual": None,
                "verified": False,
            }

        actual = _compute_checksum(artifact_path, algorithm)
        return {
            "algorithm": algorithm,
            "expected": expected,
            "actual": actual,
            "verified": actual == expected,
        }

    def _resolve_install_dir(self, install_dir: str | None = None) -> Path:
        target = install_dir or self._config.install_dir or str(self._base_dir)
        return Path(target).resolve()

    def _resolve_backup_dir(self, backup_dir: str | None = None) -> Path:
        if backup_dir is not None:
            return Path(backup_dir).resolve()
        timestamp = _utc_now().replace(":", "-")
        return (self._backups_dir / timestamp).resolve()

    def _extract_artifact(self, artifact_path: Path) -> Path:
        extract_target = (self._extracts_dir / artifact_path.stem).resolve()
        if extract_target.exists():
            shutil.rmtree(extract_target)
        extract_target.mkdir(parents=True, exist_ok=True)

        name = artifact_path.name.lower()
        if name.endswith(".zip"):
            _extract_safe_zip(artifact_path, extract_target)
            return extract_target
        if name.endswith((".tar.gz", ".tgz", ".tar", ".tar.bz2", ".tar.xz")):
            _extract_safe_tar(artifact_path, extract_target)
            return extract_target

        direct_dir = extract_target / "payload"
        direct_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, direct_dir / artifact_path.name)
        return extract_target

    def _resolve_extracted_root(self, extracted_path: Path) -> Path:
        children = [child for child in extracted_path.iterdir() if child.name != "__MACOSX"]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return extracted_path

    def _ignored_install_names(self, install_path: Path) -> set[str]:
        ignored: set[str] = set()
        if _is_relative_to(self._state_dir, install_path):
            ignored.add(self._state_dir.relative_to(install_path).parts[0])
        return ignored

    def _sync_tree(self, source_root: Path, target_root: Path, ignored_names: set[str]) -> None:
        source_entries = {entry.name: entry for entry in source_root.iterdir()}
        target_entries = {entry.name: entry for entry in target_root.iterdir() if entry.name not in ignored_names}

        for name, target_entry in target_entries.items():
            if name not in source_entries:
                if target_entry.is_dir():
                    shutil.rmtree(target_entry)
                else:
                    target_entry.unlink()

        for name, source_entry in source_entries.items():
            target_entry = target_root / name
            if source_entry.is_dir():
                if target_entry.exists() and not target_entry.is_dir():
                    target_entry.unlink()
                target_entry.mkdir(parents=True, exist_ok=True)
                self._sync_tree(source_entry, target_entry, ignored_names=set())
            else:
                if target_entry.exists() and target_entry.is_dir():
                    shutil.rmtree(target_entry)
                shutil.copy2(source_entry, target_entry)

    def _restore_backup(self, backup_path: Path, install_path: Path, ignored_names: set[str]) -> None:
        for entry in list(install_path.iterdir()):
            if entry.name in ignored_names:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        if backup_path.exists():
            self._sync_tree(backup_path, install_path, ignored_names=set())

    def _write_metadata(self, name: str, payload: dict[str, Any]) -> None:
        self._metadata_dir.mkdir(parents=True, exist_ok=True)
        (self._metadata_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _is_update_available(self, current_version: str, latest_version: str) -> bool:
        current_key = _version_key(current_version)
        latest_key = _version_key(latest_version)
        if latest_key > current_key:
            return True
        if latest_key < current_key and self._config.allow_downgrade:
            return True
        return False
