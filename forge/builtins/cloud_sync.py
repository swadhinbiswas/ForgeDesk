"""S3-compatible and path-based sync helpers (built-in extension)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinCloudSyncAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def s3_list_objects(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """List objects in a bucket (requires ``boto3``)."""
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError:
            return {"ok": False, "error": "install boto3 for S3 support"}
        try:
            kwargs: dict[str, Any] = {}
            if endpoint_url:
                kwargs["endpoint_url"] = endpoint_url
            if region:
                kwargs["region_name"] = region
            client = boto3.client("s3", **kwargs)
            resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            keys = [o["Key"] for o in resp.get("Contents", [])]
            return {"ok": True, "keys": keys}
        except Exception as exc:
            logger.exception("s3_list_objects")
            return {"ok": False, "error": str(exc)}

    def s3_upload_file(
        self,
        bucket: str,
        key: str,
        local_path: str,
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file from disk (path resolved under app base if relative)."""
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError:
            return {"ok": False, "error": "install boto3 for S3 support"}
        p = Path(local_path).expanduser()
        if not p.is_absolute():
            p = (self._app.config.get_base_dir() / p).resolve()
        if not p.is_file():
            return {"ok": False, "error": f"file not found: {p}"}
        try:
            kwargs: dict[str, Any] = {}
            if endpoint_url:
                kwargs["endpoint_url"] = endpoint_url
            if region:
                kwargs["region_name"] = region
            client = boto3.client("s3", **kwargs)
            client.upload_file(str(p), bucket, key)
            return {"ok": True}
        except Exception as exc:
            logger.exception("s3_upload_file")
            return {"ok": False, "error": str(exc)}

    def providers(self) -> dict[str, Any]:
        """Report which optional cloud backends are importable."""
        out: dict[str, bool | str] = {}
        try:
            import boto3  # type: ignore[import-not-found]  # noqa: F401

            out["s3_boto3"] = True
        except ImportError:
            out["s3_boto3"] = False
        out["note"] = (
            "Dropbox/Google Drive need provider SDKs; use S3 or sync via filesystem + rclone."
        )
        return out


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinCloudSyncAPI(app))
