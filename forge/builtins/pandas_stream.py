"""Pandas DataFrame binary streaming extension for zero-copy memory transfers."""

from __future__ import annotations

import io
import logging
import uuid
from typing import Any

from forge import memory

logger = logging.getLogger(__name__)

_CAP = "forge_extensions"


class BuiltinPandasAPI:
    """Plugin to ferry Pandas DataFrames securely to the frontend via forge-memory://."""

    __forge_capability__ = _CAP

    def __init__(self, app: Any) -> None:
        self._app = app

    def dataframe_to_memory(self, df: Any, format: str = "parquet") -> dict[str, Any]:
        """
        Converts a Pandas DataFrame to a raw byte buffer and registers it in forge.memory.
        The frontend can fetch 'forge-memory://<buffer_id>' to render high-performance data grids.
        """
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError:
            return {"ok": False, "error": "pip install pandas to use this capability"}

        if not isinstance(df, pd.DataFrame):
            return {"ok": False, "error": "Provided object is not a Pandas DataFrame."}

        buffer_id = f"df_{uuid.uuid4().hex}"
        buf = io.BytesIO()

        try:
            if format == "parquet":
                df.to_parquet(buf, engine="pyarrow")
            elif format == "csv":
                df.to_csv(buf, index=False)
            elif format == "feather":
                df.to_feather(buf)
            else:
                return {"ok": False, "error": f"Unsupported format: {format}"}

            # Inject the raw bytes into the high-speed Rust-accessible memory registry
            memory.buffers[buffer_id] = buf.getvalue()

            return {
                "ok": True,
                "buffer_id": buffer_id,
                "url": f"forge-memory://{buffer_id}",
                "format": format,
                "rows": len(df),
                "columns": list(df.columns),
            }
        except Exception as exc:
            logger.exception("dataframe_to_memory processing failed")
            return {"ok": False, "error": str(exc)}

    def free_memory_buffer(self, buffer_id: str) -> bool:
        """Release the memory buffer when the frontend no longer needs it."""
        return memory.buffers.pop(buffer_id, None) is not None


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinPandasAPI(app))
