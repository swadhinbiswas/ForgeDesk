"""Forge Background Task System.

Provides a managed task system for long-running background work in
Forge applications. Supports one-shot, persistent, and interval tasks
using daemon threads for NoGIL-friendly parallel execution.

NoGIL Notes:
    Tasks are plain daemon threads. Under Python 3.14+ free-threaded mode,
    they execute truly in parallel without GIL contention. The internal
    registry uses ``threading.Lock`` for safe mutation only.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """Internal state for a managed background task."""

    task_id: str
    name: str
    group: str | None = None
    state: TaskState = TaskState.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    result: Any = None
    thread: threading.Thread | None = field(default=None, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    interval: float | None = None  # If set, repeat every N seconds

    def snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "group": self.group,
            "state": self.state.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "interval": self.interval,
        }


class TaskManager:
    """Long-running background task system using daemon threads.

    Supports:
    - One-shot tasks: run a callable once, capture result
    - Persistent tasks: run until explicitly cancelled (e.g. WebSocket reader)
    - Interval tasks: run every N seconds (e.g. heartbeat, polling)
    - Task groups: cancel all tasks in a group at once

    All tasks are daemon threads so they don't block app shutdown.

    Args:
        app: The ForgeApp instance for event emission.
        max_tasks: Maximum number of concurrent tasks (default 50).
    """

    def __init__(self, app: Any = None, max_tasks: int = 50) -> None:
        self._app = app
        self._max_tasks = max_tasks
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def start(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        args: tuple = (),
        kwargs: dict | None = None,
        group: str | None = None,
        interval: float | None = None,
    ) -> str:
        """Start a new background task.

        Args:
            name: Human-readable task name.
            fn: The callable to execute. For persistent tasks, it should
                accept a ``cancel_event: threading.Event`` as first arg and
                check ``cancel_event.is_set()`` to know when to stop.
            args: Positional arguments for the callable.
            kwargs: Keyword arguments for the callable.
            group: Optional group name for bulk cancellation.
            interval: If set, repeat the callable every N seconds.

        Returns:
            The task_id string.

        Raises:
            RuntimeError: If max_tasks limit is reached.
        """
        kwargs = kwargs or {}

        with self._lock:
            active = sum(
                1 for t in self._tasks.values() if t.state in (TaskState.PENDING, TaskState.RUNNING)
            )
            if active >= self._max_tasks:
                raise RuntimeError(f"Maximum concurrent tasks ({self._max_tasks}) reached")

        task_id = str(uuid.uuid4())
        record = TaskRecord(
            task_id=task_id,
            name=name,
            group=group,
            interval=interval,
        )

        def _worker() -> None:
            record.state = TaskState.RUNNING
            record.started_at = time.monotonic()
            try:
                if interval is not None:
                    # Interval task: repeat until cancelled
                    while not record.cancel_event.is_set():
                        try:
                            fn(*args, **kwargs)
                        except Exception as exc:
                            logger.error("Task %s interval error: %s", name, exc)
                            self._emit_task_event("task:error", task_id, name, str(exc))
                        record.cancel_event.wait(interval)
                    record.state = TaskState.CANCELLED
                else:
                    # One-shot or persistent task
                    result = fn(record.cancel_event, *args, **kwargs)
                    if record.cancel_event.is_set():
                        record.state = TaskState.CANCELLED
                    else:
                        record.state = TaskState.COMPLETED
                        record.result = result
            except Exception as exc:
                record.state = TaskState.FAILED
                record.error = str(exc)
                logger.error("Task %s failed: %s", name, exc)
                self._emit_task_event("task:error", task_id, name, str(exc))
            finally:
                record.completed_at = time.monotonic()
                self._emit_task_event("task:completed", task_id, name, record.state.value)

        thread = threading.Thread(target=_worker, name=f"forge-task-{name}", daemon=True)
        record.thread = thread

        with self._lock:
            self._tasks[task_id] = record

        thread.start()
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a running task by ID.

        Returns:
            True if the task was found and cancellation was requested.
        """
        with self._lock:
            record = self._tasks.get(task_id)
        if record is None:
            return False
        record.cancel_event.set()
        return True

    def cancel_group(self, group: str) -> int:
        """Cancel all tasks in a group.

        Returns:
            The number of tasks cancelled.
        """
        count = 0
        with self._lock:
            targets = [
                t
                for t in self._tasks.values()
                if t.group == group and t.state in (TaskState.PENDING, TaskState.RUNNING)
            ]
        for task in targets:
            task.cancel_event.set()
            count += 1
        return count

    def cancel_all(self) -> int:
        """Cancel all running tasks. Used during app shutdown."""
        count = 0
        with self._lock:
            targets = [
                t for t in self._tasks.values() if t.state in (TaskState.PENDING, TaskState.RUNNING)
            ]
        for task in targets:
            task.cancel_event.set()
            count += 1
        return count

    def status(self, task_id: str) -> dict[str, Any] | None:
        """Get the status of a task."""
        with self._lock:
            record = self._tasks.get(task_id)
        return record.snapshot() if record else None

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks."""
        with self._lock:
            return [t.snapshot() for t in self._tasks.values()]

    def _emit_task_event(self, event: str, task_id: str, name: str, detail: str) -> None:
        """Emit a task lifecycle event if app is available."""
        if self._app and hasattr(self._app, "emit"):
            try:
                self._app.emit(
                    event,
                    {
                        "task_id": task_id,
                        "name": name,
                        "detail": detail,
                    },
                )
            except Exception:
                pass  # Don't let event emission errors crash the task
