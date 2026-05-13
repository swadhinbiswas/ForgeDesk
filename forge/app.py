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
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from .api import (  # noqa: F401
    AutostartAPI,
    ClipboardAPI,
    DeepLinkAPI,
    DialogAPI,
    DragDropAPI,
    FileSystemAPI,
    KeychainAPI,
    LifecycleAPI,
    MenuAPI,
    NotificationAPI,
    OpenerAPI,
    OSIntegrationAPI,
    PositionerAPI,
    PowerAPI,
    PrintingAPI,
    ScreenAPI,
    ShellAPI,
    ShortcutsAPI,
    SystemAPI,
    TrayAPI,
    UpdaterAPI,
    WebSocketAPI,
    WindowMessagingAPI,
    WindowStateAPI,
)
from .bridge import (  # noqa: F401 -- re-export
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    IPCBridge,
    command,
)
from .builtins import setup_builtin_plugins
from .channels import ChannelManager
from .config import ForgeConfig, load_config
from .events import EventEmitter
from .plugins import PluginManager
from .runtime import RuntimeAPI
from .state import AppState
from .support import CrashStore, RuntimeLogBuffer, SupportBundleBuilder, register_runtime_log_buffer
from .tasks import TaskManager
from .window import WindowAPI, WindowManagerAPI

logger = logging.getLogger(__name__)

# ─── Registry for @command decorator ───
# Commands decorated before ForgeApp is instantiated are held here,
# then bulk-registered when ForgeApp.__init__ runs.
_pending_commands: list[tuple[str, Callable]] = []


# WindowAPI, WindowManagerAPI imported from .window
# RuntimeAPI imported from .runtime
# (Stale inline definitions removed — canonical versions live in window.py and runtime.py)


