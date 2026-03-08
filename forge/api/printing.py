import json
import logging

logger = logging.getLogger(__name__)

class PrintingAPI:
    def __init__(self, app):
        self.app = app

        @self.app.events.on("ipc:print")
        def handle_print(event):
            try:
                self.print_page()
            except Exception as e:
                logger.error(f"Error handling print request: {e}")
                
    def print_page(self):
        """Open the native print dialog for the current window webview."""
        if hasattr(self.app.window, "print"):
            self.app.window.print("main")
        else:
            logger.error("Printing is not supported on this platform/version.")
