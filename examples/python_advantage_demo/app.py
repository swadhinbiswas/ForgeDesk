import logging

from forge import ForgeApp, command

logger = logging.getLogger(__name__)

app = ForgeApp()


@command()
def generate_market_data(rows: int) -> dict:
    """Generate fake market data locally and return buffer ID"""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return {"ok": False, "error": "install pandas to test this"}

    # Generate large dataframe
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="S"),
            "symbol": np.random.choice(["AAPL", "GOOG", "MSFT", "TSLA"], rows),
            "price": np.random.normal(150, 10, rows),
            "volume": np.random.randint(100, 10000, rows),
        }
    )

    # We call the plugin directly from the app
    plugin = app.plugins.get_plugin("pandas_stream")
    if not plugin:
        return {"ok": False, "error": "pandas plugin not loaded"}

    return plugin["instance"].dataframe_to_memory(df, format="csv")


@command()
def chat_with_llama(prompt: str, channel_id: str) -> dict:
    """Calls the local LLM plugin to stream back tokens"""
    plugin = app.plugins.get_plugin("llm_local")
    if not plugin:
        return {"ok": False, "error": "llm plugin not loaded"}

    llm = plugin["instance"]

    if not llm._llm:
        # User needs to load a mock model or real GGUF first
        return {"ok": False, "error": "No model loaded yet!"}

    messages = [{"role": "user", "content": prompt}]
    return llm.llm_chat_stream(messages, channel_id=channel_id)


@command()
def load_llama_model(path: str) -> dict:
    plugin = app.plugins.get_plugin("llm_local")
    if not plugin:
        return {"ok": False, "error": "llm plugin not loaded"}

    return plugin["instance"].llm_load(path, n_ctx=512)


@command()
def record_mouse() -> dict:
    plugin = app.plugins.get_plugin("automation")
    if not plugin:
        return {"ok": False, "error": "automation plugin not loaded"}

    auto = plugin["instance"]
    # Provide a simple demo: move mouse in a square
    auto.mouse_move(100, 100, duration=0.2)
    auto.mouse_move(200, 100, duration=0.2)
    auto.mouse_move(200, 200, duration=0.2)
    auto.mouse_move(100, 200, duration=0.2)
    return {"ok": True}


if __name__ == "__main__":
    app.run()
