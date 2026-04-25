"""
{{PROJECT_NAME}} - Complex Template Backend

This template demonstrates a modular Forge application structure
with handlers (IPC routes) and services (business logic).

Quick start:
    ./forge dev        # Start development server
    ./forge build      # Build production binary
"""

import sys
from pathlib import Path

# Ensure src/ is in Python path for modular imports
sys.path.insert(0, str(Path(__file__).parent))

from forge import ForgeApp
from handlers.system import register_system_commands
import config


def create_app() -> ForgeApp:
    """Factory function for initializing the Forge App."""
    app = ForgeApp()
    register_system_commands(app)

    @app.command
    def greet(name: str) -> str:
        return f"Hello, {name}! Welcome to {config.APP_NAME} 🚀"

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=config.DEBUG)
