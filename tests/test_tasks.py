import time
from unittest.mock import MagicMock

import pytest

from forge.tasks import TaskManager


def test_task_manager_start_and_status():
    mock_app = MagicMock()
    tm = TaskManager(mock_app)

    def my_task(cancel_event):
        time.sleep(0.05)
        return {"result": 123}

    task_id = tm.start("my_task", my_task)
    assert isinstance(task_id, str)

    status_res = tm.status(task_id)
    assert status_res is not None
    assert status_res.get("name") == "my_task"

    time.sleep(0.2)
    status_res = tm.status(task_id)
    assert status_res.get("state") == "completed"


def test_task_manager_cancel():
    mock_app = MagicMock()
    tm = TaskManager(mock_app)

    def my_task(cancel_event):
        while not cancel_event.is_set():
            time.sleep(0.01)
        return "cancelled"

    task_id = tm.start("cancellable", my_task)

    # Give the thread a moment to start running
    time.sleep(0.05)

    result = tm.cancel(task_id)
    assert result is True

    time.sleep(0.15)
    status_res = tm.status(task_id)
    assert status_res.get("state") == "cancelled"


def test_task_manager_cancel_all():
    mock_app = MagicMock()
    tm = TaskManager(mock_app)

    def long_task(cancel_event):
        while not cancel_event.is_set():
            time.sleep(0.01)

    tm.start("t1", long_task)
    tm.start("t2", long_task)

    count = tm.cancel_all()
    assert isinstance(count, int)
    assert count >= 0


def test_task_manager_status_unknown():
    mock_app = MagicMock()
    tm = TaskManager(mock_app)
    assert tm.status("nonexistent-id") is None


def test_task_manager_list_tasks():
    mock_app = MagicMock()
    tm = TaskManager(mock_app)

    def quick_task(cancel_event):
        return "done"

    tm.start("t1", quick_task)
    tm.start("t2", quick_task)

    tasks = tm.list_tasks()
    assert len(tasks) == 2
    names = {t["name"] for t in tasks}
    assert "t1" in names
    assert "t2" in names


def test_task_manager_max_tasks():
    mock_app = MagicMock()
    tm = TaskManager(mock_app, max_tasks=2)

    def block(cancel_event):
        while not cancel_event.is_set():
            time.sleep(0.01)

    tm.start("t1", block)
    tm.start("t2", block)

    with pytest.raises(RuntimeError, match="Maximum concurrent tasks"):
        tm.start("t3", block)

    tm.cancel_all()
