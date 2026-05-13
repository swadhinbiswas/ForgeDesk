"""
Forge Dialog API (v2.0).

Provides native OS dialog functionality for Forge applications.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from forge.bridge import command
from forge.forge_core import DialogManager  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class DialogAPI:
    """
    Native Dialog OS API for Forge applications.
    """

    __forge_capability__ = "dialog"

    def __init__(self) -> None:

        self._manager = DialogManager()

    @command("dialog_open")
    def open_file(
        self,
        title: str | None = None,
        directory: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        multiple: bool = False,
    ) -> dict[str, Any]:
        """Show system native open file dialog."""
        filters_json = json.dumps(filters) if filters else None
        try:
            res = self._manager.open_file(title, directory, filters_json, multiple)
            return {"paths": res, "canceled": res is None}
        except Exception as e:
            logger.error(f"Dialog error: {e}")
            return {"error": str(e), "canceled": True}

    @command("dialog_save")
    def save_file(
        self,
        title: str | None = None,
        directory: str | None = None,
        file_name: str | None = None,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Show system native save file dialog."""
        filters_json = json.dumps(filters) if filters else None
        try:
            res = self._manager.save_file(title, directory, file_name, filters_json)
            return {"path": res, "canceled": res is None}
        except Exception as e:
            logger.error(f"Dialog error: {e}")
            return {"error": str(e), "canceled": True}

    @command("dialog_folder")
    def select_folder(
        self,
        title: str | None = None,
        directory: str | None = None,
    ) -> dict[str, Any]:
        """Show system native folder selection dialog."""
        try:
            res = self._manager.select_folder(title, directory)
            return {"path": res, "canceled": res is None}
        except Exception as e:
            logger.error(f"Dialog error: {e}")
            return {"error": str(e), "canceled": True}
