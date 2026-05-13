from pathlib import Path
from typing import Any

import pytest

from forge.app import ForgeApp


def _write_config(tmp_path: Path, permissions: dict[str, Any]) -> Path:
    config_file = tmp_path / "forge.toml"

    def to_toml(d: dict, prefix="") -> str:
        lines = []
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"[{prefix}{k}]")
                lines.append(to_toml(v, f"{prefix}{k}."))
            elif isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            else:
                lines.append(f"{k} = {v}")
        return "\n".join(lines)

    config = {"app": {"name": "Test"}, "permissions": permissions}

    config_file.write_text(to_toml(config))
    return config_file


class MockProxy:
    def __init__(self):
        self.registered = []

    def register_shortcut(self, accelerator):
        self.registered.append(accelerator)
        return True

    def unregister_shortcut(self, accelerator):
        if accelerator in self.registered:
            self.registered.remove(accelerator)
            return True
        return False

    def unregister_all_shortcuts(self):
        self.registered.clear()
        return True


class TestShortcutsAPI:
    def test_shortcuts_disabled(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, {})
        app = ForgeApp(str(config_path))
        app._proxy = MockProxy()
        app._is_ready = True

        with pytest.raises(PermissionError, match="global_shortcut"):
            app.shortcuts.register("CmdOrCtrl+Shift+X", lambda: None)

    def test_shortcuts_enabled(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, {"global_shortcut": True})
        app = ForgeApp(str(config_path))
        app._proxy = MockProxy()
        app._is_ready = True

        called = False

        def on_shortcut():
            nonlocal called
            called = True

        assert app.shortcuts.register("CmdOrCtrl+Shift+X", on_shortcut) is True
        assert "CmdOrCtrl+Shift+X" in app._proxy.registered

        # trigger shortcut via event
        app.events.emit("global_shortcut", {"accelerator": "CmdOrCtrl+Shift+X"})
        assert called is True

        assert app.shortcuts.unregister("CmdOrCtrl+Shift+X") is True
        assert "CmdOrCtrl+Shift+X" not in app._proxy.registered
