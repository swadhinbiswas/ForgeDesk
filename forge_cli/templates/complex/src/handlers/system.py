"""
System IPC Handlers — Utility commands.
"""

from services.system import SystemService

from forge import ForgeApp


def register_system_commands(app: ForgeApp):
    """Register system-related IPC commands."""

    @app.command
    def get_system_info() -> dict:
        """Get system information."""
        return SystemService.get_info()

    @app.command
    def analyze_data(payload: str) -> str:
        """Process data through the service layer."""
        return SystemService.process_data(payload)
