from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    xcrun = shutil.which("xcrun")
    if not xcrun:
        raise FileNotFoundError("xcrun is required for macOS notarization")

    artifacts = [Path(path) for path in json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))]
    submit_target = next((path for path in artifacts if path.exists() and path.suffix.lower() == ".dmg"), None)
    if submit_target is None:
        submit_target = next((path for path in artifacts if path.exists() and path.suffix.lower() == ".app"), None)
    if submit_target is None:
        raise RuntimeError("No notarizable macOS artifact (.dmg or .app) was found")

    profile = os.environ.get("FORGE_MACOS_NOTARY_PROFILE")
    if profile:
        command = [xcrun, "notarytool", "submit", str(submit_target), "--wait", "--keychain-profile", profile]
    else:
        apple_id = os.environ["FORGE_MACOS_NOTARY_APPLE_ID"]
        team_id = os.environ["FORGE_MACOS_NOTARY_TEAM_ID"]
        password = os.environ["FORGE_MACOS_NOTARY_PASSWORD"]
        command = [
            xcrun,
            "notarytool",
            "submit",
            str(submit_target),
            "--wait",
            "--apple-id",
            apple_id,
            "--team-id",
            team_id,
            "--password",
            password,
        ]

    subprocess.run(command, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    main()
