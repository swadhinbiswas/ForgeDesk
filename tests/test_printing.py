import pytest
from unittest.mock import MagicMock
from forge.app import ForgeApp
from forge.api.printing import PrintingAPI

class Event:
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload

class DummyWindow:
    def __init__(self):
        self.printed = False

    def print(self, label):
        self.printed = True
        self.label = label

class DummyApp:
    def __init__(self):
        self.events = MagicMock()
        self.events.on = self.mock_on
        self.handlers = {}
        self.window = DummyWindow()

    def mock_on(self, event_name):
        def decorator(handler):
            self.handlers[event_name] = handler
            return handler
        return decorator

    def trigger(self, event_name, event):
        if event_name in self.handlers:
            self.handlers[event_name](event)

def test_printing_api_init():
    app = DummyApp()
    api = PrintingAPI(app)
    assert app.handlers["ipc:print"] is not None

def test_printing_api_trigger():
    app = DummyApp()
    api = PrintingAPI(app)
    
    app.trigger("ipc:print", Event("ipc:print", {}))
    
    assert app.window.printed is True
    assert app.window.label == "main"

