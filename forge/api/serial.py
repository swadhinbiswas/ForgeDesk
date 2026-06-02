import logging
import threading
import time
from typing import Any

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)


class SerialAPI:
    """
    Serial Port Hardware API for connecting to local USB devices, Arduinos, and IoT boards.
    """

    __forge_capability__ = "serial"

    def __init__(self, app: Any = None) -> None:
        self._app = app
        self._connections: dict[str, serial.Serial] = {}
        self._connections_lock = threading.Lock()
        # We run the background readers in threads (async read not natively supported cross platform via pyserial)  # noqa: E501
        self._running: bool = True
        logger.info("Initializing Hardware Serial/USB API")

    def _emit(self, event: str, payload: Any) -> None:
        """Emit an event through the parent app if attached."""
        if self._app is None:
            return
        try:
            self._app.events.emit(event, payload)
        except Exception as exc:
            logger.warning("Failed to emit %s: %s", event, exc)

    def available_ports(self) -> list[dict[str, str]]:
        """List all available serial ports on the system."""
        ports = serial.tools.list_ports.comports()
        return [
            {
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "manufacturer": str(getattr(p, "manufacturer", "") or ""),
            }
            for p in ports
        ]

    def open(self, port: str, baudrate: int = 9600) -> bool:
        """Open a serial connection."""
        with self._connections_lock:
            if port in self._connections:
                return True

        try:
            ser = serial.Serial(port, baudrate=baudrate, timeout=1)
            with self._connections_lock:
                self._connections[port] = ser

            # Start a read loop in background
            t = threading.Thread(target=self._read_loop, args=(port,), daemon=True)
            t.start()

            logger.info(f"Opened Serial port: {port} at {baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to open port {port}: {e}")
            return False

    def write(self, port: str, data: bytes) -> bool:
        """Write raw bytes to a port."""
        with self._connections_lock:
            ser = self._connections.get(port)
        if ser is None:
            return False

        try:
            ser.write(data)
            return True
        except Exception as e:
            logger.error(f"Write failure on {port}: {e}")
            return False

    def close(self, port: str) -> bool:
        """Close an open serial connection."""
        with self._connections_lock:
            ser = self._connections.pop(port, None)
        if ser is None:
            return False
        try:
            ser.close()
            return True
        except Exception as e:
            logger.error(f"Close failure on {port}: {e}")
            return False

    def _read_loop(self, port: str) -> None:
        """Background thread to read lines from serial and emit them to the frontend."""
        with self._connections_lock:
            ser = self._connections.get(port)
        if ser is None:
            return

        while self._running and ser.is_open:
            with self._connections_lock:
                if port not in self._connections:
                    break
            try:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    # Try to emit as string, but drop bad chars if not utf-8
                    text = data.decode("utf-8", errors="replace")
                    self._emit("serial_data", {"port": port, "data": text})
                else:
                    time.sleep(0.05)
            except Exception as e:
                logger.warning(f"Port {port} read loop disconnected: {e}")
                break

        # Clean up
        self.close(port)
        self._emit("serial_disconnected", {"port": port})

    def shutdown(self) -> None:
        """Cleanup all ports on exit."""
        self._running = False
        with self._connections_lock:
            ports = list(self._connections.keys())
        for port in ports:
            self.close(port)
