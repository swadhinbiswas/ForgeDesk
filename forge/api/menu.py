"""Forge application menu API groundwork."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from forge.bridge import command


class MenuAPI:
    """Framework-owned application menu model and event surface."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._items: list[dict[str, Any]] = []

    @command("menu_set")
    def set(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace the active application menu tree."""
        normalized = self._normalize_items(items)
        self._items = normalized
        self._emit_menu_changed()
        return self.get()

    @command("menu_get")
    def get(self) -> list[dict[str, Any]]:
        """Return the active application menu snapshot."""
        return deepcopy(self._items)

    @command("menu_clear")
    def clear(self) -> bool:
        """Remove all configured menu items."""
        self._items = []
        self._emit_menu_changed()
        return True

    @command("menu_enable")
    def enable(self, item_id: str) -> dict[str, Any]:
        """Enable a menu item by id."""
        item = self._find_item(item_id)
        item["enabled"] = True
        self._emit_menu_changed()
        return deepcopy(item)

    @command("menu_disable")
    def disable(self, item_id: str) -> dict[str, Any]:
        """Disable a menu item by id."""
        item = self._find_item(item_id)
        item["enabled"] = False
        self._emit_menu_changed()
        return deepcopy(item)

    @command("menu_check")
    def check(self, item_id: str, checked: bool = True) -> dict[str, Any]:
        """Set the checked state for a checkable menu item."""
        item = self._find_item(item_id)
        item["checked"] = bool(checked)
        self._emit_menu_changed()
        return deepcopy(item)

    @command("menu_uncheck")
    def uncheck(self, item_id: str) -> dict[str, Any]:
        """Unset the checked state for a menu item."""
        return self.check(item_id, False)

    @command("menu_trigger")
    def trigger(self, item_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Trigger a menu item action and emit a framework event."""
        item = self._find_item(item_id)
        event_payload = {
            "id": item_id,
            "label": item.get("label"),
            "role": item.get("role"),
            "payload": payload,
        }
        self._app.emit("menu:select", event_payload)
        return event_payload

    def apply_native_selection(self, item_id: str, checked: bool | None = None) -> dict[str, Any]:
        """Synchronize native menu state changes into the framework-owned model."""
        item = self._find_item(item_id)
        changed = False
        if checked is not None and item.get("checkable"):
            checked_value = bool(checked)
            if item.get("checked") != checked_value:
                item["checked"] = checked_value
                changed = True
        if changed:
            self._emit_menu_changed()
        return deepcopy(item)

    def _emit_menu_changed(self) -> None:
        snapshot = self.get()
        self._app._sync_native_menu(snapshot)
        self._app.emit("menu:changed", snapshot)

    def _normalize_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            raise TypeError("Menu items must be a list")

        seen_ids: set[str] = set()

        def normalize(item_list: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
            normalized_items: list[dict[str, Any]] = []
            for index, item in enumerate(item_list):
                if not isinstance(item, dict):
                    raise TypeError(f"Menu item at {path}[{index}] must be an object")

                normalized = deepcopy(item)
                item_id = normalized.get("id")
                submenu = normalized.get("submenu")
                item_type = normalized.get("type", "item")

                if item_type not in {"item", "separator", "checkbox"}:
                    raise ValueError(
                        f"Menu item type at {path}[{index}] must be one of: item, separator, checkbox"
                    )

                normalized["type"] = item_type

                if submenu is not None and not isinstance(submenu, list):
                    raise TypeError(f"Menu item submenu at {path}[{index}] must be a list")

                if item_type == "separator":
                    normalized["enabled"] = False
                    normalized["checked"] = False
                    normalized["checkable"] = False
                    normalized.pop("submenu", None)
                    normalized_items.append(normalized)
                    continue

                if item_id is not None:
                    if not isinstance(item_id, str) or not item_id:
                        raise ValueError(f"Menu item id at {path}[{index}] must be a non-empty string")
                    if item_id in seen_ids:
                        raise ValueError(f"Duplicate menu item id: {item_id}")
                    seen_ids.add(item_id)

                if "label" in normalized and not isinstance(normalized["label"], str):
                    raise TypeError(f"Menu item label at {path}[{index}] must be a string")

                checkable = bool(normalized.get("checkable", item_type == "checkbox" or "checked" in normalized))
                normalized["checkable"] = checkable
                normalized["enabled"] = bool(normalized.get("enabled", True))
                normalized["checked"] = bool(normalized.get("checked", False)) if checkable else False
                if submenu is not None:
                    normalized["submenu"] = normalize(submenu, f"{path}[{index}].submenu")
                normalized_items.append(normalized)
            return normalized_items

        return normalize(items, "menu")

    def _find_item(self, item_id: str) -> dict[str, Any]:
        def visit(items: list[dict[str, Any]]) -> dict[str, Any] | None:
            for item in items:
                if item.get("id") == item_id:
                    return item
                submenu = item.get("submenu")
                if isinstance(submenu, list):
                    found = visit(submenu)
                    if found is not None:
                        return found
            return None

        result = visit(self._items)
        if result is None:
            raise ValueError(f"Unknown menu item id: {item_id}")
        return result