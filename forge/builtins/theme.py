"""Theme hints (built-in extension)."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

_CAP = "forge_extensions"


class BuiltinThemeAPI:
    __forge_capability__ = _CAP

    def system_dark_mode_hint(self) -> dict[str, Any]:
        """Best-effort dark mode detection (for UI theming)."""
        sys = platform.system().lower()
        if sys == "darwin":
            try:
                out = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                dark = out.returncode == 0 and "dark" in (out.stdout or "").lower()
                return {"ok": True, "dark": dark, "source": "macos_defaults"}
            except Exception:
                return {"ok": True, "dark": None, "source": "unknown"}
        if sys == "windows":
            try:
                import winreg  # type: ignore[import-untyped]

                key = winreg.OpenKey(  # type: ignore[attr-defined]
                    winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                )
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")  # type: ignore[attr-defined]
                winreg.CloseKey(key)  # type: ignore[attr-defined]
                return {"ok": True, "dark": val == 0, "source": "windows_registry"}
            except Exception:
                return {"ok": True, "dark": None, "source": "unknown"}
        if sys == "linux":
            try:
                out = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if out.returncode == 0 and "dark" in (out.stdout or "").lower():
                    return {"ok": True, "dark": True, "source": "gsettings"}
            except Exception:
                pass
            gtk = os.environ.get("GTK_THEME", "")
            if "dark" in gtk.lower():
                return {"ok": True, "dark": True, "source": "gtk_theme_env"}
        return {"ok": True, "dark": None, "source": "unknown"}


def register(app: Any) -> None:
    app.bridge.register_commands(BuiltinThemeAPI())
