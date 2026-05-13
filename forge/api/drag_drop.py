from typing import Any


class DragDropAPI:
    """
    API for drag & drop operations.
    Listens to window events and dispatches clean path lists.
    """

    __forge_capability__ = "drag_drop"

    def __init__(self, app: Any) -> None:
        self.app = app
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        @self.app.events.on("file_drop")
        def _on_file_drop(event_data: dict[str, Any]) -> None:
            paths = event_data.get("paths", [])
            window_label = event_data.get("window", "main")

            # Dispatch to Python
            self.app.events.emit(f"drag_drop:{window_label}", {"paths": paths})
            self.app.events.emit("drag_drop", {"paths": paths, "window": window_label})

        @self.app.events.on("file_drop_hover")
        def _on_file_drop_hover(event_data: dict[str, Any]) -> None:
            paths = event_data.get("paths", [])
            window_label = event_data.get("window", "main")

            self.app.events.emit(f"drag_hover:{window_label}", {"paths": paths})
            self.app.events.emit("drag_hover", {"paths": paths, "window": window_label})

        @self.app.events.on("file_drop_cancelled")
        def _on_file_drop_cancelled(event_data: dict[str, Any]) -> None:
            window_label = event_data.get("window", "main")

            self.app.events.emit(f"drag_cancelled:{window_label}", {})
            self.app.events.emit("drag_cancelled", {"window": window_label})
