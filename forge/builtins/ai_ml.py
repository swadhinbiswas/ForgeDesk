"""Cloud AI HTTP bridge and optional local inference stubs."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinAIMLAPI:
    __forge_capability__ = _CAP

    def openai_chat(
        self,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Call OpenAI-compatible ``/chat/completions`` (pass API key from secure storage)."""
        url = base_url.rstrip("/") + "/chat/completions"
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages},
                timeout=timeout,
            )
            if r.headers.get("content-type", "").startswith("application/json"):
                return {"ok": r.ok, "status": r.status_code, "data": r.json()}
            return {"ok": r.ok, "status": r.status_code, "text": r.text[:500_000]}
        except Exception as exc:
            logger.exception("openai_chat")
            return {"ok": False, "error": str(exc)}

    def onnx_runtime_available(self) -> dict[str, Any]:
        """Report whether ``onnxruntime`` can be imported."""
        try:
            import onnxruntime as ort  # type: ignore[import-not-found]

            return {"ok": True, "version": getattr(ort, "__version__", "unknown")}
        except ImportError:
            return {"ok": False, "error": "pip install onnxruntime for local inference"}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinAIMLAPI())
