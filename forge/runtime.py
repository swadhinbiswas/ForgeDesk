"""
Runtime Introspection APIs for Forge Framework.

Splits the RuntimeAPI from the main app.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .bridge import PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS

if TYPE_CHECKING:
    from .app import ForgeApp


class RuntimeAPI:
    """Diagnostics and runtime-introspection surface for Forge applications."""

    def __init__(self, app: ForgeApp) -> None:
        self._app = app
        self._state: dict[str, Any] = {
            "url": "forge://app/index.html",
            "devtools_open": False,
        }

    def _require_proxy(self) -> Any:
        if self._app._proxy is None:
            raise RuntimeError("The native runtime is not ready yet.")
        return self._app._proxy

    def _update_state(self, **updates: Any) -> None:
        self._state.update(updates)

    def _apply_native_event(self, event: str, payload: dict[str, Any] | None) -> None:
        payload = payload or {}
        if event == "navigated":
            url = payload.get("url")
            if url:
                self._update_state(url=url)
        elif event == "devtools":
            self._update_state(devtools_open=bool(payload.get("open")))

    def state(self) -> dict[str, Any]:
        """Return cached runtime state for navigation and devtools controls."""
        return dict(self._state)

    def navigate(self, url: str) -> None:
        """Navigate the native webview to a new URL."""
        self._update_state(url=url)
        self._require_proxy().load_url("main", url)
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
        if not self._app.devtools_enabled():
            raise PermissionError("Devtools are disabled for this runtime profile.")
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
        if not self._app.devtools_enabled():
            raise PermissionError("Devtools are disabled for this runtime profile.")
        if self._state.get("devtools_open"):
            self.close_devtools()
        else:
            self.open_devtools()
        return bool(self._state.get("devtools_open"))

    def logs(self, limit: int | None = 100) -> list[dict[str, Any]]:
        """Return recent structured runtime log entries."""
        return self._app._runtime_logs.snapshot(limit)

    def export_support_bundle(self, destination: str | Path | None = None) -> str:
        """Export a minimal support bundle zip for diagnostics collection."""
        bundle_path = self._app._support_bundle.export(destination)
        self._app._log_runtime_event("runtime_export_support_bundle", path=bundle_path)
        return bundle_path

    def protocol(self) -> dict[str, Any]:
        """Return protocol compatibility information."""
        return {
            "current": PROTOCOL_VERSION,
            "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
        }

    def config_snapshot(self) -> dict[str, Any]:
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
                "tasks": config.permissions.tasks,
                "clipboard": config.permissions.clipboard,
                "dialogs": config.permissions.dialogs,
                "notifications": config.permissions.notifications,
                "system_tray": config.permissions.system_tray,
                "updater": config.permissions.updater,
                "screen": config.permissions.screen,
                "lifecycle": config.permissions.lifecycle,
                "deep_link": config.permissions.deep_link,
                "os_integration": config.permissions.os_integration,
                "autostart": config.permissions.autostart,
                "power": config.permissions.power,
                "printing": config.permissions.printing,
                "window_state": config.permissions.window_state,
                "drag_drop": config.permissions.drag_drop,
            },
            "security": {
                "allowed_commands": list(config.security.allowed_commands),
                "denied_commands": list(config.security.denied_commands),
                "allow_devtools": config.security.allow_devtools,
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

    def last_crash(self) -> dict[str, Any] | None:
        """Return the latest captured crash snapshot, if any."""
        return self._app._crash_store.snapshot()

    def commands(self) -> list[dict[str, Any]]:
        """Return the registered command manifest."""
        return self._app.bridge.get_command_registry()

    def health(self) -> dict[str, Any]:
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

    def diagnostics(self, include_logs: bool = True, log_limit: int | None = 100) -> dict[str, Any]:
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
                "tasks": bool(config.permissions.tasks),
                "clipboard": bool(config.permissions.clipboard),
                "dialogs": bool(config.permissions.dialogs),
                "notifications": bool(config.permissions.notifications),
                "system_tray": bool(config.permissions.system_tray),
                "updater": bool(config.permissions.updater),
                "screen": bool(config.permissions.screen),
                "lifecycle": bool(config.permissions.lifecycle),
                "deep_link": bool(config.permissions.deep_link),
                "os_integration": bool(config.permissions.os_integration),
                "autostart": bool(config.permissions.autostart),
                "power": bool(config.permissions.power),
                "printing": bool(config.permissions.printing),
                "window_state": bool(config.permissions.window_state),
                "drag_drop": bool(config.permissions.drag_drop),
            },
            "security": {
                "allowed_commands": list(config.security.allowed_commands),
                "denied_commands": list(config.security.denied_commands),
                "allow_devtools": config.security.allow_devtools,
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
