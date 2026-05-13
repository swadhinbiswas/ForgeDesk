"""Local AI Inference utilizing strictly offline LLaMA.cpp models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinLocalLLMAPI:
    """Plugin to automatically load and stream offline AI model outputs."""

    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app
        self._llm: Any = None
        self._model_path: str | None = None

    def _get_llama(self) -> Any:
        try:
            from llama_cpp import Llama  # type: ignore[import-not-found]

            return Llama
        except ImportError as e:
            raise RuntimeError("pip install llama-cpp-python to use local AI inference") from e

    def llm_load(self, model_path: str, n_ctx: int = 2048, n_gpu_layers: int = 0) -> dict[str, Any]:
        """Load a .gguf model from the local filesystem."""
        try:
            llama_cls = self._get_llama()
            path = Path(model_path).expanduser().resolve()
            if not path.exists():
                return {"ok": False, "error": f"Model not found at {path}"}

            self._llm = llama_cls(
                model_path=str(path), n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False
            )
            self._model_path = str(path)
            return {"ok": True, "info": f"Loaded model {path.name}"}
        except Exception as exc:
            logger.exception("llm_load")
            return {"ok": False, "error": str(exc)}

    def llm_chat(
        self, messages: list[dict[str, str]], max_tokens: int = 512, temperature: float = 0.7
    ) -> dict[str, Any]:
        """Run a standard localized chat completion without networking."""
        if not self._llm:
            return {"ok": False, "error": "No model loaded. Call llm_load first."}
        try:
            response = self._llm.create_chat_completion(
                messages=messages, max_tokens=max_tokens, temperature=temperature
            )
            return {"ok": True, "response": response}
        except Exception as exc:
            logger.exception("llm_chat")
            return {"ok": False, "error": str(exc)}

    def llm_chat_stream(
        self,
        messages: list[dict[str, str]],
        channel_id: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Stream localized chat completion via IPC channels for responsive UIs."""
        if not self._llm:
            return {"ok": False, "error": "No model loaded. Call llm_load first."}

        # We start a streaming task in the background using Forge's background task API
        def _stream_task() -> None:
            try:
                stream = self._llm.create_chat_completion(
                    messages=messages, max_tokens=max_tokens, temperature=temperature, stream=True
                )
                for chunk in stream:
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        # Push updates over our high speed IPC event stream channel
                        self._app.events.emit(
                            channel_id, {"type": "chunk", "text": delta["content"]}
                        )
                self._app.events.emit(channel_id, {"type": "done"})
            except Exception as exc:
                self._app.events.emit(channel_id, {"type": "error", "error": str(exc)})

        try:
            self._app.tasks.spawn(_stream_task)
            return {"ok": True, "stream_channel": channel_id}
        except Exception as exc:
            logger.exception("llm_chat_stream task spawn")
            return {"ok": False, "error": str(exc)}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinLocalLLMAPI(app))
