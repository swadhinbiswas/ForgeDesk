import pytest
from unittest.mock import MagicMock
from forge.api.drag_drop import DragDropAPI

class DummyEvents:
    def __init__(self):
        self.handlers = {}
        self.emitted = []

    def on(self, event_name):
        def decorator(func):
            self.handlers[event_name] = func
            return func
        return decorator

    def emit(self, event_name, data):
        self.emitted.append((event_name, data))

class DummyApp:
    def __init__(self):
        self.events = DummyEvents()

def test_drag_drop_api():
    app = DummyApp()
    api = DragDropAPI(app)

    # Simulate file drop
    app.events.handlers["file_drop"]({"paths": ["/tmp/test.txt"], "window": "main"})
    assert ("drag_drop:main", {"paths": ["/tmp/test.txt"]}) in app.events.emitted
    assert ("drag_drop", {"paths": ["/tmp/test.txt"], "window": "main"}) in app.events.emitted

    # Simulate hover
    app.events.handlers["file_drop_hover"]({"paths": ["/tmp/test2.txt"], "window": "main"})
    assert ("drag_hover:main", {"paths": ["/tmp/test2.txt"]}) in app.events.emitted
    assert ("drag_hover", {"paths": ["/tmp/test2.txt"], "window": "main"}) in app.events.emitted

    # Simulate cancel
    app.events.handlers["file_drop_cancelled"]({"window": "main"})
    assert ("drag_cancelled:main", {}) in app.events.emitted
    assert ("drag_cancelled", {"window": "main"}) in app.events.emitted
