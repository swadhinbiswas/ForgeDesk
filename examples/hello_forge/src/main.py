import math
import time
from forge.app import ForgeApp
from forge.bridge import command


class PerformanceAPI:
    @command()
    def calculate_fibonacci(self, n: int) -> dict:
        """A heavy computation task to test performance."""
        start_time = time.perf_counter()

        # Iterative Fibonacci for speed/stability in demo
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b

        execution_time = (time.perf_counter() - start_time) * 1000

        # Compute digit count without str() conversion (avoids the
        # 4300-digit limit in Python 3.11+). log10(2) * bit_length
        # gives an accurate upper bound.
        if a > 0:
            num_digits = math.floor(a.bit_length() * math.log10(2)) + 1
        else:
            num_digits = 1

        # Only convert a small prefix to string for display.
        # Shift the number right so only ~60 leading digits remain,
        # which is safely under the 4300-digit limit.
        if num_digits > 60:
            shift_digits = num_digits - 60
            truncated = a // (10**shift_digits)
            preview = str(truncated)[:50] + "..."
        else:
            preview = str(a)

        return {
            "result": preview,
            "digits": num_digits,
            "execution_time_ms": execution_time,
            "n": n,
        }

    @command()
    def get_system_info(self) -> dict:
        """Returns basic system info instantly."""
        return {
            "os": "Native (Rust Core)",
            "engine": "Wry / Tao",
            "bridge": "Binary IPC",
            "python_version": "3.14 (No-GIL Optimized)",
        }


def main():
    import os
    import sys

    # Force X11 on Linux to avoid Wayland handle mismatches
    if sys.platform == "linux":
        os.environ["GDK_BACKEND"] = "x11"
        # Fix for GBM buffer / Hardware Acceleration issues on Linux
        os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
        print("Forcing X11 backend and disabling WebKit compositing for Linux compatibility...")

    # Initialize the Forge V2 App
    app = ForgeApp()

    # Register our performance API
    perf_api = PerformanceAPI()
    app.bridge.register_commands(perf_api)

    print("Forge V2 Performance Demo Started")
    app.run(debug=True)


if __name__ == "__main__":
    main()
