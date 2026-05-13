"""OAuth2 PKCE helpers and JWT payload inspection (built-in extension)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from typing import Any

import requests

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"

# state -> { verifier: str, created: float }
_pkce_store: dict[str, dict[str, Any]] = {}


class BuiltinAuthAPI:
    __forge_capability__ = _CAP

    def oauth_pkce_start(self, redirect_uri: str) -> dict[str, Any]:
        """Begin PKCE: returns ``authorization_url`` query params to append to provider authorize URL."""  # noqa: E501
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(
            b"="
        )
        state = secrets.token_urlsafe(32)
        _pkce_store[state] = {"verifier": verifier, "redirect_uri": redirect_uri}
        return {
            "state": state,
            "code_verifier": verifier,
            "code_challenge": challenge.decode("ascii"),
            "code_challenge_method": "S256",
        }

    def oauth_pkce_exchange(
        self,
        state: str,
        token_url: str,
        client_id: str,
        code: str,
        redirect_uri: str,
        client_secret: str | None = None,
    ) -> dict[str, Any]:
        """Exchange authorization ``code`` for tokens (POST to ``token_url``)."""
        rec = _pkce_store.pop(state, None)
        if not rec:
            return {"ok": False, "error": "invalid or expired state"}
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": rec["verifier"],
        }
        if client_secret:
            data["client_secret"] = client_secret
        try:
            r = requests.post(token_url, data=data, timeout=60)
            r.raise_for_status()
            return {
                "ok": True,
                "data": r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else {"text": r.text},
            }
        except Exception as exc:
            logger.exception("oauth_pkce_exchange")
            return {"ok": False, "error": str(exc)}

    def jwt_decode_payload(self, token: str) -> dict[str, Any]:
        """Return JWT payload dict without signature verification (introspection only)."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {"ok": False, "error": "not a JWT"}
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            raw = base64.urlsafe_b64decode(payload.encode())
            return {"ok": True, "payload": json.loads(raw.decode())}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinAuthAPI())
