"""Filesystem change notifications (polling; built-in extension)."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"
_MAX_FILES = 8000


def _iter_files(root: Path, recursive: bool) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    if recursive:
        for p in root.rglob("*"):
            if p.is_file():
                yield p
    else:
        for p in root.iterdir():
            if p.is_file():
                yield p


def _snapshot(paths: list[Path], recursive: bool) -> dict[str, tuple[float, int]]:
    snap: dict[str, tuple[float, int]] = {}
    n = 0
    for root in paths:
        for fp in _iter_files(root, recursive):
            n += 1
            if n > _MAX_FILES:
                raise OSError("too many files under watch paths")
            try:
                st = fp.stat()
                snap[str(fp.resolve())] = (st.st_mtime_ns, st.st_size)
            except OSError:
                continue
    return snap


class BuiltinFileWatchAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app
        self._stop_events: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def _paths_under_base(self, paths: list[str]) -> list[Path] | None:
        base = self._app.config.get_base_dir().resolve()
        out: list[Path] = []
        for raw in paths:
            p = Path(raw).expanduser()
            if not p.is_absolute():
                p = base / p
            try:
                p = p.resolve()
                p.relative_to(base)
            except (ValueError, OSError):
                return None
            out.append(p)
        return out

    def watch_start(
        self, paths: list[str], interval_ms: int = 1500, recursive: bool = True
    ) -> dict[str, Any]:
        """Poll mtimes under ``paths`` (must stay inside app dir); emits ``forge_fs_watch`` on changes."""  # noqa: E501
        resolved = self._paths_under_base(paths)
        if resolved is None:
            return {"ok": False, "error": "paths must stay under app directory"}
        for p in resolved:
            if not p.exists():
                return {"ok": False, "error": f"missing path: {p}"}

        stop = threading.Event()
        wid = str(uuid.uuid4())

        def runner() -> None:
            try:
                prev = _snapshot(resolved, recursive)
            except OSError as exc:
                logger.error("watch snapshot: %s", exc)
                return
            interval = max(0.2, min(float(interval_ms) / 1000.0, 60.0))
            while not stop.wait(interval):
                try:
                    cur = _snapshot(resolved, recursive)
                except OSError as exc:
                    logger.warning("watch poll: %s", exc)
                    continue
                if cur != prev:
                    try:
                        self._app.emit(
                            "forge_fs_watch",
                            {
                                "watch_id": wid,
                                "changed_paths": _diff_paths(prev, cur),
                            },
                        )
                    except Exception as exc:
                        logger.debug("watch emit: %s", exc)
                    prev = cur

        t = threading.Thread(target=runner, name=f"forge-watch-{wid[:8]}", daemon=True)
        with self._lock:
            self._stop_events[wid] = stop
            self._threads[wid] = t
        t.start()
        return {"ok": True, "watch_id": wid}

    def watch_stop(self, watch_id: str) -> dict[str, Any]:
        with self._lock:
            ev = self._stop_events.pop(watch_id, None)
            self._threads.pop(watch_id, None)
        if ev is None:
            return {"ok": False, "error": "unknown watch_id"}
        ev.set()
        return {"ok": True}


def _diff_paths(
    prev: dict[str, tuple[float, int]],
    cur: dict[str, tuple[float, int]],
) -> list[str]:
    out: list[str] = []
    for k, v in cur.items():
        if prev.get(k) != v:
            out.append(k)
    for k in prev:
        if k not in cur:
            out.append(k)
    return out[:500]


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinFileWatchAPI(app))
