from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "smoke_installers.py"
_spec = spec_from_file_location("smoke_installers", SCRIPT_PATH)
assert _spec and _spec.loader
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)
installers_for_platform = _module._installers_for_platform


def test_installer_selection_filters_by_platform_and_validates_paths(tmp_path: Path) -> None:
    appimage = tmp_path / "Forge.AppImage"
    appimage.write_text("bin", encoding="utf-8")
    flatpak = tmp_path / "Forge.flatpak"
    flatpak.write_text("flatpak", encoding="utf-8")
    msi = tmp_path / "Forge.msi"
    msi.write_text("msi", encoding="utf-8")
    nsis = tmp_path / "Forge.exe"
    nsis.write_text("nsis", encoding="utf-8")

    linux_selected = installers_for_platform(
        [
            {"format": "dir", "path": str(tmp_path / "dir")},
            {"format": "appimage", "path": str(appimage)},
            {"format": "flatpak", "path": str(flatpak)},
        ],
        "linux",
    )
    assert [item["format"] for item in linux_selected] == ["appimage", "flatpak"]

    windows_selected = installers_for_platform(
        [
            {"format": "msi", "path": str(msi)},
            {"format": "nsis", "path": str(nsis)},
        ],
        "win32",
    )
    assert [item["format"] for item in windows_selected] == ["msi", "nsis"]


def test_installer_selection_rejects_missing_supported_artifacts(tmp_path: Path) -> None:
    missing = tmp_path / "Forge.dmg"

    try:
        installers_for_platform([{"format": "dmg", "path": str(missing)}], "darwin")
    except FileNotFoundError as exc:
        assert "Installer artifact missing" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
