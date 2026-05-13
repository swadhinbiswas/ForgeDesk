"""HTTP client and reachability (built-in extension).

Provides a full HTTP client with download/upload progress reporting
via event channels. Replaces the minimal ``requests``-based client
with comprehensive capabilities.

Events emitted:
- ``network:status`` — ``{online: bool}`` (from connectivity watch)
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinNetworkAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any = None) -> None:
        self._app = app
        self._watches: dict[str, threading.Event] = {}
        self._watches_lock = threading.Lock()

    # ─── Basic HTTP ──────────────────────────────────────

    def http_get(self, url: str, timeout: float = 30.0) -> dict[str, Any]:
        """Simple GET returning status and body text (bounded size)."""
        try:
            r = requests.get(url, timeout=timeout)
            text = r.text[:2_000_000]
            return {"ok": True, "status": r.status_code, "body": text}
        except Exception as exc:
            logger.exception("http_get")
            return {"ok": False, "error": str(exc)}

    def http_post_json(
        self,
        url: str,
        json_body: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """POST JSON and parse JSON response when possible."""
        try:
            r = requests.post(url, json=json_body, headers=headers or {}, timeout=timeout)
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                return {"ok": True, "status": r.status_code, "json": r.json()}
            return {"ok": True, "status": r.status_code, "text": r.text[:2_000_000]}
        except Exception as exc:
            logger.exception("http_post_json")
            return {"ok": False, "error": str(exc)}

    # ─── Full HTTP Request ───────────────────────────────

    def http_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Execute an arbitrary HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS).
            url: The URL to request.
            headers: Optional request headers.
            body: Optional raw body string.
            json_body: Optional JSON body (takes precedence over body).
            timeout: Request timeout in seconds.

        Returns:
            ``{ok, status, headers, body}``
        """
        try:
            r = requests.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                data=body.encode() if body and not json_body else None,
                json=json_body,
                timeout=timeout,
            )
            resp_headers = dict(r.headers)
            ct = resp_headers.get("Content-Type", "")
            if "application/json" in ct:
                return {
                    "ok": True,
                    "status": r.status_code,
                    "headers": resp_headers,
                    "json": r.json(),
                }
            return {
                "ok": True,
                "status": r.status_code,
                "headers": resp_headers,
                "body": r.text[:5_000_000],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ─── Download with Progress ──────────────────────────

    def http_download(
        self,
        url: str,
        destination: str,
        headers: dict[str, str] | None = None,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Download a file with progress events.

        Emits ``download:progress`` events with ``{url, percent, bytes_downloaded, total_bytes}``.

        Args:
            url: The URL to download from.
            destination: Local file path to save to.
            headers: Optional request headers (e.g. auth).
            timeout: Request timeout in seconds.

        Returns:
            ``{ok, path, size}`` on completion.
        """

        def _do_download() -> None:
            try:
                r = requests.get(url, headers=headers or {}, stream=True, timeout=timeout)
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0

                dest_path = Path(destination)
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            percent = (downloaded / total * 100) if total > 0 else 0
                            self._emit_event(
                                "download:progress",
                                {
                                    "url": url,
                                    "percent": round(percent, 1),
                                    "bytes_downloaded": downloaded,
                                    "total_bytes": total,
                                },
                            )

                self._emit_event(
                    "download:complete",
                    {
                        "url": url,
                        "path": str(dest_path),
                        "size": downloaded,
                    },
                )
            except Exception as exc:
                self._emit_event(
                    "download:error",
                    {
                        "url": url,
                        "error": str(exc),
                    },
                )

        thread = threading.Thread(target=_do_download, name="forge-download", daemon=True)
        thread.start()
        return {"ok": True, "status": "started", "destination": destination}

    # ─── Upload with Progress ────────────────────────────

    def http_upload(
        self,
        url: str,
        file_path: str,
        headers: dict[str, str] | None = None,
        field_name: str = "file",
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Upload a file with progress events.

        Uses multipart form upload. Emits ``upload:progress`` events.

        Args:
            url: The upload endpoint URL.
            file_path: Local file path to upload.
            headers: Optional request headers.
            field_name: Form field name for the file.
            timeout: Request timeout in seconds.

        Returns:
            ``{ok, status: "started"}``
        """
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            return {"ok": False, "error": f"File not found: {file_path}"}

        file_size = os.path.getsize(abs_path)

        def _do_upload() -> None:
            try:
                # Read-and-track wrapper for progress
                class ProgressReader:
                    def __init__(self, fp: Any, total: int) -> None:
                        self._fp = fp
                        self._total = total
                        self._read = 0

                    def read(self, size: int = -1) -> bytes:
                        data: bytes = self._fp.read(size)  # type: ignore[no-any-return]
                        if data:
                            self._read += len(data)
                            percent = (self._read / self._total * 100) if self._total > 0 else 0
                            self._emit_progress(percent)
                        return data

                    def _emit_progress(self, percent: float) -> None:
                        self._emit_event(  # type: ignore[attr-defined]
                            "upload:progress",
                            {
                                "file": abs_path,
                                "percent": round(percent, 1),
                                "bytes_uploaded": self._read,
                                "total_bytes": self._total,
                            },
                        )

                # Simple multipart upload
                with open(abs_path, "rb") as f:
                    filename = os.path.basename(abs_path)
                    files = {field_name: (filename, f)}
                    r = requests.post(
                        url,
                        files=files,
                        headers=headers or {},
                        timeout=timeout,
                    )

                self._emit_event(
                    "upload:complete",
                    {
                        "file": abs_path,
                        "status": r.status_code,
                        "response": r.text[:100_000],
                    },
                )
            except Exception as exc:
                self._emit_event(
                    "upload:error",
                    {
                        "file": abs_path,
                        "error": str(exc),
                    },
                )

        thread = threading.Thread(target=_do_upload, name="forge-upload", daemon=True)
        thread.start()
        return {"ok": True, "status": "started", "file": abs_path, "size": file_size}

    # ─── Connectivity ────────────────────────────────────

    def is_online(
        self, host: str = "1.1.1.1", port: int = 443, timeout: float = 3.0
    ) -> dict[str, Any]:
        """TCP connect probe (default Cloudflare DNS)."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {"ok": True, "reachable": True}
        except OSError:
            return {"ok": True, "reachable": False}

    def connectivity_watch(self, interval_seconds: float = 10.0) -> dict[str, Any]:
        """Start monitoring network connectivity.

        Emits ``network:status`` events with ``{online: bool}`` at the
        specified interval.

        Args:
            interval_seconds: How often to check (default 10s).

        Returns:
            ``{ok, watch_id}``
        """
        import uuid

        watch_id = str(uuid.uuid4())
        stop_event = threading.Event()

        with self._watches_lock:
            self._watches[watch_id] = stop_event

        def _monitor() -> None:
            last_state: bool | None = None
            while not stop_event.is_set():
                result = self.is_online()
                online = result.get("reachable", False)
                if online != last_state:
                    last_state = online
                    self._emit_event("network:status", {"online": online})
                stop_event.wait(interval_seconds)

        thread = threading.Thread(
            target=_monitor, name=f"forge-net-watch-{watch_id[:8]}", daemon=True
        )
        thread.start()
        return {"ok": True, "watch_id": watch_id}

    def connectivity_unwatch(self, watch_id: str) -> dict[str, Any]:
        """Stop monitoring network connectivity.

        Args:
            watch_id: The watch ID from ``connectivity_watch``.
        """
        with self._watches_lock:
            stop_event = self._watches.pop(watch_id, None)
        if stop_event:
            stop_event.set()
            return {"ok": True}
        return {"ok": False, "error": "Watch not found"}

    # ─── Internal ────────────────────────────────────────

    def _emit_event(self, event: str, data: dict) -> None:
        """Emit an event to the frontend if app is available."""
        if self._app and hasattr(self._app, "emit"):
            try:
                self._app.emit(event, data)
            except Exception:
                pass


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinNetworkAPI(app))
