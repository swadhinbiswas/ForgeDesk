"""
IPC Handlers for the frontend.
"""

from forge import ForgeApp
from services.system import SystemService

def register_system_commands(app: ForgeApp):
    """
    Register all system-related commands on this app instance.
    """
    
    @app.command
    def get_system_info() -> dict:
        return SystemService.get_info()

    @app.command
    def analyze_data(payload: str) -> str:
        return SystemService.process_data(payload)