class _DisabledAPI:
    """Placeholder object returned for disabled capabilities."""

    def __init__(self, capability: str) -> None:
        self._capability = capability

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(
            f"The '{self._capability}' capability is disabled in forge.toml; "
            f"cannot access '{name}'."
        )


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

    def __init__(self, config_path: str | None = None) -> None:
        self.config: ForgeConfig = load_config(config_path)
        self.bridge = IPCBridge(self)
        self.plugins = PluginManager(self, self.config.plugins)
        self.events = EventEmitter()
        self._runtime_logs = RuntimeLogBuffer()
        register_runtime_log_buffer(self._runtime_logs)
        self._crash_store = CrashStore(on_crash=self._on_crash_captured)
        self._dev_server_url = (
            os.environ.get("FORGE_DEV_SERVER_URL") or self.config.dev.dev_server_url
        )
        self._debug = False
        self.window = WindowAPI(self)
        self.windows = WindowManagerAPI(self)
        self.runtime = RuntimeAPI(self)
        self._support_bundle = SupportBundleBuilder(self, self._runtime_logs)
        self._is_ready: bool = False
        self._native_window: Any = None  # NativeWindow, set in run()
        self._proxy: Any = None  # WindowProxy from Rust, set via ready callback
        self.state = AppState()  # Thread-safe typed state container (Tauri State<T> equivalent)
        self.tasks = TaskManager(self)
        self.channels = ChannelManager()

        # Built-in APIs are attached in _setup_apis()
        self.fs: Any = _DisabledAPI("filesystem")
        self.shell: Any = _DisabledAPI("shell")
        self.system: Any = None
        self.menu: Any = None
        self.dialog: Any = _DisabledAPI("dialogs")
        self.clipboard: Any = _DisabledAPI("clipboard")
        self.notifications: Any = _DisabledAPI("notifications")
        self.tray: Any = _DisabledAPI("system_tray")
        self.deep_links: Any = None
        self.updater: Any = _DisabledAPI("updater")
        self.keychain: Any = _DisabledAPI("keychain")
        self.serial: Any = None

        # Lifecycle hooks
        self._on_ready_hooks: list[Callable] = []
        self._on_close_hooks: list[Callable] = []

        # Set up built-in APIs (only those that don't need pywebview)
        self._setup_apis()
        self._register_internal_runtime_commands()
        setup_builtin_plugins(self)
        self.plugins.load_all()
        self._log_runtime_event("app_initialized", app_name=self.config.app.name)

        # Register any commands added via @command before app was created
        self._register_pending_commands()

    def _log_runtime_event(self, event: str, **meta: Any) -> None:
        logger.info(
            event.replace("_", " "),
            extra={"forge_event": event, "forge_meta": meta},
        )

    def _on_crash_captured(self, crash: dict[str, Any]) -> None:
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
    ) -> dict[str, Any]:
        return self._crash_store.capture_exception(
            exc_type,
            exc_value,
            exc_traceback,
            thread_name=thread_name,
            fatal=fatal,
        )

    def include_router(self, router: Any) -> None:
        """
        Include commands from a Router.
        """
        for name, command_func in router.commands.items():

            def register(name: str = name, func: Any = command_func) -> None:  # type: ignore[no-untyped-def]
                cap_req = getattr(func, "__forge_capability__", None)
                getattr(func, "__forge_plugin__", None)
                if cap_req and getattr(self, "config", None):
                    if not getattr(self.config.permissions, cap_req, False):
                        return
                # we bypass exact capabilities or plugins check if it's missing in config for simplicity,  # noqa: E501
                # bridge handles the actual invocation, but we map endpoints here anyway
                self.bridge.register_command(
                    name, func, capability=cap_req, version="1.0", internal=False
                )

            register()

    def _setup_apis(self) -> None:
        """Initialize built-in APIs and register them as IPC commands."""
        # Note: Using top-level imports from .api

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

        self.os_integration = OSIntegrationAPI(self)
        self.bridge.register_commands(self.os_integration)

        if self.config.permissions.shell:
            self.shell = ShellAPI(self, self.config.get_base_dir(), self.config.permissions.shell)
            self.bridge.register_commands(self.shell)

        self.autostart = AutostartAPI(self)
        self.bridge.register_commands(self.autostart)

        self.power = PowerAPI(self)
        self.bridge.register_commands(self.power)

        if self.config.permissions.keychain:
            self.keychain = KeychainAPI(self)
            self.bridge.register_commands(self.keychain)

        # Initialize Window State Auto-Persistency (opt-in via config.window.remember_state)
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

        self.window_messaging = WindowMessagingAPI(self)
        self.bridge.register_commands(self.window_messaging)

        self.positioner = PositionerAPI(self)
        self.bridge.register_commands(self.positioner)

        self.opener = OpenerAPI()
        self.bridge.register_commands(self.opener)

        # Register task API dynamically inline
        class TaskIPC:
            __forge_capability__ = "tasks"

            def task_start(p, name: str, interval: float | None = None) -> str:  # noqa: N805  # p shadows outer scope; self would conflict
                if interval is not None and interval <= 0:
                    raise ValueError("interval must be greater than 0")

                if interval is None:

                    def _persistent(cancel_event: Any) -> str:
                        while not cancel_event.is_set():
                            cancel_event.wait(0.25)
                        return "cancelled"

                    return self.tasks.start(name=name, fn=_persistent)

                def _ticker() -> None:
                    self.emit("task:tick", {"name": name, "interval": interval})

                return self.tasks.start(name=name, fn=_ticker, interval=interval)

            def task_cancel(p, task_id: str) -> bool:  # noqa: N805
                return self.tasks.cancel(task_id)

            def task_status(p, task_id: str) -> dict | None:  # noqa: N805
                return self.tasks.status(task_id)

            def task_list(p) -> list:  # noqa: N805
                return self.tasks.list_tasks()

        self.bridge.register_commands(TaskIPC())

        ws_config = self.config.permissions.websocket
        if ws_config:
            self.ws = WebSocketAPI(self)
            self.bridge.register_commands(self.ws)

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

        if getattr(self.config.permissions, "serial", False):
            from .api.serial import SerialAPI

            self.serial = SerialAPI()
            self.bridge.register_commands(self.serial)

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
            "__forge_runtime_log_from_js",
            self._ipc_runtime_log_from_js,
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
            "__forge_window_set_vibrancy",
            self._ipc_window_set_vibrancy,
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
        for command_name, handler in [  # type: ignore[assignment]
            ("__forge_window_get_position", self._ipc_window_get_position),
            ("__forge_window_is_visible", self._ipc_window_is_visible),
            ("__forge_window_is_focused", self._ipc_window_is_focused),
            ("__forge_window_is_minimized", self._ipc_window_is_minimized),
            ("__forge_window_is_maximized", self._ipc_window_is_maximized),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)

        for command_name, handler in [  # type: ignore[assignment]
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

        for command_name, handler in [  # type: ignore[assignment]
            ("__forge_windows_current", self._ipc_windows_current),
            ("__forge_windows_list", self._ipc_windows_list),
            ("__forge_windows_get", self._ipc_windows_get),
            ("__forge_window_create", self._ipc_window_create),
            ("__forge_window_close_label", self._ipc_window_close_label),
            ("__forge_windows_set_title", self._ipc_windows_set_title),
            ("__forge_windows_set_size", self._ipc_windows_set_size),  # type: ignore[assignment]
            ("__forge_windows_set_position", self._ipc_windows_set_position),
            ("__forge_windows_focus", self._ipc_windows_focus),
            ("__forge_windows_minimize", self._ipc_windows_minimize),
            ("__forge_windows_maximize", self._ipc_windows_maximize),
            ("__forge_windows_set_fullscreen", self._ipc_windows_set_fullscreen),
            ("__forge_windows_show", self._ipc_windows_show),
            ("__forge_windows_hide", self._ipc_windows_hide),
        ]:
            self.bridge.register_command(command_name, handler, version="1.0", internal=True)

    def _ipc_window_set_title(self, title: str) -> bool:
        self.window.set_title(title)
        return True

    def _ipc_runtime_health(self) -> dict[str, Any]:
        return self.runtime.health()

    def _ipc_runtime_diagnostics(self) -> dict[str, Any]:
        return self.runtime.diagnostics()

    def _ipc_runtime_commands(self) -> list[dict[str, Any]]:
        return self.runtime.commands()

    def _ipc_runtime_protocol(self) -> dict[str, Any]:
        return self.runtime.protocol()

    def _ipc_runtime_plugins(self) -> dict[str, Any]:
        return self.plugins.summary()

    def _ipc_runtime_security(self) -> dict[str, Any]:
        return {
            "allowed_commands": list(self.config.security.allowed_commands),
            "denied_commands": list(self.config.security.denied_commands),
            "allow_devtools": self.config.security.allow_devtools,
            "expose_command_introspection": bool(self.config.security.expose_command_introspection),
            "allowed_origins": self.allowed_origins(),
            "window_scopes": {
                key: list(value) for key, value in self.config.security.window_scopes.items()
            },
        }

    def _ipc_runtime_last_crash(self) -> dict[str, Any] | None:
        return self.runtime.last_crash()

    def _ipc_runtime_logs(self, limit: int | None = 100) -> list[dict[str, Any]]:
        return self.runtime.logs(limit)

    def _ipc_runtime_get_state(self) -> dict[str, Any]:
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

    def _ipc_runtime_log_from_js(
        self, level: str, message: str, context: dict | None = None
    ) -> bool:
        ctx = context or {}
        if level == "error":
            logger.error(f"[JS] {message}", extra={"forge_event": "js_log", "forge_meta": ctx})
        elif level == "warn" or level == "warning":
            logger.warning(f"[JS] {message}", extra={"forge_event": "js_log", "forge_meta": ctx})
        elif level == "debug":
            logger.debug(f"[JS] {message}", extra={"forge_event": "js_log", "forge_meta": ctx})
        else:
            logger.info(f"[JS] {message}", extra={"forge_event": "js_log", "forge_meta": ctx})
        return True

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

    def _ipc_window_set_vibrancy(self, effect: str | None) -> bool:
        self.window.set_vibrancy(effect)
        return True

    def _ipc_window_get_state(self) -> dict[str, Any]:
        return self.window.state()

    def _ipc_window_get_position(self) -> dict[str, Any]:
        return self.window.position()

    def _ipc_screen_get_monitors(self) -> list[dict[str, Any]]:
        self.screen._require_capability()
        if not self._is_ready or not self._proxy:
            return []
        try:
            res = self._proxy.get_monitors()
            return json.loads(res) if res else []
        except Exception:
            return []

    def _ipc_screen_get_primary(self) -> dict[str, Any] | None:
        self.screen._require_capability()
        if not self._is_ready or not self._proxy:
            return None
        try:
            res = self._proxy.get_primary_monitor()
            return json.loads(res) if res else None
        except Exception:
            return None

    def _ipc_screen_get_cursor(self) -> dict[str, int]:
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
            return self._proxy.register_shortcut(accelerator)  # type: ignore[no-any-return]
        except Exception:
            return False

    def _ipc_shortcuts_unregister(self, accelerator: str) -> bool:
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.unregister_shortcut(accelerator)  # type: ignore[no-any-return]
        except Exception:
            return False

    def _ipc_shortcuts_unregister_all(self) -> bool:
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.unregister_all_shortcuts()  # type: ignore[no-any-return]
        except Exception:
            return False

    def _ipc_os_set_progress_bar(self, progress: float) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.os_set_progress_bar(progress)  # type: ignore[no-any-return]
        except Exception:
            return False

    def _ipc_os_request_user_attention(self, is_critical: bool) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            type_str = "critical" if is_critical else "informational"
            return self._proxy.os_request_user_attention(type_str)  # type: ignore[no-any-return]
        except Exception:
            return False

    def _ipc_os_clear_user_attention(self) -> bool:
        self.os_integration._require_capability()
        if not self._is_ready or not self._proxy:
            return False
        try:
            return self._proxy.os_request_user_attention("")  # type: ignore[no-any-return]
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

    def _ipc_windows_current(self) -> dict[str, Any]:
        return self.windows.current()

    def _ipc_windows_list(self) -> list[dict[str, Any]]:
        return self.windows.list()

    def _ipc_windows_get(self, label: str) -> dict[str, Any]:
        return self.windows.get(label)

    def _ipc_window_create(self, **options: Any) -> dict[str, Any]:
        return self.windows.create(**options)

    def _ipc_window_close_label(self, label: str) -> bool:
        return self.windows.close(label)

    # ─── Multi-Window Label-Targeted IPC Handlers ───

    def _ipc_windows_set_title(self, label: str, title: str) -> bool:
        self.windows.set_title(label, title)
        return True

    def _ipc_windows_set_size(self, label: str, width: int | float, height: int | float) -> bool:
        self.windows.set_size(label, width, height)
        return True

    def _ipc_windows_set_position(self, label: str, x: int | float, y: int | float) -> bool:
        self.windows.set_position(label, x, y)
        return True

    def _ipc_windows_focus(self, label: str) -> bool:
        self.windows.focus(label)
        return True

    def _ipc_windows_minimize(self, label: str) -> bool:
        self.windows.minimize(label)
        return True

    def _ipc_windows_maximize(self, label: str) -> bool:
        self.windows.maximize(label)
        return True

    def _ipc_windows_set_fullscreen(self, label: str, enabled: bool) -> bool:
        self.windows.set_fullscreen(label, enabled)
        return True

    def _ipc_windows_show(self, label: str) -> bool:
        self.windows.show(label)
        return True

    def _ipc_windows_hide(self, label: str) -> bool:
        self.windows.hide(label)
        return True

    def _ipc_power_get_battery_info(self) -> dict[str, Any]:
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
        self.bridge.register_command(
            name,
            func,
        )

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

    def allowed_origins(self) -> list[str]:
        """Return normalized allowed origins for frontend IPC."""
        origins = list(self.config.security.allowed_origins)
        if not any(origin.startswith("forge://app") for origin in origins):
            origins.append("forge://app")
        if self._dev_server_url:
            origins.append(self._dev_server_url)

        deduped: list[str] = []
        for origin in origins:
            if origin and origin not in deduped:
                deduped.append(origin)
        return deduped

    def is_development_mode(self) -> bool:
        """Return whether this app should behave like a development runtime."""
        if self._debug or os.environ.get("FORGE_INSPECT") == "1":
            return True
        if self._dev_server_url:
            return True
        return self.config.is_development_mode()

    def devtools_enabled(self) -> bool:
        """Return whether devtools should be exposed for this runtime."""
        override = self.config.security.allow_devtools
        if override is not None:
            return bool(override)
        return self.is_development_mode()

    def content_security_policy(self) -> str:
        """Resolve the effective content security policy for the current runtime."""
        if self.config.security.csp:
            return self.config.security.csp
        if self.is_development_mode():
            return (
                "default-src 'self' forge: forge-asset: forge-memory: http://localhost:* http://127.0.0.1:*; "  # noqa: E501
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' forge: http://localhost:* http://127.0.0.1:*; "  # noqa: E501
                "style-src 'self' 'unsafe-inline' forge: http://localhost:* http://127.0.0.1:*; "
                "img-src 'self' data: blob: forge: forge-asset: forge-memory: http://localhost:* http://127.0.0.1:*; "  # noqa: E501
                "media-src 'self' data: blob: forge: forge-asset: forge-memory: http://localhost:* http://127.0.0.1:*; "  # noqa: E501
                "connect-src 'self' ws://localhost:* ws://127.0.0.1:* http://localhost:* http://127.0.0.1:* forge: forge-asset: forge-memory:;"  # noqa: E501
            )
        return (
            "default-src 'self' forge: forge-asset: forge-memory:; "
            "script-src 'self' 'unsafe-inline' forge:; "
            "style-src 'self' 'unsafe-inline' forge:; "
            "img-src 'self' data: blob: forge: forge-asset: forge-memory:; "
            "media-src 'self' data: blob: forge: forge-asset: forge-memory:; "
            "connect-src 'self' forge: forge-asset: forge-memory:;"
        )

    def is_origin_allowed(self, origin: str | None) -> bool:
        """Return whether a caller origin is allowed to use the IPC bridge.

        In strict_mode, only forge:// origins and explicitly listed origins pass.
        Without strict_mode, behavior is unchanged (forge://app auto-added).
        """
        if not origin:
            return True

        # forge:// protocol origins are always trusted (same-app webview)
        if origin.startswith("forge://"):
            return True

        allowed_list = self.allowed_origins()

        # Strict mode: if no explicit HTTP/HTTPS origins configured, block external
        if self.config.security.strict_mode:
            has_explicit_external = any(
                not a.startswith("forge://") for a in self.config.security.allowed_origins
            )
            if not has_explicit_external:
                return False

        parsed_origin = urlparse(origin)
        normalized_origin = (
            f"{parsed_origin.scheme}://{parsed_origin.netloc}"
            if parsed_origin.scheme in {"http", "https"} and parsed_origin.netloc
            else origin
        )

        for allowed in allowed_list:
            if allowed.startswith("forge://"):
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

    def command(  # noqa: F811  # re-exported from bridge, class scope is distinct
        self,
        func: Callable | None = None,
        name: str | None = None,
        capability: str | None = None,
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

            # Parse to extract the message ID for the JS callback
            def _handle_response(response_json: str) -> None:
                try:
                    logger.debug(f"IPC response: {response_json[:200]}")
                    response = json.loads(response_json)
                    msg_id = response.get("id")

                    if msg_id is not None:
                        js_call = f"window.__forge__._handleMessage({response_json})"
                        logger.debug(f"Sending to JS: {js_call[:200]}")
                        proxy.evaluate_script("main", js_call)
                except Exception as e:
                    logger.error(f"Failed to process or send IPC message response: {e}")
                    import traceback

                    traceback.print_exc()

            # Schedule full pipeline execution in background
            self.bridge.invoke_command_threaded(message, _handle_response)

        except Exception as e:
            logger.error(f"Failed to schedule IPC message: {e}")

    def _sync_native_menu(self, items: list[dict[str, Any]] | None = None) -> None:
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
        if os.environ.get("FORGE_INSPECT") == "1":
            try:
                self._proxy.evaluate_script("main", "window.__FORGE_INSPECT__ = true;")
                if self.devtools_enabled():
                    self._proxy.open_devtools()
            except Exception:
                pass
        self.window._apply_native_event("ready", None)
        self.windows.sync_main_window()
        self.runtime._apply_native_event("ready", None)
        self._sync_native_menu()
        if self._dev_server_url:
            self.runtime._update_state(url=self._dev_server_url)
            try:
                proxy.load_url("main", self._dev_server_url)
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

        label = self.windows._apply_native_event(
            event, payload if isinstance(payload, dict) else None
        )
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
        import os

        if os.environ.get("FORGE_INSPECT") == "1":
            try:
                json.dumps(payload)
            except Exception:
                str(payload)

        # Python-side listeners
        self.events.emit(event, payload)

        # JS-side listeners — use the WindowProxy (not NativeWindow)
        if self._proxy is not None:
            data = json.dumps({"type": "event", "event": event, "payload": payload})
            self._proxy.evaluate_script("main", f"window.__forge__._handleMessage({data})")

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

    def quit(self) -> None:
        """
        Force quit the application immediately.
        Bypasses close_to_tray and actually asks the Rust event loop to terminate.
        """
        if self._proxy is not None:
            self._proxy.close()

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
        self._debug = bool(debug)
        if debug:
            logging.basicConfig(level=logging.DEBUG)

        # Resolve frontend path
        base_dir = self.config.get_base_dir()
        frontend_path = base_dir / self.config.dev.frontend_dir

        if not frontend_path.exists():
            logger.error(f"Frontend directory not found: {frontend_path}")
            return

        # Copy forge.js into the frontend directory
        forge_js_src = os.path.join(os.path.dirname(__file__), "js", "forge.js")
        forge_js_dest = frontend_path / "forge.js"
        if os.path.exists(forge_js_src):
            shutil.copy2(forge_js_src, str(forge_js_dest))

        os.environ["FORGE_RUNTIME_DEVTOOLS"] = "1" if self.devtools_enabled() else "0"
        os.environ["FORGE_RUNTIME_CSP"] = self.content_security_policy()

        # Import the Rust extension
        from .forge_core import NativeWindow  # type: ignore[import-untyped]

        # Create the native window with full config passthrough
        wc = self.config.window
        # Get persistent state for main window
        state = self.window_state.get_state("main")
        w_width = float(state.get("width", wc.width))
        w_height = float(state.get("height", wc.height))
        w_x = state.get("x", None)
        w_y = state.get("y", None)
        if w_x is not None:
            w_x = float(w_x)
        if w_y is not None:
            w_y = float(w_y)

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
            wc.close_to_tray,
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
        except Exception as startup_error:
            logger.exception("Fatal unhandled exception in Forge application")
            try:
                from .forge_core import DialogManager

                DialogManager().show_message(
                    "Fatal Application Error",
                    f"The application encountered a critical error and must close.\n\n{startup_error}",  # noqa: E501
                    "error",
                )
            except Exception:
                pass
            raise
        finally:
            self._crash_store.uninstall()
            # Fire on_close hooks
            for hook in self._on_close_hooks:
                try:
                    hook()
                except Exception as e:
                    logger.error(f"on_close hook failed: {e}")

            # Clean up background tasks and channels
            self.tasks.cancel_all()
            self.channels.close_all()
            if hasattr(self, "ws"):
                self.ws.close_all()

            # Clean up the thread pool
            self.bridge.shutdown()
