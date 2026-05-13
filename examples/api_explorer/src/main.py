"""
Forge API Explorer - Demo Application

An interactive application showcasing all Forge Framework APIs.
Use this to test and understand each API's capabilities.
"""

import threading
import time
from datetime import datetime
from pathlib import Path

from forge import ForgeApp

app = ForgeApp()

# Demo directory for file operations
DEMO_DIR = Path.cwd() / "api_demo"
DEMO_DIR.mkdir(exist_ok=True)


# =============================================================================
# System API Demos
# =============================================================================


@app.command
def get_system_info() -> dict:
    """Get comprehensive system information."""
    import platform

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.machine(),
        "processor": platform.processor(),
        "node": platform.node(),
    }


@app.command
def get_app_version() -> str:
    """Get the application version."""
    return "1.0.0"


@app.command
def get_current_timestamp() -> dict:
    """Get current timestamp in various formats."""
    now = datetime.now()
    return {
        "iso": now.isoformat(),
        "unix": int(now.timestamp()),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": now.strftime("%A"),
    }


# =============================================================================
# Clipboard API Demos
# =============================================================================


@app.command
def clipboard_read() -> str:
    """Read text from clipboard."""
    return app.clipboard.read()


@app.command
def clipboard_write(text: str) -> bool:
    """Write text to clipboard."""
    try:
        app.clipboard.write(text)
        return True
    except Exception:
        return False


# =============================================================================
# File System API Demos
# =============================================================================


@app.command
def fs_list(path: str = ".") -> list[dict]:
    """List directory contents."""
    try:
        items = app.fs.list_dir(path, include_hidden=True)
        return items
    except Exception as e:
        return [{"error": str(e)}]


@app.command
def fs_read(path: str) -> str:
    """Read file contents."""
    return app.fs.read(path)


@app.command
def fs_write(path: str, content: str) -> bool:
    """Write content to file."""
    try:
        app.fs.write(path, content)
        return True
    except Exception:
        return False


@app.command
def fs_exists(path: str) -> bool:
    """Check if path exists."""
    return app.fs.exists(path)


@app.command
def fs_delete(path: str) -> bool:
    """Delete a file."""
    try:
        app.fs.delete(path)
        return True
    except Exception:
        return False


@app.command
def fs_mkdir(path: str) -> bool:
    """Create a directory."""
    try:
        app.fs.mkdir(path)
        return True
    except Exception:
        return False


@app.command
def fs_get_base_path() -> str:
    """Get the base path for file operations."""
    return str(app.fs.get_base_path())


# =============================================================================
# Dialog API Demos
# =============================================================================


@app.command
def dialog_open_file() -> dict | None:
    """Show open file dialog."""
    try:
        path = app.dialog.open_file(
            title="Open File",
            filters=[
                {"name": "All Files", "extensions": ["*"]},
                {"name": "Text Files", "extensions": ["txt"]},
                {"name": "JSON Files", "extensions": ["json"]},
            ],
        )
        if path:
            content = Path(path).read_text(encoding="utf-8")
            return {"path": path, "content": content}
        return None
    except Exception as e:
        return {"error": str(e)}


@app.command
def dialog_save_file(content: str) -> str | None:
    """Show save file dialog."""
    try:
        path = app.dialog.save_file(
            title="Save File",
            default_path="demo.txt",
            filters=[{"name": "Text Files", "extensions": ["txt"]}],
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            return path
        return None
    except Exception:
        return None


@app.command
def dialog_message(title: str, body: str, type: str = "info") -> None:
    """Show a message dialog."""
    app.dialog.message(title, body, type)


# =============================================================================
# Event System Demos
# =============================================================================


@app.command
def start_counter() -> str:
    """Start a counter that emits events."""

    def run_counter():
        for i in range(1, 101):
            app.emit("counter_update", {"count": i, "percent": i})
            time.sleep(0.05)
        app.emit("counter_complete", {"message": "Counter finished!"})

    threading.Thread(target=run_counter, daemon=True).start()
    return "Counter started"


@app.command
def stop_counter() -> str:
    """Stop the counter."""
    app.emit("counter_stop", {"message": "Counter stopped by user"})
    return "Counter stopped"


@app.command
def emit_custom_event(event_name: str, data: dict) -> bool:
    """Emit a custom event."""
    try:
        app.emit(event_name, data)
        return True
    except Exception:
        return False


# =============================================================================
# Utility Demos
# =============================================================================


@app.command
def echo(data: dict) -> dict:
    """Echo back any data sent."""
    data["_echoed_at"] = datetime.now().isoformat()
    return data


@app.command
def process_text(text: str, operation: str) -> dict:
    """Process text with various operations."""
    operations = {
        "uppercase": lambda t: t.upper(),
        "lowercase": lambda t: t.lower(),
        "reverse": lambda t: t[::-1],
        "word_count": lambda t: len(t.split()),
        "char_count": lambda t: len(t),
        "line_count": lambda t: len(t.split("\n")),
        "trim": lambda t: t.strip(),
    }

    if operation not in operations:
        return {"error": f"Unknown operation: {operation}"}

    result = operations[operation](text)
    return {
        "original": text,
        "operation": operation,
        "result": result,
    }


@app.command
def get_api_list() -> list[dict]:
    """Get list of all available APIs."""
    return [
        {
            "category": "System",
            "apis": ["get_system_info", "get_app_version", "get_current_timestamp"],
        },
        {"category": "Clipboard", "apis": ["clipboard_read", "clipboard_write"]},
        {
            "category": "File System",
            "apis": ["fs_list", "fs_read", "fs_write", "fs_exists", "fs_delete", "fs_mkdir"],
        },
        {"category": "Dialog", "apis": ["dialog_open_file", "dialog_save_file", "dialog_message"]},
        {"category": "Events", "apis": ["start_counter", "stop_counter", "emit_custom_event"]},
        {"category": "Utilities", "apis": ["echo", "process_text", "get_api_list"]},
    ]


if __name__ == "__main__":
    app.run(debug=True)
