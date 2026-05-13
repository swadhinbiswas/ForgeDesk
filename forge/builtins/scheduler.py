"""Thread-based one-shot and interval jobs (built-in extension)."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class _Job:
    __slots__ = ("timer", "cancelled")

    def __init__(self) -> None:
        self.timer: threading.Timer | None = None
        self.cancelled = False


_jobs: dict[str, _Job] = {}
_jobs_lock = threading.Lock()


class BuiltinSchedulerAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def schedule_ipc(
        self,
        delay_seconds: float,
        command: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """After ``delay_seconds``, invoke an IPC ``command`` on the bridge (same process)."""
        jid = str(uuid.uuid4())
        job = _Job()

        def fire() -> None:
            try:
                with _jobs_lock:
                    if job.cancelled:
                        return
                    _jobs.pop(jid, None)
                raw = json.dumps(
                    {"command": command, "id": jid, "args": args or {}},
                    separators=(",", ":"),
                )
                self._app.bridge.invoke_command(raw)
            except Exception as exc:
                logger.exception("schedule_ipc: %s", exc)

        timer = threading.Timer(delay_seconds, fire)
        job.timer = timer
        with _jobs_lock:
            _jobs[jid] = job
        timer.daemon = True
        timer.start()
        return {"job_id": jid}

    def cancel(self, job_id: str) -> bool:
        with _jobs_lock:
            job = _jobs.pop(job_id, None)
        if job is None:
            return False
        job.cancelled = True
        if job.timer:
            job.timer.cancel()
        return True


def register(app: Any) -> None:
    # schedule_ipc needs proper bridge invocation - read bridge for public API
    app.bridge.register_commands(BuiltinSchedulerAPI(app))
