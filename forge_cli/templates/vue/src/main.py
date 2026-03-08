"""
{{PROJECT_NAME}} - Python Backend (Vue Template)

This is the main entry point for your Forge application.
Define your Python commands here and expose them to the frontend.
"""

from forge import ForgeApp

# Create the app instance
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


# Run the application
if __name__ == "__main__":
    app.run(debug=True)
