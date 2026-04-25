"""
Todo Service — Business logic for todo management.

Demonstrates:
- Thread-safe in-memory storage
- Domain-driven design patterns
- Clean separation from handlers
"""

import threading
from datetime import datetime


class TodoService:
    _todos: list[dict] = []
    _counter: int = 0
    _lock = threading.Lock()

    @classmethod
    def add(cls, text: str) -> dict:
        with cls._lock:
            cls._counter += 1
            todo = {
                "id": cls._counter,
                "text": text.strip(),
                "done": False,
                "created_at": datetime.now().isoformat(),
            }
            cls._todos.append(todo)
        return {"success": True, "todo": dict(todo)}

    @classmethod
    def list_all(cls) -> list[dict]:
        with cls._lock:
            return [dict(t) for t in cls._todos]

    @classmethod
    def toggle(cls, id: int) -> dict:
        with cls._lock:
            for todo in cls._todos:
                if todo["id"] == id:
                    todo["done"] = not todo["done"]
                    todo["updated_at"] = datetime.now().isoformat()
                    return {"success": True, "todo": dict(todo)}
        return {"success": False, "error": f"Todo {id} not found"}

    @classmethod
    def delete(cls, id: int) -> dict:
        with cls._lock:
            original = len(cls._todos)
            cls._todos = [t for t in cls._todos if t["id"] != id]
            deleted = len(cls._todos) < original
        return {"success": deleted, "deleted_id": id if deleted else None}

    @classmethod
    def clear_completed(cls) -> dict:
        with cls._lock:
            before = len(cls._todos)
            cls._todos = [t for t in cls._todos if not t["done"]]
            removed = before - len(cls._todos)
        return {"success": True, "removed_count": removed}
