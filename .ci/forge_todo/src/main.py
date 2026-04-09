from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from forge import ForgeApp

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / ".forge-data"
STORE_PATH = DATA_DIR / "tasks.json"
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = str(tag).strip().lower()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _normalize_due_date(value: str | None) -> str | None:
    if value is None:
        return None
    clean_value = str(value).strip()
    if not clean_value:
        return None
    try:
        return date.fromisoformat(clean_value).isoformat()
    except ValueError as exc:
        raise ValueError("Due date must use YYYY-MM-DD format") from exc


class TodoStore:
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"version": 1, "tasks": []}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        self._ensure()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"version": 1, "tasks": []}
            self._save(payload)
        payload.setdefault("version", 1)
        payload.setdefault("tasks", [])
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _normalize_task_record(self, raw: dict[str, Any], *, existing_ids: set[str] | None = None) -> dict[str, Any]:
        title = str(raw.get("title", "")).strip()
        if not title:
            raise ValueError("Imported task title is required")
        existing_ids = existing_ids or set()
        task_id = str(raw.get("id") or uuid4())
        if task_id in existing_ids:
            task_id = str(uuid4())
        completed = bool(raw.get("completed", False))
        created_at = raw.get("created_at") or _now_iso()
        updated_at = raw.get("updated_at") or created_at
        updated_at_epoch = raw.get("updated_at_epoch")
        if not isinstance(updated_at_epoch, (int, float)):
            updated_at_epoch = datetime.now(timezone.utc).timestamp()
        return {
            "id": task_id,
            "title": title,
            "description": str(raw.get("description", "")).strip(),
            "priority": raw.get("priority") if raw.get("priority") in PRIORITY_ORDER else "medium",
            "due_date": _normalize_due_date(raw.get("due_date")),
            "tags": _normalize_tags(raw.get("tags")),
            "completed": completed,
            "created_at": str(created_at),
            "updated_at": str(updated_at),
            "updated_at_epoch": float(updated_at_epoch),
        }

    def _sort_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            tasks,
            key=lambda task: (
                1 if task.get("completed") else 0,
                PRIORITY_ORDER.get(task.get("priority", "medium"), 1),
                task.get("due_date") or "9999-12-31",
                -(task.get("updated_at_epoch") or 0),
            ),
        )

    def list_tasks(self, *, status: str = "all", search: str = "", priority: str = "all") -> list[dict[str, Any]]:
        tasks = self._load()["tasks"]
        query = search.strip().lower()
        filtered: list[dict[str, Any]] = []
        for task in tasks:
            if status == "active" and task.get("completed"):
                continue
            if status == "completed" and not task.get("completed"):
                continue
            if priority != "all" and task.get("priority") != priority:
                continue
            haystack = " ".join(
                [
                    task.get("title", ""),
                    task.get("description", ""),
                    " ".join(task.get("tags", [])),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            filtered.append(task)
        return self._sort_tasks(filtered)

    def create_task(
        self,
        *,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required")
        clean_priority = priority if priority in PRIORITY_ORDER else "medium"
        payload = self._load()
        now = _now_iso()
        epoch = datetime.now(timezone.utc).timestamp()
        task = {
            "id": str(uuid4()),
            "title": clean_title,
            "description": description.strip(),
            "priority": clean_priority,
            "due_date": _normalize_due_date(due_date),
            "tags": _normalize_tags(tags),
            "completed": False,
            "created_at": now,
            "updated_at": now,
            "updated_at_epoch": epoch,
        }
        payload["tasks"].append(task)
        self._save(payload)
        return task

    def update_task(
        self,
        task_id: str,
        *,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Task title is required")
        payload = self._load()
        for task in payload["tasks"]:
            if task["id"] == task_id:
                task["title"] = clean_title
                task["description"] = description.strip()
                task["priority"] = priority if priority in PRIORITY_ORDER else "medium"
                task["due_date"] = _normalize_due_date(due_date)
                task["tags"] = _normalize_tags(tags)
                task["updated_at"] = _now_iso()
                task["updated_at_epoch"] = datetime.now(timezone.utc).timestamp()
                self._save(payload)
                return task
        raise FileNotFoundError(f"Task not found: {task_id}")

    def set_completed(self, task_id: str, completed: bool) -> dict[str, Any]:
        payload = self._load()
        for task in payload["tasks"]:
            if task["id"] == task_id:
                task["completed"] = bool(completed)
                task["updated_at"] = _now_iso()
                task["updated_at_epoch"] = datetime.now(timezone.utc).timestamp()
                self._save(payload)
                return task
        raise FileNotFoundError(f"Task not found: {task_id}")

    def delete_task(self, task_id: str) -> bool:
        payload = self._load()
        tasks = payload["tasks"]
        remaining = [task for task in tasks if task["id"] != task_id]
        if len(remaining) == len(tasks):
            raise FileNotFoundError(f"Task not found: {task_id}")
        payload["tasks"] = remaining
        self._save(payload)
        return True

    def clear_completed(self) -> int:
        payload = self._load()
        tasks = payload["tasks"]
        remaining = [task for task in tasks if not task.get("completed")]
        removed = len(tasks) - len(remaining)
        payload["tasks"] = remaining
        self._save(payload)
        return removed

    def duplicate_task(self, task_id: str) -> dict[str, Any]:
        payload = self._load()
        for task in payload["tasks"]:
            if task["id"] == task_id:
                now = _now_iso()
                duplicate = {
                    **task,
                    "id": str(uuid4()),
                    "title": f"{task['title']} (copy)",
                    "completed": False,
                    "created_at": now,
                    "updated_at": now,
                    "updated_at_epoch": datetime.now(timezone.utc).timestamp(),
                }
                payload["tasks"].append(duplicate)
                self._save(payload)
                return duplicate
        raise FileNotFoundError(f"Task not found: {task_id}")

    def seed_demo(self) -> dict[str, Any]:
        payload = self._load()
        if payload["tasks"]:
            return {"created": 0, "skipped": True}
        demo_tasks = [
            {
                "title": "Ship Forge Todo example",
                "description": "Finish the full-stack task manager example and validate it.",
                "priority": "high",
                "due_date": datetime.now().date().isoformat(),
                "tags": ["forge", "release"],
            },
            {
                "title": "Review updater roadmap",
                "description": "Map release automation work to installer and notarization milestones.",
                "priority": "medium",
                "due_date": None,
                "tags": ["planning"],
            },
            {
                "title": "Polish desktop UX",
                "description": "Add keyboard shortcuts, empty states, and completion feedback.",
                "priority": "low",
                "due_date": None,
                "tags": ["ux"],
            },
        ]
        for item in demo_tasks:
            self.create_task(**item)
        return {"created": len(demo_tasks), "skipped": False}

    def export_tasks(self, export_path: Path) -> dict[str, Any]:
        payload = self._load()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "path": str(export_path),
            "count": len(payload["tasks"]),
            "size": export_path.stat().st_size,
        }

    def import_tasks(self, import_path: Path, *, merge: bool = True) -> dict[str, Any]:
        raw_payload = json.loads(import_path.read_text(encoding="utf-8"))
        return self.import_task_records(raw_payload, merge=merge, source=str(import_path))

    def export_payload(self) -> dict[str, Any]:
        return self._load()

    def import_task_records(
        self,
        raw_payload: dict[str, Any] | list[dict[str, Any]],
        *,
        merge: bool = True,
        source: str = "memory",
    ) -> dict[str, Any]:
        source_tasks = raw_payload.get("tasks", raw_payload) if isinstance(raw_payload, dict) else raw_payload
        if not isinstance(source_tasks, list):
            raise ValueError("Imported file must contain a tasks list")

        payload = self._load()
        existing_tasks = payload["tasks"] if merge else []
        existing_ids = {str(task.get("id")) for task in existing_tasks}
        imported: list[dict[str, Any]] = []
        for item in source_tasks:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_task_record(item, existing_ids=existing_ids)
            existing_ids.add(normalized["id"])
            imported.append(normalized)

        payload["tasks"] = existing_tasks + imported
        self._save(payload)
        return {
            "path": source,
            "imported": len(imported),
            "total": len(payload["tasks"]),
            "merge": merge,
        }

    def stats(self) -> dict[str, Any]:
        tasks = self._load()["tasks"]
        total = len(tasks)
        completed = sum(1 for task in tasks if task.get("completed"))
        active = total - completed
        overdue = sum(
            1
            for task in tasks
            if not task.get("completed")
            and task.get("due_date")
            and task["due_date"] < datetime.now().date().isoformat()
        )
        priority_counts = {
            level: sum(1 for task in tasks if task.get("priority") == level)
            for level in ["high", "medium", "low"]
        }
        return {
            "total": total,
            "completed": completed,
            "active": active,
            "overdue": overdue,
            "completion_rate": round((completed / total) * 100, 1) if total else 0.0,
            "priorities": priority_counts,
        }

    def storage_info(self) -> dict[str, Any]:
        self._ensure()
        size = self.path.stat().st_size if self.path.exists() else 0
        payload = self._load()
        return {
            "path": str(self.path),
            "exists": self.path.exists(),
            "size": size,
            "task_count": len(payload["tasks"]),
        }


if os.name == "posix" and os.uname().sysname == "Linux":
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

app = ForgeApp()
store = TodoStore()


@app.command
def list_tasks(status: str = "all", search: str = "", priority: str = "all") -> list[dict[str, Any]]:
    return store.list_tasks(status=status, search=search, priority=priority)


@app.command
def create_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return store.create_task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        tags=tags,
    )


@app.command
def update_task(
    task_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return store.update_task(
        task_id,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        tags=tags,
    )


@app.command
def set_task_completed(task_id: str, completed: bool) -> dict[str, Any]:
    return store.set_completed(task_id, completed)


@app.command
def delete_task(task_id: str) -> bool:
    return store.delete_task(task_id)


@app.command
def clear_completed_tasks() -> int:
    return store.clear_completed()


@app.command
def duplicate_task(task_id: str) -> dict[str, Any]:
    return store.duplicate_task(task_id)


@app.command
def get_task_stats() -> dict[str, Any]:
    return store.stats()


@app.command
def get_storage_info() -> dict[str, Any]:
    return store.storage_info()


@app.command
def export_tasks_payload() -> dict[str, Any]:
    return store.export_payload()


@app.command
def import_tasks_payload(tasks: list[dict[str, Any]], merge: bool = True) -> dict[str, Any]:
    return store.import_task_records(tasks, merge=merge)


@app.command
def seed_demo_tasks() -> dict[str, Any]:
    return store.seed_demo()


@app.command
def export_tasks_dialog() -> dict[str, Any] | None:
    path = app.dialog.save_file(
        title="Export Tasks",
        default_path="forge-tasks.json",
        filters=[{"name": "JSON Files", "extensions": ["json"]}],
    )
    if not path:
        return None
    return store.export_tasks(Path(path))


@app.command
def import_tasks_dialog(merge: bool = True) -> dict[str, Any] | None:
    path = app.dialog.open_file(
        title="Import Tasks",
        filters=[{"name": "JSON Files", "extensions": ["json"]}],
    )
    if not path:
        return None
    return store.import_tasks(Path(path), merge=merge)


if __name__ == "__main__":
    store._ensure()
    app.run(debug=True)
