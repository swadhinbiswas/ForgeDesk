"""Cryptographic helpers (Fernet, hashing) using ``cryptography`` (built-in extension)."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinCryptoAPI:
    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def _under_base(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs).expanduser()
        if not p.is_absolute():
            p = self._app.config.get_base_dir() / p
        return p.resolve()

    def hash_sha256_hex(self, text: str) -> str:
        """SHA-256 hex digest of a UTF-8 string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def hash_sha256_file(self, path: str) -> dict[str, Any]:
        """Stream hash of a file under the app project directory."""
        target = self._under_base(path)
        if not target.is_file():
            return {"ok": False, "error": f"not a file: {target}"}
        try:
            h = hashlib.sha256()
            with target.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return {"ok": True, "hex": h.hexdigest()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def fernet_generate_key(self) -> dict[str, str]:
        """Return a URL-safe base64 key suitable for :meth:`fernet_encrypt`."""
        return {"key": Fernet.generate_key().decode("ascii")}

    def fernet_encrypt(self, key_b64: str, plaintext: str) -> dict[str, Any]:
        """Encrypt UTF-8 text with Fernet."""
        try:
            f = Fernet(key_b64.encode("ascii"))
            tok = f.encrypt(plaintext.encode("utf-8"))
            return {"ok": True, "token": tok.decode("ascii")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def fernet_decrypt(self, key_b64: str, token: str) -> dict[str, Any]:
        """Decrypt a token produced by :meth:`fernet_encrypt`."""
        try:
            f = Fernet(key_b64.encode("ascii"))
            pt = f.decrypt(token.encode("ascii"))
            return {"ok": True, "plaintext": pt.decode("utf-8")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def pbkdf2_derive_key(
        self,
        password: str,
        salt_b64: str,
        iterations: int = 480_000,
        length: int = 32,
    ) -> dict[str, Any]:
        """Derive a key bytes (hex) using PBKDF2-HMAC-SHA256."""
        try:
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii") + b"==")
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=length,
                salt=salt,
                iterations=iterations,
            )
            key = kdf.derive(password.encode("utf-8"))
            return {"ok": True, "key_hex": key.hex()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def random_bytes_hex(self, num_bytes: int = 32) -> dict[str, str]:
        """Cryptographically random bytes as hex (default 32 bytes)."""
        n = max(1, min(num_bytes, 512))
        return {"hex": secrets.token_hex(n)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinCryptoAPI(app))
