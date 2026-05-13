"""
Forge Notes - Demo Application

A note-taking app demonstrating Forge's file system and dialog APIs.

Features:
- List notes from a directory
- Create, read, update, delete notes
- Native file dialogs for opening/saving
- Auto-save functionality
- Search notes
"""

from datetime import datetime
from pathlib import Path

from forge import ForgeApp

app = ForgeApp()

# Notes directory (relative to app)
NOTES_DIR = Path.cwd() / "notes"


def _get_notes_dir() -> Path:
    """Get or create the notes directory."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return NOTES_DIR


def _format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


@app.command
def list_notes() -> list[dict]:
    """
    List all notes in the notes directory.

    Returns:
        List of note info dictionaries with name, size, and modified time.
    """
    notes_dir = _get_notes_dir()
    notes = []

    for file in sorted(notes_dir.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True):
        stat = file.stat()
        notes.append(
            {
                "name": file.stem,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "modified_formatted": _format_timestamp(stat.st_mtime),
            }
        )

    return notes


@app.command
def read_note(name: str) -> str:
    """
    Read a note's contents.

    Args:
        name: Note name (without .txt extension).

    Returns:
        The note contents.

    Raises:
        FileNotFoundError: If the note doesn't exist.
    """
    notes_dir = _get_notes_dir()
    note_path = notes_dir / f"{name}.txt"

    if not note_path.exists():
        raise FileNotFoundError(f"Note not found: {name}")

    return note_path.read_text(encoding="utf-8")


@app.command
def save_note(name: str, content: str) -> dict:
    """
    Save a note.

    Args:
        name: Note name (without .txt extension).
        content: Note contents.

    Returns:
        Dictionary with success status and note info.
    """
    notes_dir = _get_notes_dir()
    note_path = notes_dir / f"{name}.txt"

    note_path.write_text(content, encoding="utf-8")

    stat = note_path.stat()
    return {
        "success": True,
        "name": name,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "modified_formatted": _format_timestamp(stat.st_mtime),
    }


@app.command
def delete_note(name: str) -> bool:
    """
    Delete a note.

    Args:
        name: Note name (without .txt extension).

    Returns:
        True if successful.

    Raises:
        FileNotFoundError: If the note doesn't exist.
    """
    notes_dir = _get_notes_dir()
    note_path = notes_dir / f"{name}.txt"

    if not note_path.exists():
        raise FileNotFoundError(f"Note not found: {name}")

    note_path.unlink()
    return True


@app.command
def search_notes(query: str) -> list[dict]:
    """
    Search notes by content.

    Args:
        query: Search query string.

    Returns:
        List of matching notes with preview.
    """
    notes_dir = _get_notes_dir()
    results = []
    query_lower = query.lower()

    for file in notes_dir.glob("*.txt"):
        try:
            content = file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                # Find the matching line
                for line in content.split("\n"):
                    if query_lower in line.lower():
                        stat = file.stat()
                        results.append(
                            {
                                "name": file.stem,
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                                "modified_formatted": _format_timestamp(stat.st_mtime),
                                "preview": line.strip()[:100],
                            }
                        )
                        break
        except UnicodeDecodeError, PermissionError:
            continue

    return results


@app.command
def open_note_dialog() -> dict | None:
    """
    Show a file open dialog and read the selected file.

    Returns:
        Dictionary with path and content, or None if cancelled.
    """
    dialog = app.dialog

    path = dialog.open_file(
        title="Open Note",
        filters=[{"name": "Text Files", "extensions": ["txt"]}],
    )

    if path:
        content = Path(path).read_text(encoding="utf-8")
        return {
            "path": path,
            "content": content,
            "name": Path(path).stem,
        }

    return None


@app.command
def save_note_dialog(content: str, default_name: str = "note") -> str | None:
    """
    Show a save dialog and write to the selected file.

    Args:
        content: Content to save.
        default_name: Default filename.

    Returns:
        The saved file path, or None if cancelled.
    """
    dialog = app.dialog

    path = dialog.save_file(
        title="Save Note As",
        default_path=f"{default_name}.txt",
        filters=[{"name": "Text Files", "extensions": ["txt"]}],
    )

    if path:
        Path(path).write_text(content, encoding="utf-8")
        return path

    return None


@app.command
def get_note_stats() -> dict:
    """
    Get statistics about notes.

    Returns:
        Dictionary with note count, total size, etc.
    """
    notes_dir = _get_notes_dir()
    files = list(notes_dir.glob("*.txt"))

    total_size = sum(f.stat().st_size for f in files)

    return {
        "count": len(files),
        "total_size": total_size,
        "total_size_formatted": f"{total_size / 1024:.1f} KB"
        if total_size < 1024 * 1024
        else f"{total_size / (1024 * 1024):.1f} MB",
    }


@app.command
def rename_note(old_name: str, new_name: str) -> bool:
    """
    Rename a note.

    Args:
        old_name: Current note name.
        new_name: New note name.

    Returns:
        True if successful.

    Raises:
        FileNotFoundError: If the note doesn't exist.
        FileExistsError: If new name already exists.
    """
    notes_dir = _get_notes_dir()
    old_path = notes_dir / f"{old_name}.txt"
    new_path = notes_dir / f"{new_name}.txt"

    if not old_path.exists():
        raise FileNotFoundError(f"Note not found: {old_name}")

    if new_path.exists():
        raise FileExistsError(f"Note already exists: {new_name}")

    old_path.rename(new_path)
    return True


if __name__ == "__main__":
    # Create notes directory on startup
    _get_notes_dir()
    app.run(debug=True)
