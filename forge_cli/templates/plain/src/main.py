"""
{{PROJECT_NAME}} - Todo List Backend

A production-ready todo list application demonstrating:
- CRUD operations via IPC
- State persistence in memory
- Thread-safe operations

Quick start:
    ./forge dev        # Start development server
    ./forge build      # Build production binary
"""

import threading
from datetime import datetime

from forge import ForgeApp

app = ForgeApp()

# Thread-safe in-memory storage
_todos: list[dict] = []
_counter = 0
_lock = threading.Lock()


@app.command
def todo_add(text: str) -> dict:
    """Add a new todo item."""
    global _counter
    with _lock:
        _counter += 1
        todo = {
            "id": _counter,
            "text": text.strip(),
            "done": False,
            "created_at": datetime.now().isoformat(),
        }
        _todos.append(todo)
    return {"success": True, "todo": todo}


@app.command
def todo_list() -> list[dict]:
    """Get all todo items."""
    with _lock:
        # Return copies to prevent mutation
        return [dict(t) for t in _todos]


@app.command
def todo_toggle(id: int) -> dict:
    """Toggle the completion status of a todo."""
    with _lock:
        for todo in _todos:
            if todo["id"] == id:
                todo["done"] = not todo["done"]
                todo["updated_at"] = datetime.now().isoformat()
                return {"success": True, "todo": dict(todo)}
    return {"success": False, "error": f"Todo {id} not found"}


@app.command
def todo_delete(id: int) -> dict:
    """Delete a todo item."""
    global _todos
    with _lock:
        original_len = len(_todos)
        _todos = [t for t in _todos if t["id"] != id]
        deleted = len(_todos) < original_len
    return {"success": deleted, "deleted_id": id if deleted else None}


@app.command
def todo_clear_completed() -> dict:
    """Remove all completed todos."""
    global _todos
    with _lock:
        before = len(_todos)
        _todos = [t for t in _todos if not t["done"]]
        removed = before - len(_todos)
    return {"success": True, "removed_count": removed}


@app.command
def get_system_info() -> dict:
    """Get system information."""
    import platform

    return {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "platform": platform.machine(),
    }


if __name__ == "__main__":
    app.run(debug=True)
