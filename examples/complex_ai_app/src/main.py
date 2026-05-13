"""
complex_ai_app - Flagship AI and Data Science Example

Demonstrates:
- Local LLM Integration (`forge.builtins.llm_local`)
- High-Performance Pandas Data Grids via Zero-Copy IPC (`forge-memory://`)
- Window State Management

Quick start:
    ./forge dev        # Start development server
"""

from typing import Any

import numpy as np
import pandas as pd

from forge import ForgeApp

app = ForgeApp()

# --- Pandas Zero-Copy Data Grid Example ---


@app.command
def generate_dataset(rows: int = 100_000) -> dict[str, Any]:
    """Generates a massive Pandas DataFrame and streams it to the frontend via Zero-Copy memory IPC."""  # noqa: E501
    # Generate some fake financial or sensor data
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="s"),
            "sensor_value": np.random.randn(rows),
            "status": np.random.choice(["OK", "WARNING", "ERROR"], rows),
            "category": np.random.choice(["A", "B", "C"], rows),
        }
    )

    # Use the Pandas Plugin to convert the DataFrame to a memory pointer
    return app.pandas_stream.dataframe_to_memory(df, format="csv")


# --- Local LLM App Backend ---
# The actual LLM operations are handled natively by the `forge.builtins.llm_local` plugin
# via the `llm_load`, `llm_chat`, and `llm_chat_stream` commands.
# We just need to make sure the plugins are enabled in forge.toml.

if __name__ == "__main__":
    app.run(debug=True)
