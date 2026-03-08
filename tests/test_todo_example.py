from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "examples" / "forge_todo" / "src" / "main.py"
spec = importlib.util.spec_from_file_location("forge_todo_example", MODULE_PATH)
assert spec and spec.loader
forge_todo_example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge_todo_example)
TodoStore = forge_todo_example.TodoStore


def test_todo_store_crud_filters_and_stats(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "tasks.json")

    created = store.create_task(
        title="Ship Forge Todo",
        description="Validate the example app.",
        priority="high",
        due_date="2026-03-08",
        tags=["Forge", "release", "forge"],
    )

    assert created["title"] == "Ship Forge Todo"
    assert created["priority"] == "high"
    assert created["tags"] == ["forge", "release"]

    updated = store.update_task(
        created["id"],
        title="Ship Forge Todo app",
        description="Desktop-ready example.",
        priority="medium",
        due_date="2026-03-10",
        tags=["desktop", "demo"],
    )
    store.set_completed(created["id"], True)

    completed = store.list_tasks(status="completed")
    active = store.list_tasks(status="active")
    stats = store.stats()

    assert updated["title"] == "Ship Forge Todo app"
    assert len(completed) == 1
    assert active == []
    assert stats["total"] == 1
    assert stats["completed"] == 1
    assert stats["completion_rate"] == 100.0


def test_todo_store_duplicate_import_export_and_storage(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "tasks.json")
    original = store.create_task(title="Review roadmap", priority="low")
    duplicate = store.duplicate_task(original["id"])
    export_path = tmp_path / "exports" / "tasks.json"

    export_result = store.export_tasks(export_path)
    imported_store = TodoStore(tmp_path / "imported" / "tasks.json")
    import_result = imported_store.import_tasks(export_path, merge=False)
    storage = imported_store.storage_info()

    assert duplicate["title"].endswith("(copy)")
    assert export_result["count"] == 2
    assert import_result["imported"] == 2
    assert imported_store.stats()["total"] == 2
    assert storage["exists"] is True
    assert storage["task_count"] == 2


def test_todo_store_rejects_invalid_due_date(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "tasks.json")

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        store.create_task(title="Broken date", due_date="03/08/2026")
