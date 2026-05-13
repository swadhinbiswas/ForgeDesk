import logging
from typing import Any

logger = logging.getLogger(__name__)


class PrintingAPI:
    __forge_capability__ = "printing"

    def __init__(self, app: Any) -> None:
        self.app = app

        @self.app.events.on("ipc:print")
        def handle_print(event: Any) -> None:
            try:
                self.print_page()
            except Exception as e:
                logger.error(f"Error handling print request: {e}")

    def print_page(self) -> None:
        """Open the native print dialog for the current window webview."""
        checker = getattr(self.app, "has_capability", None)
        if callable(checker) and not checker("printing"):
            raise PermissionError("The 'printing' capability is required.")

        proxy = getattr(self.app, "_proxy", None)
        if proxy is not None and hasattr(proxy, "print"):
            proxy.print("main")
            return

        window = getattr(self.app, "window", None)
        if window is not None and hasattr(window, "print"):
            window.print("main")
            return

        logger.error("Printing is not supported on this platform/version.")
