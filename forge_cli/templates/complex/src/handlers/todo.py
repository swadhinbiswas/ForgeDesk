"""
Todo IPC Handlers — Bridge between frontend and business logic.
"""

from forge import ForgeApp
from services.todo import TodoService


def register_todo_commands(app: ForgeApp):
    """Register all todo-related IPC commands."""

    @app.command
    def todo_add(text: str) -> dict:
        """Add a new todo item."""
        return TodoService.add(text)

    @app.command
    def todo_list() -> list[dict]:
        """Get all todo items."""
        return TodoService.list_all()

    @app.command
    def todo_toggle(id: int) -> dict:
        """Toggle a todo's completion status."""
        return TodoService.toggle(id)

    @app.command
    def todo_delete(id: int) -> dict:
        """Delete a todo item."""
        return TodoService.delete(id)

    @app.command
    def todo_clear_completed() -> dict:
        """Remove all completed todos."""
        return TodoService.clear_completed()
