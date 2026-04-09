"""
System-level services and business logic.
"""
import platform

class SystemService:
    @staticmethod
    def get_info() -> dict:
        return {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "platform": platform.machine(),
        }

    @staticmethod
    def process_data(data: str) -> str:
        # Perform some business logic here
        return f"Processed: {data}"
