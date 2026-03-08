"""Forge deep link / custom protocol handler API."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from forge.bridge import command


class DeepLinkAPI:
    """Framework-owned deep link state and dispatch surface."""

    def __init__(self, app: Any, schemes: list[str]) -> None:
        self._app = app
        self._schemes = list(schemes)
        self._history: list[dict[str, Any]] = []

    @command("deep_link_protocols")
    def protocols(self) -> dict[str, Any]:
        """Return configured custom protocol schemes."""
        return {
            "schemes": list(self._schemes),
            "configured": bool(self._schemes),
        }

    @command("deep_link_state")
    def state(self) -> dict[str, Any]:
        """Return deep link history and most recent URL."""
        return {
            "schemes": list(self._schemes),
            "last_url": self._history[-1]["url"] if self._history else None,
            "history": list(self._history),
        }

    @command("deep_link_open")
    def open(self, url: str) -> dict[str, Any]:
        """Validate and dispatch a deep link into the running application."""
        parsed = urlparse(url)
        if not parsed.scheme:
            raise ValueError("Deep link URL must include a scheme")
        if self._schemes and parsed.scheme not in self._schemes:
            raise ValueError(
                f"Deep link scheme {parsed.scheme!r} is not configured; expected one of {self._schemes!r}"
            )

        payload = {
            "url": url,
            "scheme": parsed.scheme,
            "host": parsed.netloc or None,
            "path": parsed.path,
            "query": parsed.query or None,
            "fragment": parsed.fragment or None,
        }
        self._history.append(payload)
        self._history = self._history[-50:]
        self._app.emit("deep-link", payload)
        self._app.emit(f"deep-link:{parsed.scheme}", payload)
        return payload
