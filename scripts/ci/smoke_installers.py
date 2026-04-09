from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


LAUNCH_SECONDS = 6


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, check=True, capture_output=True, text=True)


def _launch_for_a_moment(command: list[str], *, env: dict[str, str] | None = None) -> None:
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(LAUNCH_SECONDS)
    if process.poll() not in {None, 0}:
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(f"Launch failed for {' '.join(command)}\nstdout={stdout}\nstderr={stderr}")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("build"), dict):
        return payload
    if payload.get("package"):
        return {"build": payload}
    raise ValueError(f"Unsupported build payload: {path}")


def _installers_for_platform(installers: list[dict[str, Any]], platform_name: str) -> list[dict[str, Any]]:
    if platform_name.startswith("linux"):
        supported = {"appimage", "flatpak"}
    elif platform_name == "darwin":
        supported = {"dmg"}
    elif platform_name == "win32":
        supported = {"msi", "nsis"}
    else:
        raise RuntimeError(f"Unsupported smoke-test platform: {platform_name}")

    selected: list[dict[str, Any]] = []
    for installer in installers:
        if not isinstance(installer, dict):
            continue
        fmt = installer.get("format")
        path = installer.get("path")
        if fmt not in supported or not isinstance(path, str) or not path:
            continue
        artifact_path = Path(path)
        if not artifact_path.exists() or not artifact_path.is_file():
            raise FileNotFoundError(f"Installer artifact missing: {artifact_path}")
        selected.append(installer)

    if not selected:
        raise ValueError(f"No supported installers found for platform {platform_name}")
    return selected


def _linux_smoke(installers: list[dict[str, Any]]) -> None:
    xvfb = shutil.which("xvfb-run")
    for installer in installers:
        fmt = installer["format"]
        path = Path(installer["path"])
        if fmt == "appimage":
            path.chmod(path.stat().st_mode | 0o111)
            command = [str(path)]
            if xvfb:
                command = [xvfb, "-a", *command]
            _launch_for_a_moment(command, env={**os.environ, "APPIMAGE_EXTRACT_AND_RUN": "1"})
        elif fmt == "flatpak":
            _run(["flatpak", "install", "--user", "-y", "--bundle", str(path)])
            _run([
                "flatpak",
                "run",
                "--command=sh",
                installer["app_id"],
                "-c",
                "echo forge-flatpak-smoke-ok",
            ])


def _macos_smoke(installers: list[dict[str, Any]]) -> None:
    for installer in installers:
        if installer["format"] != "dmg":
            continue
        dmg_path = Path(installer["path"])
        mount_point = Path(tempfile.mkdtemp(prefix="forge-dmg-"))
        try:
            _run(["hdiutil", "attach", str(dmg_path), "-mountpoint", str(mount_point), "-nobrowse", "-quiet"])
            app_bundle = next(mount_point.glob("*.app"))
            info_plist = plistlib.loads((app_bundle / "Contents" / "Info.plist").read_bytes())
            executable = info_plist["CFBundleExecutable"]
            binary = app_bundle / "Contents" / "MacOS" / executable
            _launch_for_a_moment([str(binary)])
        finally:
            subprocess.run(["hdiutil", "detach", str(mount_point), "-quiet"], check=False, capture_output=True, text=True)


def _find_windows_binary(install_root: Path) -> Path:
    for candidate in install_root.rglob("*.exe"):
        if candidate.name.lower() not in {"uninstall.exe", "unins000.exe"}:
            return candidate
    raise FileNotFoundError(f"No installed executable found in {install_root}")


def _windows_smoke(installers: list[dict[str, Any]]) -> None:
    for installer in installers:
        fmt = installer["format"]
        path = Path(installer["path"])
        install_root = Path(tempfile.mkdtemp(prefix=f"forge-{fmt}-"))
        if fmt == "msi":
            _run(["msiexec", "/i", str(path), "/qn", f"INSTALLFOLDER={install_root}"])
        elif fmt == "nsis":
            _run([str(path), "/S", f"/D={install_root}"])
        else:
            continue
        binary = _find_windows_binary(install_root)
        _launch_for_a_moment([str(binary)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Forge installer artifacts")
    parser.add_argument("--build-result", required=True)
    args = parser.parse_args()

    payload = _load_payload(Path(args.build_result))
    installers = _installers_for_platform(list(payload["build"].get("installers", [])), sys.platform)

    current = sys.platform
    if current.startswith("linux"):
        _linux_smoke(installers)
    elif current == "darwin":
        _macos_smoke(installers)
    elif current == "win32":
        _windows_smoke(installers)
    else:
        raise RuntimeError(f"Unsupported smoke-test platform: {current}")


if __name__ == "__main__":
    main()
