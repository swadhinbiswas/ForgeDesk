from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_script(path: Path, module_name: str):
    spec = spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
sign_windows = _load_script(ROOT / "scripts" / "ci" / "sign_windows.py", "sign_windows")
verify_windows = _load_script(ROOT / "scripts" / "ci" / "verify_windows.py", "verify_windows")
sign_macos = _load_script(ROOT / "scripts" / "ci" / "sign_macos.py", "sign_macos")
verify_macos = _load_script(ROOT / "scripts" / "ci" / "verify_macos.py", "verify_macos")


def test_windows_target_selection_filters_existing_suffixes(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "Forge.exe"
    msi = tmp_path / "Forge.msi"
    dll = tmp_path / "Forge.dll"
    exe.write_text("exe", encoding="utf-8")
    msi.write_text("msi", encoding="utf-8")
    dll.write_text("dll", encoding="utf-8")

    monkeypatch.setenv(
        "FORGE_BUILD_ARTIFACTS",
        json.dumps([str(exe), str(msi), str(dll), str(tmp_path / "missing.txt")]),
    )

    assert sign_windows._select_targets() == [exe, msi, dll]
    assert verify_windows._select_targets() == [exe, msi, dll]


def test_macos_target_selection_filters_existing_suffixes(tmp_path: Path, monkeypatch) -> None:
    app_bundle = tmp_path / "Forge.app"
    dmg = tmp_path / "Forge.dmg"
    framework = tmp_path / "Forge.framework"
    app_bundle.mkdir()
    dmg.write_text("dmg", encoding="utf-8")
    framework.mkdir()

    monkeypatch.setenv(
        "FORGE_BUILD_ARTIFACTS",
        json.dumps([str(app_bundle), str(dmg), str(framework), str(tmp_path / "missing.so")]),
    )

    assert sign_macos._select_targets() == [app_bundle, dmg, framework]
    assert verify_macos._select_targets() == [app_bundle, dmg, framework]
