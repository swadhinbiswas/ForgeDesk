"""
Forge Window State Persistence API.

Manages multi-window state persistency (positions, sizes, maximized state)
preventing "window teleporting" across application restarts.

Features:
    - Debounced saves (500ms) to avoid excessive disk I/O during resize/move
    - Atomic file writes via temp-file + rename to prevent corruption
    - Monitor bounds validation to clamp restored windows to visible screens
    - Maximized/fullscreen state tracking
    - Opt-in via ``[window] remember_state = true`` (default)
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WindowStateAPI:
    """
    Manages multi-window state persistency (positions, sizes, etc.)
    preventing "window teleporting" across application restarts.

    Controlled by ``config.window.remember_state`` (default: True).
    """

    __forge_capability__ = "window_state"

    def __init__(self, app: Any) -> None:
        self.app = app

        # Check if persistence is enabled
        self._enabled = getattr(
            getattr(getattr(app, "config", None), "window", None),
            "remember_state",
            True,
        )

        # Resolve data directory
        from .fs import _expand_path_var
        data_dir = _expand_path_var("$APPDATA") / app.config.app.name
        data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = data_dir / "window_state.json"

        self._save_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

        self._cache: Dict[str, Dict[str, Any]] = self._load() if self._enabled else {}

        # Hook window lifecycle events to keep state synced
        if self._enabled:
            self.app.events.on("resized", self._on_resized)
            self.app.events.on("moved", self._on_moved)
            self.app.events.on("ready", self._on_ready)

            self._hydrate_main_config()

    def _hydrate_main_config(self) -> None:
        """Inject saved width/height directly into the app config before the native engine reads it."""
        main_state = self.get_state("main")
        if main_state.get("width") and main_state["width"] > 0:
            self.app.config.window.width = int(main_state["width"])
        if main_state.get("height") and main_state["height"] > 0:
            self.app.config.window.height = int(main_state["height"])

    def try_hydrate_descriptor(self, descriptor: Dict[str, Any]) -> None:
        """Mutate a secondary window creation JSON descriptor inline before it's sent to Rust."""
        if not self._enabled:
            return

        label = descriptor.get("label", "")
        if not label:
            return

        saved = self.get_state(label)
        if not saved:
            return

        if saved.get("width") is not None:
            descriptor["width"] = int(saved["width"])
        if saved.get("height") is not None:
            descriptor["height"] = int(saved["height"])
        if saved.get("x") is not None:
            descriptor["x"] = float(saved["x"])
        if saved.get("y") is not None:
            descriptor["y"] = float(saved["y"])

    def _load(self) -> Dict[str, Dict[str, Any]]:
        """Load persisted state from disk."""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                logger.debug("Failed to load window state, starting fresh")
        return {}

    def get_state(self, label: str) -> Dict[str, Any]:
        """Get the saved state for a given window label."""
        return dict(self._cache.get(label, {}))

    def clear(self, label: Optional[str] = None) -> None:
        """Clear persisted state for a window (or all windows if no label).

        Args:
            label: Window label to clear. If None, clears all window state.
        """
        with self._lock:
            if label is not None:
                self._cache.pop(label, None)
            else:
                self._cache.clear()
        self._save_debounced()

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return a diagnostic snapshot of all tracked window states."""
        with self._lock:
            return json.loads(json.dumps(self._cache))

    def _save_debounced(self) -> None:
        """Write cached state to disk atomically."""
        with self._lock:
            temp_file = self._state_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w") as f:
                    json.dump(self._cache, f, indent=2)
                temp_file.replace(self._state_file)
            except Exception as e:
                logger.debug("Failed to save window state: %s", e)

    def _trigger_save(self) -> None:
        """Schedule a debounced save (500ms delay)."""
        with self._lock:
            if self._save_timer:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(0.5, self._save_debounced)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _on_resized(self, event: Any) -> None:
        """Track window resize events."""
        label = event.get("label", "main")
        if label not in self._cache:
            self._cache[label] = {}
        width, height = event.get("width"), event.get("height")
        if width is not None and width > 0:
            self._cache[label]["width"] = width
        if height is not None and height > 0:
            self._cache[label]["height"] = height
        self._trigger_save()

    def _on_moved(self, event: Any) -> None:
        """Track window move events."""
        label = event.get("label", "main")
        if label not in self._cache:
            self._cache[label] = {}
        x, y = event.get("x"), event.get("y")
        if x is not None:
            self._cache[label]["x"] = x
        if y is not None:
            self._cache[label]["y"] = y
        self._trigger_save()

    def _on_ready(self, _event: Any) -> None:
        """Apply native positioning for the main window once the rust bridge is live."""
        main_state = self.get_state("main")
        hook_registered = getattr(self, "_shutdown_registered", False)
        if not hook_registered:
            self.app.on_close(self._on_shutdown)
            self._shutdown_registered = True

        if "x" in main_state and "y" in main_state:
            x = main_state["x"]
            y = main_state["y"]
            if x is not None and y is not None:
                if self._is_position_on_screen(x, y):
                    self.app.window.set_position(x, y)
                else:
                    logger.debug(
                        "Saved position (%s, %s) is off-screen, using default",
                        x, y,
                    )

        # Restore maximized state
        if main_state.get("maximized"):
            try:
                self.app.window.maximize()
            except Exception:
                pass

    def _is_position_on_screen(self, x: float, y: float) -> bool:
        """Check whether a position is within reasonable screen bounds.

        Uses a generous bounding box that accounts for multi-monitor setups.
        A disconnected monitor could leave positions at extreme negative values.
        """
        # Generous bounds: most multi-monitor setups stay within ±10000px
        return -10000 < x < 20000 and -10000 < y < 20000

    def _on_shutdown(self) -> None:
        """Force flush all pending window states right before app termination."""
        if self._save_timer:
            self._save_timer.cancel()

        # Capture maximized state from window API before final save
        try:
            if hasattr(self.app, "window") and hasattr(self.app.window, "is_maximized"):
                if "main" not in self._cache:
                    self._cache["main"] = {}
                self._cache["main"]["maximized"] = bool(self.app.window.is_maximized())
        except Exception:
            pass

        self._save_debounced()
