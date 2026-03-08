"""
Forge Application (v2.0).

The main ForgeApp class that ties together the Rust native window,
the IPC bridge, the event system, and all built-in APIs.

Features:
    - Working @command decorator that actually registers commands
    - Full window config passthrough (decorations, transparent, always_on_top, etc.)
    - Threaded IPC dispatch for NoGIL parallel command execution
    - Event emitter for Python <-> JS communication
    - Lifecycle hooks (on_ready, on_close)
    - No pywebview dependency -- uses forge_core.NativeWindow (Rust/PyO3)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from .bridge import (  # noqa: F401 -- re-export
    IPCBridge,
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    command,
)
from .config import ForgeConfig, load_config
from .events import EventEmitter
from .plugins import PluginManager
from .support import CrashStore, RuntimeLogBuffer, SupportBundleBuilder, register_runtime_log_buffer
from .api.window_state import WindowStateAPI
from .api.drag_drop import DragDropAPI
from .api.drag_drop import DragDropAPI
from .api.drag_drop import DragDropAPI
from .api.drag_drop import DragDropAPI
from .api.drag_drop import DragDropAPI
from .api import ClipboardAPI, DialogAPI, FileSystemAPI, NotificationAPI, SystemAPI, MenuAPI, TrayAPI, UpdaterAPI, DeepLinkAPI, ScreenAPI, ShortcutsAPI, LifecycleAPI, OSIntegrationAPI, AutostartAPI, PowerAPI, KeychainAPI
from .api.drag_drop import DragDropAPI
from .api import ClipboardAPI, DialogAPI, FileSystemAPI, NotificationAPI, SystemAPI, MenuAPI, TrayAPI, UpdaterAPI, DeepLinkAPI, ScreenAPI, ShortcutsAPI, LifecycleAPI, OSIntegrationAPI, AutostartAPI, PowerAPI, KeychainAPI

logger = logging.getLogger(__name__)

# ─── Registry for @command decorator ───
# Commands decorated before ForgeApp is instantiated are held here,
# then bulk-registered when ForgeApp.__init__ runs.
_pending_commands: List[tuple[str, Callable]] = []


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
        """Evaluate JavaScript in the live webview."""
        self._require_proxy().evaluate_script(script)

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
            "always_on_top": bool(always_on_top),
            "visible": bool(visible),
            "focused": bool(focus),
            "closed": False,
            "backend": "native" if self._supports_native_multiwindow() else "managed-popup",
            "parent": parent,
            "created_at": time.time(),
        }
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


class RuntimeAPI:
    """Diagnostics and runtime-introspection surface for Forge applications."""

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        self._state: Dict[str, Any] = {
            "url": "forge://app/index.html",
            "devtools_open": False,
        }

    def _require_proxy(self) -> Any:
        if self._app._proxy is None:
            raise RuntimeError("The native runtime is not ready yet.")
        return self._app._proxy

    def _update_state(self, **updates: Any) -> None:
        self._state.update(updates)

    def _apply_native_event(self, event: str, payload: Dict[str, Any] | None) -> None:
        payload = payload or {}
        if event == "navigated":
            url = payload.get("url")
            if url:
                self._update_state(url=url)
        elif event == "devtools":
            self._update_state(devtools_open=bool(payload.get("open")))

    def state(self) -> Dict[str, Any]:
        """Return cached runtime state for navigation and devtools controls."""
        return dict(self._state)

    def navigate(self, url: str) -> None:
        """Navigate the native webview to a new URL."""
        self._update_state(url=url)
        self._require_proxy().load_url(url)
        self._app._log_runtime_event("runtime_navigate", url=url)

    def reload(self) -> None:
        """Reload the current native webview page."""
        self._require_proxy().reload()
        self._app._log_runtime_event("runtime_reload", url=self._state.get("url"))

    def go_back(self) -> None:
        """Navigate backward in webview history."""
        self._require_proxy().go_back()
        self._app._log_runtime_event("runtime_go_back")

    def go_forward(self) -> None:
        """Navigate forward in webview history."""
        self._require_proxy().go_forward()
        self._app._log_runtime_event("runtime_go_forward")

    def open_devtools(self) -> None:
        """Open native webview devtools when supported by the platform."""
        self._update_state(devtools_open=True)
        self._require_proxy().open_devtools()
        self._app._log_runtime_event("runtime_open_devtools")

    def close_devtools(self) -> None:
        """Close native webview devtools when supported by the platform."""
        self._update_state(devtools_open=False)
        self._require_proxy().close_devtools()
        self._app._log_runtime_event("runtime_close_devtools")

    def toggle_devtools(self) -> bool:
        """Toggle the cached devtools state and apply it to the runtime."""
        if self._state.get("devtools_open"):
            self.close_devtools()
        else:
            self.open_devtools()
        return bool(self._state.get("devtools_open"))

    def logs(self, limit: int | None = 100) -> List[Dict[str, Any]]:
        """Return recent structured runtime log entries."""
        return self._app._runtime_logs.snapshot(limit)

    def export_support_bundle(self, destination: str | Path | None = None) -> str:
        """Export a minimal support bundle zip for diagnostics collection."""
        bundle_path = self._app._support_bundle.export(destination)
        self._app._log_runtime_event("runtime_export_support_bundle", path=bundle_path)
        return bundle_path

    def protocol(self) -> Dict[str, Any]:
        """Return protocol compatibility information."""
        return {
            "current": PROTOCOL_VERSION,
            "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
        }

    def config_snapshot(self) -> Dict[str, Any]:
        """Return a serializable snapshot of effective Forge configuration."""
        config = self._app.config
        return {
            "app": {
                "name": config.app.name,
                "version": config.app.version,
                "description": config.app.description,
                "authors": list(config.app.authors),
            },
            "window": {
                "title": config.window.title,
                "width": config.window.width,
                "height": config.window.height,
                "fullscreen": config.window.fullscreen,
                "resizable": config.window.resizable,
                "decorations": config.window.decorations,
                "always_on_top": config.window.always_on_top,
                "transparent": config.window.transparent,
            },
            "build": {
                "entry": config.build.entry,
                "output_dir": config.build.output_dir,
                "single_binary": config.build.single_binary,
            },
            "protocol": {
                "schemes": list(config.protocol.schemes),
            },
            "packaging": {
                "app_id": config.packaging.app_id,
                "product_name": config.packaging.product_name,
                "formats": list(config.packaging.formats),
                "category": config.packaging.category,
            },
            "signing": {
                "enabled": config.signing.enabled,
                "adapter": config.signing.adapter,
                "identity": config.signing.identity,
                "sign_command": config.signing.sign_command,
                "verify_command": config.signing.verify_command,
                "notarize": config.signing.notarize,
                "timestamp_url": config.signing.timestamp_url,
            },
            "dev": {
                "frontend_dir": config.dev.frontend_dir,
                "hot_reload": config.dev.hot_reload,
                "port": config.dev.port,
            },
            "permissions": {
                "filesystem": config.permissions.filesystem,
                "clipboard": config.permissions.clipboard,
                "dialogs": config.permissions.dialogs,
                "notifications": config.permissions.notifications,
                "system_tray": config.permissions.system_tray,
                "updater": config.permissions.updater,
            },
            "security": {
                "allowed_commands": list(config.security.allowed_commands),
                "denied_commands": list(config.security.denied_commands),
                "expose_command_introspection": bool(config.security.expose_command_introspection),
                "allowed_origins": self._app.allowed_origins(),
                "window_scopes": {
                    key: list(value) for key, value in config.security.window_scopes.items()
                },
            },
            "plugins": self._app.plugins.summary(),
            "updater": {
                "enabled": config.updater.enabled,
                "endpoint": config.updater.endpoint,
                "channel": config.updater.channel,
                "check_on_startup": config.updater.check_on_startup,
                "allow_downgrade": config.updater.allow_downgrade,
                "public_key": config.updater.public_key,
                "require_signature": config.updater.require_signature,
                "staging_dir": config.updater.staging_dir,
                "install_dir": config.updater.install_dir,
            },
            "windows": self._app.windows.list(),
        }

    def last_crash(self) -> Dict[str, Any] | None:
        """Return the latest captured crash snapshot, if any."""
        return self._app._crash_store.snapshot()

    def commands(self) -> List[Dict[str, Any]]:
        """Return the registered command manifest."""
        return self._app.bridge.get_command_registry()

    def health(self) -> Dict[str, Any]:
        """Return a lightweight runtime health snapshot."""
        frontend_path = self._app.config.get_frontend_path()
        command_count = len(self._app.bridge.get_command_registry())
        window_state = self._app.window.state()
        ok = frontend_path.exists() and command_count > 0 and not window_state["closed"]
        return {
            "ok": ok,
            "window_ready": self._app.window.is_ready,
            "frontend_exists": frontend_path.exists(),
            "command_count": command_count,
            "window_closed": window_state["closed"],
            "window_count": len(self._app.windows.list()),
            "plugin_count": self._app.plugins.summary()["loaded"],
            "protocol": PROTOCOL_VERSION,
            "url": self._state["url"],
            "devtools_open": self._state["devtools_open"],
            "last_crash": self.last_crash() is not None,
        }

    def diagnostics(self, include_logs: bool = True, log_limit: int | None = 100) -> Dict[str, Any]:
        """Return a structured runtime diagnostics payload."""
        config = self._app.config
        payload = {
            "app": {
                "name": config.app.name,
                "version": config.app.version,
            },
            "runtime": {
                "window_ready": self._app.window.is_ready,
                "frontend_dir": str(config.get_frontend_path()),
                "config_path": str(config.config_path) if config.config_path else None,
                "state": self.state(),
            },
            "config": self.config_snapshot(),
            "protocol": self.protocol(),
            "permissions": {
                "filesystem": bool(config.permissions.filesystem),
                "clipboard": bool(config.permissions.clipboard),
                "dialogs": bool(config.permissions.dialogs),
                "notifications": bool(config.permissions.notifications),
                "system_tray": bool(config.permissions.system_tray),
                "updater": bool(config.permissions.updater),
            },
            "security": {
                "allowed_commands": list(config.security.allowed_commands),
                "denied_commands": list(config.security.denied_commands),
                "expose_command_introspection": bool(config.security.expose_command_introspection),
                "allowed_origins": self._app.allowed_origins(),
                "window_scopes": {
                    key: list(value) for key, value in config.security.window_scopes.items()
                },
            },
            "plugins": self._app.plugins.summary(),
            "window": self._app.window.state(),
            "windows": self._app.windows.list(),
            "health": self.health(),
            "commands": self.commands(),
            "crash": self.last_crash(),
            "support": {
                "bundle_export_supported": True,
            },
            "updater": {
                "enabled": bool(config.updater.enabled),
                "configured": bool(config.updater.endpoint),
                "channel": config.updater.channel,
                "check_on_startup": bool(config.updater.check_on_startup),
                "require_signature": bool(config.updater.require_signature),
                "staging_dir": config.updater.staging_dir,
                "install_dir": config.updater.install_dir,
            },
            "notifications": self._app.notifications.state()
            if self._app.has_capability("notifications")
            else None,
            "tray": self._app.tray.state() if self._app.has_capability("system_tray") else None,
            "deep_links": self._app.deep_links.state(),
        }
        if include_logs:
            payload["logs"] = self.logs(log_limit)
        return payload


class _DisabledAPI:
    """Placeholder object returned for disabled capabilities."""

    def __init__(self, capability: str) -> None:
        self._capability = capability

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(
            f"The '{self._capability}' capability is disabled in forge.toml; "
            f"cannot access '{name}'."
        )


def command(
    name: Optional[str] = None,
    capability: Optional[str] = None,
    version: str = "1.0",
) -> Callable:
    """
    Decorator to register a function as a Forge IPC command.

    Can be used at module level before the app is created -- the command
    will be registered when ForgeApp is instantiated.

    Usage:
        @command()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        @command("custom_name")
        def handler() -> dict:
            return {"status": "ok"}

    Args:
        name: Optional custom command name. Defaults to function name.
    """

    def decorator(func: Callable) -> Callable:
        cmd_name = name or func.__name__
        func._forge_cmd = cmd_name  # type: ignore[attr-defined]
        if capability is not None:
            func._forge_capability = capability  # type: ignore[attr-defined]
        func._forge_version = version  # type: ignore[attr-defined]
        _pending_commands.append((cmd_name, func))
        return func

    return decorator


class ForgeApp:
    """
    Main application class for Forge Framework v2.0.

    Manages the native window (Rust), IPC bridge, event system,
    and built-in APIs. Supports both desktop and (future) web modes.

    Args:
        config_path: Optional path to forge.toml. If None, searches
                     up from cwd.

    Example:
        ```python
        from forge import ForgeApp, command

        app = ForgeApp()

        @command()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        app.run()
        ```
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config: ForgeConfig = load_config(config_path)
        self.bridge = IPCBridge(self)
        self.plugins = PluginManager(self, self.config.plugins)
        self.events = EventEmitter()
        self._runtime_logs = RuntimeLogBuffer()
        register_runtime_log_buffer(self._runtime_logs)
        self._crash_store = CrashStore(on_crash=self._on_crash_captured)
        self._dev_server_url = os.environ.get("FORGE_DEV_SERVER_URL")
        self.window = WindowAPI(self)
        self.windows = WindowManagerAPI(self)
        self.runtime = RuntimeAPI(self)
        self._support_bundle = SupportBundleBuilder(self, self._runtime_logs)
        self._native_window: Any = None  # NativeWindow, set in run()
        self._proxy: Any = None  # WindowProxy from Rust, set via ready callback

        # Built-in APIs are attached in _setup_apis()
        self.fs: Any = _DisabledAPI("filesystem")
        self.system: Any = None
        self.menu: Any = None
        self.dialog: Any = _DisabledAPI("dialogs")
        self.clipboard: Any = _DisabledAPI("clipboard")
        self.notifications: Any = _DisabledAPI("notifications")
        self.tray: Any = _DisabledAPI("system_tray")
        self.deep_links: Any = None
        self.updater: Any = _DisabledAPI("updater")
        self.keychain: Any = _DisabledAPI("keychain")

        # Lifecycle hooks
        self._on_ready_hooks: List[Callable] = []
        self._on_close_hooks: List[Callable] = []

        # Set up built-in APIs (only those that don't need pywebview)
        self._setup_apis()
        self._register_internal_runtime_commands()
        self.plugins.load_all()
        self._log_runtime_event("app_initialized", app_name=self.config.app.name)

        # Register any commands added via @command before app was created
        self._register_pending_commands()

    def _log_runtime_event(self, event: str, **meta: Any) -> None:
        logger.info(
            event.replace("_", " "),
            extra={"forge_event": event, "forge_meta": meta},
        )

    def _on_crash_captured(self, crash: Dict[str, Any]) -> None:
        logger.error(
            "captured runtime crash",
            extra={"forge_event": "runtime_crash", "forge_meta": crash},
        )

    def _record_crash(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
        *,
        thread_name: str | None = None,
        fatal: bool = True,
    ) -> Dict[str, Any]:
        return self._crash_store.capture_exception(
            exc_type,
            exc_value,
            exc_traceback,
            thread_name=thread_name,
            fatal=fatal,
        )

    def _setup_apis(self) -> None:
        """Initialize built-in APIs and register them as IPC commands."""
        from .api.clipboard import ClipboardAPI
        from .api.deep_link import DeepLinkAPI
        from .api.dialog import DialogAPI
        from .api.fs import FileSystemAPI
        from .api.menu import MenuAPI
        from .api.notification import NotificationAPI
        from .api.system import SystemAPI
        from .api.tray import TrayAPI
        from .api.updater import UpdaterAPI
        from .api.screen import ScreenAPI
        from .api.shortcuts import ShortcutsAPI
        from .api.lifecycle import LifecycleAPI
        from .api.os_integration import OsIntegrationAPI
        from .api.autostart import AutostartAPI
        from .api.power import PowerAPI
        from .api.keychain import KeychainAPI

        fs_config = self.config.permissions.filesystem
        if fs_config:
            fs_api = FileSystemAPI(self.config.get_base_dir(), permissions=fs_config)
            self.fs = fs_api
            self.bridge.register_commands(fs_api)

        system_api = SystemAPI(
            app_name=self.config.app.name,
            app_version=self.config.app.version,
        )
        self.system = system_api
        self.bridge.register_commands(system_api)

        self.screen = ScreenAPI(self)
        self.bridge.register_commands(self.screen)

        self.shortcuts = ShortcutsAPI(self)
        self.bridge.register_commands(self.shortcuts)

        self.lifecycle = LifecycleAPI(self)
        self.bridge.register_commands(self.lifecycle)

        self.os_integration = OsIntegrationAPI(self)
        self.bridge.register_commands(self.os_integration)

        self.autostart = AutostartAPI(self)
        self.bridge.register_commands(self.autostart)

        self.power = PowerAPI(self)
        self.bridge.register_commands(self.power)

        if self.config.permissions.keychain:
            self.keychain = KeychainAPI(self)
            self.bridge.register_commands(self.keychain)

        # Initialize Window State Auto-Persistency
        self.window_state = WindowStateAPI(self)
        self.drag_drop = DragDropAPI(self)
        self.printing = PrintingAPI(self)
        # Initialize Window State Auto-Persistency
        self.window_state = WindowStateAPI(self)
        self.drag_drop = DragDropAPI(self)
        self.printing = PrintingAPI(self)
        self.menu = MenuAPI(self)
        self.bridge.register_commands(self.menu)

        self.deep_links = DeepLinkAPI(self, self.config.protocol.schemes)
        self.bridge.register_commands(self.deep_links)

        if self.config.permissions.dialogs:
            self.dialog = DialogAPI()
            self.bridge.register_commands(self.dialog)

        if self.config.permissions.clipboard:
            self.clipboard = ClipboardAPI()
            self.bridge.register_commands(self.clipboard)

        if self.config.permissions.notifications:
            self.notifications = NotificationAPI(self)
            self.bridge.register_commands(self.notifications)

        if self.config.permissions.system_tray:
            self.tray = TrayAPI(self)
            self.tray.set_action_handler(
                lambda action, payload=None: self.emit(
                    "tray:select",
                    {
                        "action": action,
                        "payload": payload,
                    },
                )
            )
            self.bridge.register_commands(self.tray)

        if self.config.permissions.updater and self.config.updater.enabled:
            self.updater = UpdaterAPI(
                app_name=self.config.app.name,
                current_version=self.config.app.version,
                config=self.config.updater,
                base_dir=self.config.get_base_dir(),
            )
            self.bridge.register_commands(self.updater)

    def _register_pending_commands(self) -> None:
        """Register commands that were decorated before the app was created."""
        global _pending_commands
        for cmd_name, func in _pending_commands:
            self.bridge.register_command(cmd_name, func)
        _pending_commands.clear()

    def _register_internal_runtime_commands(self) -> None:
        """Register internal runtime commands consumed by the JS bridge."""
        self.bridge.register_command(
            "__forge_window_set_title",
            self._ipc_window_set_title,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_runtime_plugins",
            self._ipc_runtime_plugins,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_runtime_security",
            self._ipc_runtime_security,
            version="1.0",
            internal=True,
        )
        for command_name, handler in [
            ("__forge_runtime_health", self._ipc_runtime_health),
            ("__forge_runtime_diagnostics", self._ipc_runtime_diagnostics),
            ("__forge_runtime_commands", self._ipc_runtime_commands),
            ("__forge_runtime_protocol", self._ipc_runtime_protocol),
            ("__forge_runtime_last_crash", self._ipc_runtime_last_crash),
            ("__forge_runtime_logs", self._ipc_runtime_logs),
            ("__forge_runtime_get_state", self._ipc_runtime_get_state),
            ("__forge_runtime_reload", self._ipc_runtime_reload),
            ("__forge_runtime_go_back", self._ipc_runtime_go_back),
            ("__forge_runtime_go_forward", self._ipc_runtime_go_forward),
            ("__forge_runtime_open_devtools", self._ipc_runtime_open_devtools),
            ("__forge_runtime_close_devtools", self._ipc_runtime_close_devtools),
            ("__forge_runtime_toggle_devtools", self._ipc_runtime_toggle_devtools),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)
        self.bridge.register_command(
            "__forge_runtime_navigate",
            self._ipc_runtime_navigate,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_runtime_export_support_bundle",
            self._ipc_runtime_export_support_bundle,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_window_set_size",
            self._ipc_window_set_size,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_window_set_fullscreen",
            self._ipc_window_set_fullscreen,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_window_set_always_on_top",
            self._ipc_window_set_always_on_top,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_window_set_position",
            self._ipc_window_set_position,
            version="1.0",
            internal=True,
        )
        self.bridge.register_command(
            "__forge_window_get_state",
            self._ipc_window_get_state,
            version="1.0",
            internal=True,
        )
        for command_name, handler in [
            ("__forge_window_get_position", self._ipc_window_get_position),
            ("__forge_window_is_visible", self._ipc_window_is_visible),
            ("__forge_window_is_focused", self._ipc_window_is_focused),
            ("__forge_window_is_minimized", self._ipc_window_is_minimized),
            ("__forge_window_is_maximized", self._ipc_window_is_maximized),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)

        for command_name, handler in [
            ("__forge_window_show", self._ipc_window_show),
            ("__forge_window_hide", self._ipc_window_hide),
            ("__forge_window_focus", self._ipc_window_focus),
            ("__forge_window_minimize", self._ipc_window_minimize),
            ("__forge_window_unminimize", self._ipc_window_unminimize),
            ("__forge_window_maximize", self._ipc_window_maximize),
            ("__forge_window_unmaximize", self._ipc_window_unmaximize),
            ("__forge_window_close", self._ipc_window_close),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)

        for command_name, handler in [
            ("__forge_windows_current", self._ipc_windows_current),
            ("__forge_windows_list", self._ipc_windows_list),
            ("__forge_windows_get", self._ipc_windows_get),
            ("__forge_window_create", self._ipc_window_create),
            ("__forge_window_close_label", self._ipc_window_close_label),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)

    def _ipc_window_set_title(self, title: str) -> bool:
        self.window.set_title(title)
        return True

    def _ipc_runtime_health(self) -> Dict[str, Any]:
        return self.runtime.health()

    def _ipc_runtime_diagnostics(self) -> Dict[str, Any]:
        return self.runtime.diagnostics()

    def _ipc_runtime_commands(self) -> List[Dict[str, Any]]:
        return self.runtime.commands()

    def _ipc_runtime_protocol(self) -> Dict[str, Any]:
        return self.runtime.protocol()

    def _ipc_runtime_plugins(self) -> Dict[str, Any]:
        return self.plugins.summary()

    def _ipc_runtime_security(self) -> Dict[str, Any]:
        return {
            "allowed_commands": list(self.config.security.allowed_commands),
            "denied_commands": list(self.config.security.denied_commands),
            "expose_command_introspection": bool(self.config.security.expose_command_introspection),
            "allowed_origins": self.allowed_origins(),
            "window_scopes": {
                key: list(value) for key, value in self.config.security.window_scopes.items()
            },
        }

    def _ipc_runtime_last_crash(self) -> Dict[str, Any] | None:
        return self.runtime.last_crash()

    def _ipc_runtime_logs(self, limit: int | None = 100) -> List[Dict[str, Any]]:
        return self.runtime.logs(limit)

    def _ipc_runtime_get_state(self) -> Dict[str, Any]:
        return self.runtime.state()

    def _ipc_runtime_navigate(self, url: str) -> bool:
        self.runtime.navigate(url)
        return True

    def _ipc_runtime_reload(self) -> bool:
        self.runtime.reload()
        return True

    def _ipc_runtime_go_back(self) -> bool:
        self.runtime.go_back()
        return True

    def _ipc_runtime_go_forward(self) -> bool:
        self.runtime.go_forward()
        return True

    def _ipc_runtime_open_devtools(self) -> bool:
        self.runtime.open_devtools()
        return True

    def _ipc_runtime_close_devtools(self) -> bool:
        self.runtime.close_devtools()
        return True

    def _ipc_runtime_toggle_devtools(self) -> bool:
        return self.runtime.toggle_devtools()

    def _ipc_runtime_export_support_bundle(self, destination: str | None = None) -> str:
        return self.runtime.export_support_bundle(destination)

    def _ipc_window_set_size(self, width: int | float, height: int | float) -> bool:
        self.window.set_size(width, height)
        return True

    def _ipc_window_set_fullscreen(self, enabled: bool) -> bool:
        self.window.set_fullscreen(enabled)
        return True

    def _ipc_window_set_position(self, x: int | float, y: int | float) -> bool:
        self.window.set_position(x, y)
        return True

    def _ipc_window_set_always_on_top(self, enabled: bool) -> bool:
        self.window.set_always_on_top(enabled)
        return True

    def _ipc_window_get_state(self) -> Dict[str, Any]:
        return self.window.state()

    def _ipc_window_get_position(self) -> Dict[str, Any]:
        return self.window.position()

    def _ipc_screen_get_monitors(self) -> List[Dict[str, Any]]:
        self.screen._require_capability()
        if not self._is_ready or not self._proxy:
            return []
        try:
            res = self._proxy.get_monitors()
            return json.loads(res) if res else []
        except Exception:
            return []

    def _ipc_screen_get_primary(self) -> Dict[str, Any] | None:
        self.screen._require_capability()
        if not self._is_ready or not self._proxy:
            return None
        try:
            res = self._proxy.get_primary_monitor()
            return json.loads(res) if res else None
        except Exception:
            return None

    def _ipc_screen_get_cursor(self) -> Dict[str, int]:
        self.screen._require_capability()
        if not self._is_ready or not self._proxy:
            return {"x": 0, "y": 0}
        try:
            res = self._proxy.get_cursor_position()
            return json.loads(res) if res else {"x": 0, "y": 0}
        except Exception:
            return {"x": 0, "y": 0}

    def _ipc_shortcuts_register(self, accelerator: str) -> bool:
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.register_shortcut(accelerator)
        except Exception:
            return False

    def _ipc_shortcuts_unregister(self, accelerator: str) -> bool:
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.unregister_shortcut(accelerator)
        except Exception:
            return False

    def _ipc_shortcuts_unregister_all(self) -> bool:
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.unregister_all_shortcuts()
        except Exception:
            return False

    def _ipc_os_set_progress_bar(self, progress: float) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.os_set_progress_bar(progress)
        except Exception:
            return False

    def _ipc_os_request_user_attention(self, is_critical: bool) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            type_str = "critical" if is_critical else "informational"
            return self._proxy.os_request_user_attention(type_str)
        except Exception:
            return False

    def _ipc_os_clear_user_attention(self) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.os_request_user_attention("")
        except Exception:
            return False

    def _ipc_window_is_visible(self) -> bool:
        return self.window.is_visible()

    def _ipc_window_is_focused(self) -> bool:
        return self.window.is_focused()

    def _ipc_window_is_minimized(self) -> bool:
        return self.window.is_minimized()

    def _ipc_window_is_maximized(self) -> bool:
        return self.window.is_maximized()

    def _ipc_window_show(self) -> bool:
        self.window.show()
        return True

    def _ipc_window_hide(self) -> bool:
        self.window.hide()
        return True

    def _ipc_window_focus(self) -> bool:
        self.window.focus()
        return True

    def _ipc_window_minimize(self) -> bool:
        self.window.minimize()
        return True

    def _ipc_window_unminimize(self) -> bool:
        self.window.unminimize()
        return True

    def _ipc_window_maximize(self) -> bool:
        self.window.maximize()
        return True

    def _ipc_window_unmaximize(self) -> bool:
        self.window.unmaximize()
        return True

    def _ipc_window_close(self) -> bool:
        self.window.close()
        return True

    def _ipc_windows_current(self) -> Dict[str, Any]:
        return self.windows.current()

    def _ipc_windows_list(self) -> List[Dict[str, Any]]:
        return self.windows.list()

    def _ipc_windows_get(self, label: str) -> Dict[str, Any]:
        return self.windows.get(label)

    def _ipc_window_create(self, **options: Any) -> Dict[str, Any]:
        return self.windows.create(**options)

    def _ipc_window_close_label(self, label: str) -> bool:
        return self.windows.close(label)

    def _ipc_power_get_battery_info(self) -> Dict[str, Any]:
        self.power._require_capability()
        if not self._is_ready or not self._proxy:
            return {}
        try:
            res = self._proxy.power_get_battery_info()
            return json.loads(res) if res else {}
        except Exception:
            return {}

    # ─── Command Registration (instance-level) ───

    def register_command(self, name: str, func: Callable) -> None:
        """
        Register a custom IPC command at runtime.

        Args:
            name: The command name.
            func: The callable to execute.
        """
        self.bridge.register_command(name, func)

    def has_capability(self, capability: str, *, window_label: str | None = None) -> bool:
        """Return whether a named capability is enabled for this app and window scope."""
        if capability == "system":
            return True

        enabled = bool(getattr(self.config.permissions, capability, False))
        if not enabled:
            return False

        if window_label is None:
            return enabled

        scopes = self.config.security.window_scopes or {}
        normalized_label = str(window_label).strip().lower() or "main"
        if normalized_label not in scopes:
            return enabled

        allowed = {item for item in scopes.get(normalized_label, []) if isinstance(item, str)}
        if not allowed:
            return False
        return capability in allowed or "*" in allowed or "all" in allowed

    def allowed_origins(self) -> List[str]:
        """Return normalized allowed origins for frontend IPC."""
        origins = list(self.config.security.allowed_origins)
        if not any(origin.startswith("forge://app") for origin in origins):
            origins.append("forge://app")
        if self._dev_server_url:
            origins.append(self._dev_server_url)

        deduped: List[str] = []
        for origin in origins:
            if origin and origin not in deduped:
                deduped.append(origin)
        return deduped

    def is_origin_allowed(self, origin: str | None) -> bool:
        """Return whether a caller origin is allowed to use the IPC bridge."""
        if not origin:
            return True

        parsed_origin = urlparse(origin)
        normalized_origin = (
            f"{parsed_origin.scheme}://{parsed_origin.netloc}"
            if parsed_origin.scheme in {"http", "https"} and parsed_origin.netloc
            else origin
        )

        for allowed in self.allowed_origins():
            if allowed.startswith("forge://"):
                if origin.startswith(allowed):
                    return True
                continue

            parsed_allowed = urlparse(allowed)
            allowed_origin = (
                f"{parsed_allowed.scheme}://{parsed_allowed.netloc}"
                if parsed_allowed.scheme in {"http", "https"} and parsed_allowed.netloc
                else allowed
            )
            if normalized_origin == allowed_origin:
                return True
        return False

    def command(
        self,
        func: Optional[Callable] = None,
        name: Optional[str] = None,
        capability: Optional[str] = None,
        version: str = "1.0",
    ) -> Callable:
        """
        Register an instance-bound IPC command.

        Supported usage:
            @app.command
            def greet(...): ...

            @app.command()
            def greet(...): ...

            @app.command("custom_name")
            def greet(...): ...

            @app.command(name="custom_name")
            def greet(...): ...
        """
        if callable(func):
            cmd_name = getattr(func, "_forge_cmd", None) or func.__name__
            if capability is not None:
                func._forge_capability = capability  # type: ignore[attr-defined]
            func._forge_version = version  # type: ignore[attr-defined]
            self.register_command(cmd_name, func)
            return func

        if isinstance(func, str):
            name = func

        def decorator(target: Callable) -> Callable:
            cmd_name = name or getattr(target, "_forge_cmd", None) or target.__name__
            if capability is not None:
                target._forge_capability = capability  # type: ignore[attr-defined]
            target._forge_version = version  # type: ignore[attr-defined]
            self.register_command(cmd_name, target)
            return target

        return decorator

    # ─── IPC Message Handling ───

    def _on_ipc_message(self, message: str, proxy: Any) -> None:
        """
        Handle an incoming IPC message from the Rust engine.

        Dispatches the message through the bridge, which handles
        parsing, validation, execution, and response serialization.

        The response is sent back to JS via the WindowProxy's
        evaluate_script method (avoids PyO3 borrow conflict with NativeWindow).

        Args:
            message: Raw JSON string from the frontend.
            proxy: WindowProxy instance for sending JS responses.
        """
        try:
            # Store proxy for later use (e.g. emit())
            if self._proxy is None:
                self._proxy = proxy

            logger.debug(f"IPC received: {message[:200]}")

            # Use the bridge's full invoke pipeline (validates, executes, returns JSON)
            response_json = self.bridge.invoke_command(message)

            logger.debug(f"IPC response: {response_json[:200]}")

            # Parse to extract the message ID for the JS callback
            response = json.loads(response_json)
            msg_id = response.get("id")

            if msg_id is not None:
                js_call = f"window.__forge__._handleMessage({response_json})"
                logger.debug(f"Sending to JS: {js_call[:200]}")
                proxy.evaluate_script(js_call)
        except Exception as e:
            logger.error(f"Failed to process IPC message: {e}")
            import traceback

            traceback.print_exc()
            # Try to send error response back to JS
            try:
                error_response = json.dumps({"id": None, "result": None, "error": str(e)})
                proxy.evaluate_script(f"window.__forge__._handleMessage({error_response})")
            except Exception:
                pass  # Last resort — can't send to JS either

    def _sync_native_menu(self, items: List[Dict[str, Any]] | None = None) -> None:
        """Push the current menu model into the native runtime when available."""
        if self._proxy is None or self.menu is None:
            return

        payload = self.menu.get() if items is None else items
        if items is None and not payload:
            return
        try:
            self._proxy.set_menu(json.dumps(payload))
            self._log_runtime_event("menu_sync", items=len(payload))
        except Exception as exc:
            logger.warning(f"failed to sync native menu: {exc}")

    def _on_window_ready(self, proxy: Any) -> None:
        """
        Called by the Rust engine once the window and WebView are ready.

        Stores the WindowProxy and fires on_ready lifecycle hooks.

        Args:
            proxy: WindowProxy instance for sending JS to the WebView.
        """
        self._proxy = proxy
        self.window._apply_native_event("ready", None)
        self.windows.sync_main_window()
        self.runtime._apply_native_event("ready", None)
        self._sync_native_menu()
        if self._dev_server_url:
            self.runtime._update_state(url=self._dev_server_url)
            try:
                proxy.load_url(self._dev_server_url)
                self._log_runtime_event("dev_server_navigate", url=self._dev_server_url)
            except Exception as e:
                logger.error(f"failed to navigate to configured dev server: {e}")
        self._log_runtime_event("window_ready")
        self.emit("window:ready", self.window.state())

        for hook in self._on_ready_hooks:
            try:
                hook()
            except Exception as e:
                logger.error(f"on_ready hook failed: {e}")

    def _on_window_event(self, event: str, payload_json: str) -> None:
        """Handle native window lifecycle/state events emitted by the Rust runtime."""
        try:
            payload = json.loads(payload_json) if payload_json else None
        except Exception:
            payload = None

        if event == "menu_selected" and isinstance(payload, dict):
            item_id = payload.get("id")
            if isinstance(item_id, str) and self.menu is not None:
                try:
                    item = self.menu.apply_native_selection(item_id, payload.get("checked"))
                    payload.setdefault("label", item.get("label"))
                    payload.setdefault("role", item.get("role"))
                except Exception as exc:
                    logger.warning(f"failed to apply native menu selection: {exc}")
            self._log_runtime_event("native_event", name=event, payload=payload)
            self.emit("menu:select", payload)
            self.emit(f"window:{event}", payload)
            return

        label = self.windows._apply_native_event(event, payload if isinstance(payload, dict) else None)
        if label == "main":
            self.window._apply_native_event(event, payload)
            self.windows.sync_main_window()
        self.runtime._apply_native_event(event, payload)
        self._log_runtime_event("native_event", name=event, payload=payload)
        self.emit(f"window:{event}", payload)

    # ─── Frontend Communication ───

    def emit(self, event: str, payload: Any = None) -> None:
        """
        Emit an event to the JavaScript frontend.

        Also dispatches to Python-side event listeners.

        Args:
            event: Event name.
            payload: Optional JSON-serializable data.
        """
        # Python-side listeners
        self.events.emit(event, payload)

        # JS-side listeners — use the WindowProxy (not NativeWindow)
        if self._proxy is not None:
            data = json.dumps({"type": "event", "event": event, "payload": payload})
            self._proxy.evaluate_script(f"window.__forge__._handleMessage({data})")

    # ─── Lifecycle Hooks ───

    def on_ready(self, func: Callable) -> Callable:
        """
        Register a callback to run after the window is created.

        Can be used as a decorator:
            @app.on_ready
            def startup():
                print("App is ready!")
        """
        self._on_ready_hooks.append(func)
        return func

    def on_close(self, func: Callable) -> Callable:
        """
        Register a callback to run before the window closes.

        Can be used as a decorator:
            @app.on_close
            def cleanup():
                print("Cleaning up...")
        """
        self._on_close_hooks.append(func)
        return func

    # ─── Run ───

    def run(self, debug: bool = False) -> None:
        """
        Launch the native window and block until it closes.

        This method:
        1. Copies forge.js into the frontend directory
        2. Creates the NativeWindow with full config passthrough
        3. Registers the IPC handler and ready callback
        4. Starts the native OS event loop (blocks)
        5. Fires on_close hooks when the event loop exits

        Args:
            debug: Enable debug logging if True.
        """
        if debug:
            logging.basicConfig(level=logging.DEBUG)

        # Resolve frontend path
        base_dir = self.config.get_base_dir()
        frontend_path = base_dir / self.config.dev.frontend_dir

        if not frontend_path.exists():
            logger.error(f"Frontend directory not found: {frontend_path}")
            print(f"Error: Could not find frontend directory at {frontend_path}")
            return

        # Copy forge.js into the frontend directory
        forge_js_src = os.path.join(os.path.dirname(__file__), "js", "forge.js")
        forge_js_dest = frontend_path / "forge.js"
        if os.path.exists(forge_js_src):
            shutil.copy2(forge_js_src, str(forge_js_dest))

        # Import the Rust extension
        from .forge_core import NativeWindow

        # Create the native window with full config passthrough
        wc = self.config.window
        # Get persistent state for main window
        state = self.window_state.get_state("main")
        w_width = float(state.get("width", wc.width))
        w_height = float(state.get("height", wc.height))
        w_x = state.get("x", None)
        w_y = state.get("y", None)
        if w_x is not None: w_x = float(w_x)
        if w_y is not None: w_y = float(w_y)

        # Get persistent state for main window
        state = self.window_state.get_state("main")
        w_width = float(state.get("width", wc.width))
        w_height = float(state.get("height", wc.height))
        w_x = state.get("x", None)
        w_y = state.get("y", None)
        if w_x is not None: w_x = float(w_x)
        if w_y is not None: w_y = float(w_y)

        self._native_window = NativeWindow(
            wc.title or self.config.app.name,
            str(frontend_path),
            w_width,
            w_height,
            wc.fullscreen,
            wc.resizable,
            wc.decorations,
            wc.transparent,
            wc.always_on_top,
            float(wc.min_width),
            float(wc.min_height),
            w_x,
            w_y,
            wc.vibrancy,
        )

        # Register IPC handler — receives (message, proxy) from Rust
        self._native_window.set_ipc_callback(self._on_ipc_message)

        # Register ready callback — receives (proxy,) once window is created
        self._native_window.set_ready_callback(self._on_window_ready)
        self._native_window.set_window_event_callback(self._on_window_event)

        # Start the native event loop (blocks until window closes)
        try:
            self._crash_store.install()
            self._native_window.run()
        finally:
            self._crash_store.uninstall()
            # Fire on_close hooks
            for hook in self._on_close_hooks:
                try:
                    hook()
                except Exception as e:
                    logger.error(f"on_close hook failed: {e}")

            # Clean up the thread pool
            self.bridge.shutdown()
