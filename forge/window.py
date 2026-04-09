"""
Window Management APIs for Forge Framework.

Splits the WindowAPI and WindowManagerAPI from the main app.py
to organize window lifecycle and state synchronization.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import ForgeApp


class WindowAPI:
    """High-level Python control surface for the native application window."""

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        initial_title = app.config.window.title or app.config.app.name
        self._state: Dict[str, Any] = {
            "title": initial_title,
            "width": int(app.config.window.width),
            "height": int(app.config.window.height),
            "fullscreen": bool(app.config.window.fullscreen),
            "always_on_top": bool(app.config.window.always_on_top),
            "visible": True,
            "focused": False,
            "minimized": False,
            "maximized": False,
            "x": None,
            "y": None,
            "closed": False,
        }

    @property
    def is_ready(self) -> bool:
        """Return whether the native runtime has attached a live window proxy."""
        return self._app._proxy is not None

    def _require_proxy(self) -> Any:
        if self._app._proxy is None:
            raise RuntimeError("The native window is not ready yet.")
        return self._app._proxy

    def _update_state(self, **updates: Any) -> None:
        self._state.update(updates)

    def _apply_native_event(self, event: str, payload: Dict[str, Any] | None) -> None:
        payload = payload or {}
        if event == "ready":
            self._update_state(visible=True, closed=False)
        elif event == "resized":
            width = payload.get("width")
            height = payload.get("height")
            if width is not None and height is not None:
                self._update_state(width=int(width), height=int(height))
        elif event == "moved":
            self._update_state(x=payload.get("x"), y=payload.get("y"))
        elif event == "focused":
            self._update_state(focused=bool(payload.get("focused")))
        elif event == "close_requested":
            self._update_state(visible=False)
        elif event == "destroyed":
            self._update_state(closed=True, visible=False)

    def state(self) -> Dict[str, Any]:
        """Return the latest known window state snapshot."""
        return dict(self._state)

    def position(self) -> Dict[str, Any]:
        """Return the latest known outer window position."""
        return {"x": self._state.get("x"), "y": self._state.get("y")}

    def is_visible(self) -> bool:
        """Return whether the window is currently visible."""
        return bool(self._state.get("visible"))

    def is_focused(self) -> bool:
        """Return whether the window is currently focused."""
        return bool(self._state.get("focused"))

    def is_minimized(self) -> bool:
        """Return whether the window is currently minimized."""
        return bool(self._state.get("minimized"))

    def is_maximized(self) -> bool:
        """Return whether the window is currently maximized."""
        return bool(self._state.get("maximized"))

    def evaluate_script(self, script: str) -> None:
        """Evaluate JavaScript in the live main webview."""
        self._require_proxy().evaluate_script("main", script)

    def set_title(self, title: str) -> None:
        """Update the window title now, or the initial title before startup."""
        self._app.config.window.title = title
        self._update_state(title=title)
        if self._app._proxy is not None:
            self._app._proxy.set_title(title)

    def set_position(self, x: int | float, y: int | float) -> None:
        """Move the outer window position."""
        x_val = int(x)
        y_val = int(y)
        self._update_state(x=x_val, y=y_val)
        if self._app._proxy is not None:
            self._app._proxy.set_position(float(x_val), float(y_val))

    def set_size(self, width: int | float, height: int | float) -> None:
        """Update the window size now, or the initial size before startup."""
        width_val = int(width)
        height_val = int(height)
        if width_val <= 0 or height_val <= 0:
            raise ValueError("Window width and height must be positive.")

        self._app.config.window.width = width_val
        self._app.config.window.height = height_val
        self._update_state(width=width_val, height=height_val)

        if self._app._proxy is not None:
            self._app._proxy.set_size(float(width_val), float(height_val))

    def set_fullscreen(self, enabled: bool) -> None:
        """Enable or disable fullscreen mode."""
        self._app.config.window.fullscreen = bool(enabled)
        self._update_state(fullscreen=bool(enabled))
        if self._app._proxy is not None:
            self._app._proxy.set_fullscreen(bool(enabled))

    def set_always_on_top(self, enabled: bool) -> None:
        """Enable or disable the always-on-top window state."""
        self._app.config.window.always_on_top = bool(enabled)
        self._update_state(always_on_top=bool(enabled))
        if self._app._proxy is not None:
            self._app._proxy.set_always_on_top(bool(enabled))

    def show(self) -> None:
        """Show the native window."""
        self._update_state(visible=True)
        self._require_proxy().set_visible(True)

    def set_vibrancy(self, effect: str | None) -> None:
        """
        Dynamically update the native window's vibrancy material effect.
        Supported materials include 'mica', 'acrylic', 'blur' (Windows),
        and 'sidebar', 'popover', 'hud_window', etc. (macOS).
        Set to None to remove vibrancy.
        """
        self._update_state(vibrancy=effect)
        self._require_proxy().set_vibrancy(label="main", vibrancy=effect)

    def hide(self) -> None:
        """Hide the native window."""
        self._update_state(visible=False)
        self._require_proxy().set_visible(False)

    def focus(self) -> None:
        """Bring the native window to the front."""
        self._update_state(focused=True)
        self._require_proxy().focus()

    def minimize(self) -> None:
        """Minimize the native window."""
        self._update_state(minimized=True, maximized=False)
        self._require_proxy().set_minimized(True)

    def unminimize(self) -> None:
        """Restore the window from a minimized state."""
        self._update_state(minimized=False)
        self._require_proxy().set_minimized(False)

    def maximize(self) -> None:
        """Maximize the native window."""
        self._update_state(maximized=True, minimized=False)
        self._require_proxy().set_maximized(True)

    def unmaximize(self) -> None:
        """Restore the window from a maximized state."""
        self._update_state(maximized=False)
        self._require_proxy().set_maximized(False)

    def close(self) -> None:
        """Request that the native window close."""
        self._update_state(closed=True, visible=False)
        self._require_proxy().close()


class WindowManagerAPI:
    """Managed multiwindow registry and orchestration surface."""

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        self._current_label = "main"
        self._windows: Dict[str, Dict[str, Any]] = {}
        self._register_main_window()

    def _register_main_window(self) -> None:
        config = self._app.config.window
        self._windows["main"] = {
            "label": "main",
            "title": config.title or self._app.config.app.name,
            "url": self._resolve_url(),
            "route": "/",
            "width": int(config.width),
            "height": int(config.height),
            "fullscreen": bool(config.fullscreen),
            "resizable": bool(config.resizable),
            "decorations": bool(config.decorations),
            "transparent": bool(config.transparent),
            "always_on_top": bool(config.always_on_top),
            "visible": True,
            "focused": False,
            "closed": False,
            "backend": "native",
            "parent": None,
            "created_at": time.time(),
        }

    def _resolve_url(self, route: str = "/", explicit_url: str | None = None) -> str:
        if explicit_url:
            return explicit_url
        clean_route = route if route.startswith("/") else f"/{route}"
        if self._app._dev_server_url:
            return f"{self._app._dev_server_url.rstrip('/')}{clean_route}"
        if clean_route == "/":
            return "forge://app/index.html"
        return f"forge://app{clean_route}"

    def _emit_frontend_open(self, descriptor: Dict[str, Any]) -> None:
        if self._app._proxy is None:
            return
        payload = json.dumps(descriptor)
        self._app._proxy.evaluate_script(f"window.__forge__.__openManagedWindow({payload})")

    def _emit_frontend_close(self, label: str) -> None:
        if self._app._proxy is None:
            return
        self._app._proxy.evaluate_script(
            f"window.__forge__.__closeManagedWindow({json.dumps(label)})"
        )

    def _supports_native_multiwindow(self) -> bool:
        return self._app._proxy is not None and hasattr(self._app._proxy, "create_window")

    def _apply_native_event(self, event: str, payload: Dict[str, Any] | None) -> str:
        payload = payload or {}
        label = str(payload.get("label") or "main").strip().lower() or "main"

        if label == "main":
            self.sync_main_window()
            return label

        descriptor = self._windows.setdefault(
            label,
            {
                "label": label,
                "title": payload.get("title") or label.replace("-", " ").title(),
                "url": payload.get("url") or self._resolve_url(),
                "route": payload.get("route") or "/",
                "width": int(payload.get("width") or self._app.config.window.width),
                "height": int(payload.get("height") or self._app.config.window.height),
                "fullscreen": bool(payload.get("fullscreen", False)),
                "resizable": bool(payload.get("resizable", True)),
                "decorations": bool(payload.get("decorations", True)),
                "transparent": bool(payload.get("transparent", False)),
                "always_on_top": bool(payload.get("always_on_top", False)),
                "visible": bool(payload.get("visible", True)),
                "focused": bool(payload.get("focused", False)),
                "closed": False,
                "backend": "native",
                "parent": payload.get("parent") or "main",
                "created_at": time.time(),
            },
        )

        descriptor["backend"] = payload.get("backend") or descriptor.get("backend") or "native"
        if "title" in payload:
            descriptor["title"] = payload.get("title")
        if "url" in payload:
            descriptor["url"] = payload.get("url")
        if "route" in payload:
            descriptor["route"] = payload.get("route")
        if "width" in payload and payload.get("width") is not None:
            descriptor["width"] = int(payload["width"])
        if "height" in payload and payload.get("height") is not None:
            descriptor["height"] = int(payload["height"])
        if "fullscreen" in payload:
            descriptor["fullscreen"] = bool(payload.get("fullscreen"))
        if "resizable" in payload:
            descriptor["resizable"] = bool(payload.get("resizable"))
        if "decorations" in payload:
            descriptor["decorations"] = bool(payload.get("decorations"))
        if "transparent" in payload:
            descriptor["transparent"] = bool(payload.get("transparent"))
        if "always_on_top" in payload:
            descriptor["always_on_top"] = bool(payload.get("always_on_top"))
        if "visible" in payload:
            descriptor["visible"] = bool(payload.get("visible"))
        if "focused" in payload:
            descriptor["focused"] = bool(payload.get("focused"))

        if event == "close_requested":
            descriptor["visible"] = False
            descriptor["focused"] = False
        elif event == "destroyed":
            descriptor["visible"] = False
            descriptor["focused"] = False
            descriptor["closed"] = True
        elif event == "created":
            descriptor["closed"] = False
            descriptor["visible"] = bool(payload.get("visible", True))
            descriptor["focused"] = bool(payload.get("focused", False))
        elif event == "focused":
            descriptor["focused"] = bool(payload.get("focused"))
        elif event == "navigated" and payload.get("url"):
            descriptor["url"] = payload["url"]

        self._windows[label] = descriptor
        return label

    def sync_main_window(self) -> None:
        state = self._app.window.state()
        main = self._windows.setdefault("main", {})
        main.update(
            {
                "label": "main",
                "title": state.get("title"),
                "url": self._resolve_url(),
                "route": "/",
                "width": state.get("width"),
                "height": state.get("height"),
                "fullscreen": state.get("fullscreen"),
                "resizable": bool(self._app.config.window.resizable),
                "decorations": bool(self._app.config.window.decorations),
                "transparent": bool(self._app.config.window.transparent),
                "always_on_top": state.get("always_on_top"),
                "visible": state.get("visible"),
                "focused": state.get("focused"),
                "closed": state.get("closed"),
                "backend": "native",
                "parent": None,
            }
        )

    def current(self) -> Dict[str, Any]:
        self.sync_main_window()
        return dict(self._windows[self._current_label])

    def evaluate_script(self, label: str, script: str) -> None:
        """Evaluate JavaScript in a specific live webview by label."""
        if self._app._proxy is None:
            raise RuntimeError("The native window is not ready yet.")
        self._app._proxy.evaluate_script(label, script)

    def broadcast(self, script: str) -> None:
        """Evaluate JavaScript across all managed active windows."""
        if self._app._proxy is None:
            return
        for window_label in self._windows.keys():
            self._app._proxy.evaluate_script(window_label, script)

    def list(self) -> List[Dict[str, Any]]:
        self.sync_main_window()
        return [dict(item) for item in self._windows.values()]

    def get(self, label: str) -> Dict[str, Any]:
        self.sync_main_window()
        if label not in self._windows:
            raise KeyError(f"Unknown window label: {label}")
        return dict(self._windows[label])

    def create(
        self,
        label: str,
        url: str | None = None,
        route: str = "/",
        title: str | None = None,
        width: int | float | None = None,
        height: int | float | None = None,
        fullscreen: bool = False,
        resizable: bool = True,
        decorations: bool = True,
        transparent: bool = False,
        always_on_top: bool = False,
        visible: bool = True,
        focus: bool = True,
        parent: str | None = "main",
    ) -> Dict[str, Any]:
        normalized_label = str(label).strip().lower()
        if not normalized_label:
            raise ValueError("Window label is required")
        if normalized_label in self._windows:
            raise ValueError(f"Window already exists: {normalized_label}")

        descriptor = {
            "label": normalized_label,
            "title": title or normalized_label.replace("-", " ").title(),
            "url": self._resolve_url(route=route, explicit_url=url),
            "route": route if route.startswith("/") else f"/{route}",
            "width": int(width or self._app.config.window.width),
            "height": int(height or self._app.config.window.height),
            "fullscreen": bool(fullscreen),
            "resizable": bool(resizable),
            "decorations": bool(decorations),
            "transparent": bool(transparent),
            "always_on_top": bool(always_on_top),
            "visible": bool(visible),
            "focused": bool(focus),
            "closed": False,
            "backend": "native" if self._supports_native_multiwindow() else "managed-popup",
            "parent": parent,
            "created_at": time.time(),
        }

        # Inject persisted window state geometry if window_state capability is active
        window_state = getattr(self._app, "window_state", None)
        if window_state is not None:
            window_state.try_hydrate_descriptor(descriptor)
            
        self._windows[normalized_label] = descriptor
        if descriptor["backend"] == "native":
            try:
                self._app._proxy.create_window(json.dumps(descriptor))
            except Exception:
                descriptor["backend"] = "managed-popup"
                self._emit_frontend_open(descriptor)
        else:
            self._emit_frontend_open(descriptor)
        self._app.emit("window:created", descriptor)
        self._app._log_runtime_event("window_created", label=normalized_label, url=descriptor["url"])
        return dict(descriptor)

    def close(self, label: str) -> bool:
        normalized_label = str(label).strip().lower()
        if normalized_label == "main":
            self._app.window.close()
            self.sync_main_window()
            return True
        descriptor = self._windows.get(normalized_label)
        if descriptor is None:
            raise KeyError(f"Unknown window label: {normalized_label}")
        descriptor["closed"] = True
        descriptor["visible"] = False
        descriptor["focused"] = False
        if descriptor.get("backend") == "native" and self._supports_native_multiwindow():
            self._app._proxy.close_window_label(normalized_label)
        else:
            self._emit_frontend_close(normalized_label)
        self._app.emit("window:closed", dict(descriptor))
        self._app._log_runtime_event("window_closed", label=normalized_label)
        return True

    # ─── Label-Targeted Window Controls ───

    def _require_label(self, label: str) -> str:
        """Normalize and validate a window label, returning the normalized form."""
        normalized = str(label).strip().lower()
        if not normalized:
            raise ValueError("Window label is required")
        if normalized not in self._windows:
            raise KeyError(f"Unknown window label: {normalized}")
        return normalized

    def set_title(self, label: str, title: str) -> None:
        """Update the title of a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.set_title(title)
            self.sync_main_window()
            return
        self._windows[normalized]["title"] = title
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_title(title)
            except Exception:
                pass

    def set_size(self, label: str, width: int | float, height: int | float) -> None:
        """Resize a specific window by label."""
        normalized = self._require_label(label)
        width_val = int(width)
        height_val = int(height)
        if width_val <= 0 or height_val <= 0:
            raise ValueError("Window width and height must be positive.")
        if normalized == "main":
            self._app.window.set_size(width_val, height_val)
            self.sync_main_window()
            return
        self._windows[normalized]["width"] = width_val
        self._windows[normalized]["height"] = height_val
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_size(float(width_val), float(height_val))
            except Exception:
                pass

    def set_position(self, label: str, x: int | float, y: int | float) -> None:
        """Move a specific window by label."""
        normalized = self._require_label(label)
        x_val = int(x)
        y_val = int(y)
        if normalized == "main":
            self._app.window.set_position(x_val, y_val)
            self.sync_main_window()
            return
        self._windows[normalized]["x"] = x_val
        self._windows[normalized]["y"] = y_val
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_position(float(x_val), float(y_val))
            except Exception:
                pass

    def focus(self, label: str) -> None:
        """Focus a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.focus()
            self.sync_main_window()
            return
        self._windows[normalized]["focused"] = True
        if self._app._proxy is not None:
            try:
                self._app._proxy.focus()
            except Exception:
                pass

    def minimize(self, label: str) -> None:
        """Minimize a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.minimize()
            self.sync_main_window()
            return
        self._windows[normalized]["minimized"] = True
        self._windows[normalized]["maximized"] = False
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_minimized(True)
            except Exception:
                pass

    def maximize(self, label: str) -> None:
        """Maximize a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.maximize()
            self.sync_main_window()
            return
        self._windows[normalized]["maximized"] = True
        self._windows[normalized]["minimized"] = False
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_maximized(True)
            except Exception:
                pass

    def set_fullscreen(self, label: str, enabled: bool) -> None:
        """Toggle fullscreen for a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.set_fullscreen(enabled)
            self.sync_main_window()
            return
        self._windows[normalized]["fullscreen"] = bool(enabled)
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_fullscreen(bool(enabled))
            except Exception:
                pass

    def show(self, label: str) -> None:
        """Show a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.show()
            self.sync_main_window()
            return
        self._windows[normalized]["visible"] = True
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_visible(True)
            except Exception:
                pass

    def hide(self, label: str) -> None:
        """Hide a specific window by label."""
        normalized = self._require_label(label)
        if normalized == "main":
            self._app.window.hide()
            self.sync_main_window()
            return
        self._windows[normalized]["visible"] = False
        if self._app._proxy is not None:
            try:
                self._app._proxy.set_visible(False)
            except Exception:
                pass
