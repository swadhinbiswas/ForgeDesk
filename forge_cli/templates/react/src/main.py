"""
{{PROJECT_NAME}} - Python Backend

This is the main entry point for your Forge desktop application.
Define Python commands here and call them from your frontend via IPC.

Quick start:
    ./forge dev        # Start development server
    ./forge build      # Build production binary
"""

from forge import ForgeApp

app = ForgeApp()


@app.command
def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}! Welcome to {{PROJECT_NAME}} 🚀"


@app.command
def get_system_info() -> dict:
    """Get system information."""
    import platform

    return {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "platform": platform.machine(),
    }


@app.command
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


if __name__ == "__main__":
    app.run(debug=True)
