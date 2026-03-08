"""Forge system tray API."""

from __future__ import annotations

import logging
import importlib
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from forge.bridge import command

logger = logging.getLogger(__name__)


class TrayAPI:
    """Framework-owned system tray model and event surface.

    Provides methods for creating and managing a system tray icon
    with context menu. Uses `pystray` + `pillow` when available and
    reports structured state even when no tray backend is installed.

    Platform support:
        - Windows: Full support via pystray
        - macOS: Status bar item via pystray
        - Linux: Depends on desktop environment (AppIndicator)
    """

    __forge_capability__ = "system_tray"

    def __init__(self, app: Any) -> None:
        """Initialize the Tray API."""
        self._app = app
        self._icon: Any = None
        self._icon_path: Optional[str] = None
        self._menu_items: List[Dict[str, Any]] = []
        self._visible = False
        self._lock = threading.Lock()
        self._on_action: Optional[Callable[[str, dict[str, Any] | None], None]] = None
        self._backend_name: str = "none"
        self._backend_available = False

    def set_action_handler(self, handler: Callable[[str, dict[str, Any] | None], None]) -> None:
        """
        Set the callback for tray menu actions.

        Args:
            handler: Function called with the action name when a menu item is clicked.
        """
        self._on_action = handler

    @command("tray_set_icon")
    def set_icon(self, icon_path: str) -> str:
        """
        Set the system tray icon.

        Args:
            icon_path: Path to the icon image file (PNG recommended).

        Raises:
            FileNotFoundError: If the icon file doesn't exist.
        """
        path = Path(icon_path)
        if not path.exists():
            raise FileNotFoundError(f"Icon not found: {icon_path}")

        self._icon_path = str(path)
        logger.debug(f"Tray icon set: {icon_path}")

        if self._visible:
            self._update_tray()
        return self._icon_path

    @command("tray_set_menu")
    def set_menu(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Set the tray context menu items.

        Args:
            items: List of menu item definitions. Each item can have:
                   - label: str - Menu item text
                   - action: str - Action name (emitted as event)
                   - separator: bool - If True, creates a separator
                   - enabled: bool - Whether the item is enabled
        """
        self._menu_items = self._normalize_items(items)
        logger.debug(f"Tray menu set with {len(items)} items")

        if self._visible:
            self._update_tray()
        return list(self._menu_items)

    @command("tray_show")
    def show(self) -> bool:
        """Show the system tray icon."""
        if self._visible:
            return True

        self._create_tray()
        if self._backend_available:
            self._visible = True
            logger.info("System tray icon shown")
        else:
            logger.info("System tray requested but no supported tray backend is available")
        return self._visible

    @command("tray_hide")
    def hide(self) -> bool:
        """Hide the system tray icon."""
        if not self._visible:
            return False

        self._destroy_tray()
        self._visible = False
        logger.info("System tray icon hidden")
        return True

    @command("tray_is_visible")
    def is_visible(self) -> bool:
        """Check if the tray icon is currently visible."""
        return self._visible

    @command("tray_state")
    def state(self) -> Dict[str, Any]:
        """Return a structured tray state snapshot."""
        return {
            "visible": self._visible,
            "icon_path": self._icon_path,
            "menu": list(self._menu_items),
            "backend": self._backend_name,
            "backend_available": self._backend_available,
        }

    @command("tray_trigger")
    def trigger(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Trigger a tray action and emit the framework event surface."""
        event_payload = {
            "action": action,
            "payload": payload,
        }
        if self._on_action:
            self._on_action(action, payload)
        else:
            self._app.emit("tray:select", event_payload)
        return event_payload

    def _normalize_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            raise TypeError("Tray menu items must be a list")

        normalized: List[Dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError(f"Tray item at index {index} must be an object")
            if item.get("separator"):
                normalized.append({"separator": True})
                continue

            label = item.get("label")
            action = item.get("action")
            if not isinstance(label, str) or not label:
                raise ValueError(f"Tray item label at index {index} must be a non-empty string")
            if not isinstance(action, str) or not action:
                raise ValueError(f"Tray item action at index {index} must be a non-empty string")

            normalized.append(
                {
                    "label": label,
                    "action": action,
                    "enabled": bool(item.get("enabled", True)),
                    "checked": bool(item.get("checked", False)),
                    "checkable": bool(item.get("checkable", "checked" in item)),
                    "separator": False,
                }
            )
        return normalized

    def _emit_action(self, action: str, payload: dict[str, Any] | None = None) -> None:
        event_payload = {"action": action, "payload": payload}
        if self._on_action is not None:
            self._on_action(action, payload)
        else:
            self._app.emit("tray:select", event_payload)

    def _load_backend(self) -> tuple[Any, Any] | None:
        try:
            pystray = importlib.import_module("pystray")
            pil_image = importlib.import_module("PIL.Image")

            self._backend_name = "pystray"
            self._backend_available = True
            return pystray, pil_image
        except ImportError:
            self._backend_name = "none"
            self._backend_available = False
            return None

    def _create_tray(self) -> None:
        """
        Create the system tray icon using pystray if available.
        """
        backend = self._load_backend()
        if backend is None:
            logger.info(
                "pystray not installed -- system tray disabled. "
                "Install with: pip install pystray pillow"
            )
            return

        pystray, Image = backend

        try:
            if not self._icon_path:
                logger.warning("No tray icon set")
                return

            image = Image.open(self._icon_path)

            # Build menu
            menu_items = []
            for item in self._menu_items:
                if item.get("separator"):
                    menu_items.append(pystray.Menu.SEPARATOR)
                else:
                    label = item.get("label", "")
                    action = item.get("action", "")
                    enabled = item.get("enabled", True)
                    checked = item.get("checked", False)
                    checkable = item.get("checkable", False)

                    def make_callback(act: str) -> Callable:
                        def callback(icon: Any, menu_item: Any) -> None:
                            payload = {
                                "checked": bool(getattr(menu_item, "checked", False)) if checkable else None,
                            }
                            self._emit_action(act, payload)

                        return callback

                    menu_items.append(
                        pystray.MenuItem(
                            label,
                            make_callback(action),
                            enabled=enabled,
                            checked=(lambda item=item: bool(item.get("checked", False))) if checkable else None,
                        )
                    )

            menu = pystray.Menu(*menu_items) if menu_items else None
            self._icon = pystray.Icon("forge", image, menu=menu)

            # Run in a background thread
            tray_thread = threading.Thread(target=self._icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            self._backend_available = False
            logger.error(f"Failed to create tray icon: {e}")

    def _update_tray(self) -> None:
        """Update the existing tray icon and menu."""
        if not self._visible:
            return
        # Recreate for simplicity
        self._destroy_tray()
        self._create_tray()

    def _destroy_tray(self) -> None:
        """Destroy the system tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
