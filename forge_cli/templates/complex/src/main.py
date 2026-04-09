"""
{{PROJECT_NAME}} - Main Entry Point

This file sets up a modular Forge application, splitting logic into
handlers (IPC routes) and services (business logic).
"""

from forge import ForgeApp
from handlers.system import register_system_commands

import config

def create_app() -> ForgeApp:
    """Factory function for initializing the Forge App."""
    app = ForgeApp()

    # Register modular subsystems
    register_system_commands(app)
    
    @app.command
    def greet(name: str) -> str:
        return f"Hello, {name}! Welcome to {config.APP_NAME} 🚀"
        
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=config.DEBUG)
