"""
forge_chat - Python Backend (React Template)
"""

import time

from forge import ForgeApp

# Create the app instance
app = ForgeApp()


@app.command
def open_settings() -> bool:
    """Open the settings secondary window if it doesn't exist."""
    windows = getattr(app, "windows", None)
    if not windows:
        return False

    try:
        # Check if settings window exists
        win = windows.get_window("settings")
        if win:
            win.focus()
            return True

        # Create a new secondary window that loads the settings route
        windows.create_window(
            label="settings",
            title="Settings",
            url="forge://app/index.html#/settings",
            width=500,
            height=600,
            resizable=False,
        )
        return True
    except Exception:
        return False


@app.command
def simulate_file_download(filename: str) -> str:
    """Trigger a background task simulating a long-running download."""

    def _download_task(cancel_event, app_context):
        # Create a streaming channel
        channels = getattr(app_context, "channels", None)
        if not channels:
            return "Channels unavailable"

        # create a channel targeted at whoever is listening?
        # Actually it targets "main" by default
        target = "main"
        channel_id = channels.create(f"download-{filename}", target_label=target)

        # Notify JS what our channel ID is
        app_context.emit("download:started", {"filename": filename, "channel_id": channel_id})

        # Stream progress
        total = 100
        for i in range(1, total + 1):
            if cancel_event.is_set():
                channels.close(channel_id)
                return "cancelled"

            time.sleep(0.05)
            channels.send(channel_id, {"percent": i, "filename": filename})

        channels.close(channel_id)
        return "completed"

    tasks = getattr(app, "tasks", None)
    if tasks:
        # Returns the task string ID automatically
        return tasks.start(f"dl-{filename}", _download_task)

    return "Error: tasks not enabled"


# Run the application
if __name__ == "__main__":
    app.run(debug=True)
