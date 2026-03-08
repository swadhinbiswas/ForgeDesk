import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional

class WindowStateAPI:
    """
    Manages multi-window state persistency (positions, sizes, etc.)
    preventing "window teleporting" across application restarts.
    """
    def __init__(self, app):
        self.app = app
        # Ensure FS API is initialized before accessing paths
        from .fs import _expand_path_var
        data_dir = _expand_path_var("$APPDATA") / app.config.app.name
        data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = data_dir / "window_state.json" 
        
        self._save_timer = None
        self._lock = threading.Lock()
        
        self._cache = self._load()
        
        # Hook window lifecycle events to keep state synced without JS
        self.app.events.on("resized", self._on_resized)
        self.app.events.on("moved", self._on_moved)

    def _load(self) -> Dict[str, Any]:
        if self._state_file.exists():
            try:
                with open(self._state_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def get_state(self, label: str) -> Dict[str, Any]:
        """Get the saved state for a given window label."""
        return self._cache.get(label, {})

    def _save_debounced(self):
        with self._lock:
            # Atomic write to avoid corruption
            temp_file = self._state_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w") as f:
                    json.dump(self._cache, f)
                temp_file.replace(self._state_file)
            except Exception as e:
                pass # Silent fail if permissions block saving state

    def _trigger_save(self):
        with self._lock:
            if self._save_timer:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(0.3, self._save_debounced)
            self._save_timer.start()

    def _on_resized(self, event):
        label = event.get("label", "main")
        if label not in self._cache:
            self._cache[label] = {}
        self._cache[label]["width"] = event.get("width")
        self._cache[label]["height"] = event.get("height")
        self._trigger_save()
        
    def _on_moved(self, event):
        label = event.get("label", "main")
        if label not in self._cache:
            self._cache[label] = {}
        self._cache[label]["x"] = event.get("x")
        self._cache[label]["y"] = event.get("y")
        self._trigger_save()
