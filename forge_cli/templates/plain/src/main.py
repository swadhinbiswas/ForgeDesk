"""
{{PROJECT_NAME}} - Python Backend

This is the main entry point for your Forge application.
Define your Python commands here and expose them to the frontend.
"""

from forge import ForgeApp

# Create the app instance
app = ForgeApp()


@app.command
def greet(name: str) -> str:
    """
    Greet a user by name.

    Args:
        name: The name to greet.

    Returns:
        A greeting message.
    """
    return f"Hello, {name}! Welcome to {{PROJECT_NAME}} 🚀"


@app.command
def get_system_info() -> dict:
    """
    Get system information.

    Returns:
        Dictionary with OS, Python version, and platform info.
    """
    import platform

    return {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "platform": platform.machine(),
    }


@app.command
def add_numbers(a: int, b: int) -> int:
    """
    Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b


# Run the application
if __name__ == "__main__":
    app.run(debug=True)
