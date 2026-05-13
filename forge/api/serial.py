import logging

import serial
import serial.tools.list_ports

from forge.events import emit  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class SerialAPI:
    """
    Serial Port Hardware API for connecting to local USB devices, Arduinos, and IoT boards.
    """

    __forge_capability__ = "serial"

    def __init__(self) -> None:
        self._connections: dict[str, serial.Serial] = {}
        # We run the background readers in threads (async read not natively supported cross platform via pyserial)  # noqa: E501
        self._running: bool = True
        logger.info("Initializing Hardware Serial/USB API")

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
        if port in self._connections:
            return True

        try:
            ser = serial.Serial(port, baudrate=baudrate, timeout=1)
            self._connections[port] = ser

            # Start a read loop in background
            import threading

            t = threading.Thread(target=self._read_loop, args=(port,), daemon=True)
            t.start()

            logger.info(f"Opened Serial port: {port} at {baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to open port {port}: {e}")
            return False

    def write(self, port: str, data: bytes) -> bool:
        """Write raw bytes to a port."""
        if port not in self._connections:
            return False

        try:
            self._connections[port].write(data)
            return True
        except Exception as e:
            logger.error(f"Write failure on {port}: {e}")
            return False

    def close(self, port: str) -> bool:
        """Close an open serial connection."""
        if port in self._connections:
            try:
                self._connections[port].close()
                del self._connections[port]
                return True
            except Exception as e:
                logger.error(f"Close failure on {port}: {e}")
        return False

    def _read_loop(self, port: str) -> None:
        """Background thread to read lines from serial and emit them to the frontend."""
        if port not in self._connections:
            return

        ser = self._connections[port]
        while self._running and port in self._connections and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    # Try to emit as string, but drop bad chars if not utf-8
                    text = data.decode("utf-8", errors="replace")
                    emit("serial_data", {"port": port, "data": text})
                else:
                    import time

                    time.sleep(0.05)
            except Exception as e:
                logger.warning(f"Port {port} read loop disconnected: {e}")
                break

        # Clean up
        self.close(port)
        emit("serial_disconnected", {"port": port})

    def shutdown(self) -> None:
        """Cleanup all ports on exit."""
        self._running = False
        ports = list(self._connections.keys())
        for port in ports:
            self.close(port)
