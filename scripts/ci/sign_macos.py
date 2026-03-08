from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


SIGNABLE_SUFFIXES = {"", ".app", ".dmg", ".framework", ".so", ".dylib"}


def _targets() -> list[Path]:
    artifacts = json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))
    candidates = [Path(path) for path in artifacts]
    return [path for path in candidates if path.exists() and (path.is_dir() or path.suffix.lower() in SIGNABLE_SUFFIXES)]


def main() -> None:
    identity = os.environ["FORGE_MACOS_SIGN_IDENTITY"]
    codesign = shutil.which("codesign")
    if not codesign:
        raise FileNotFoundError("codesign is required for macOS signing")

    timestamp_url = os.environ.get("FORGE_MACOS_TIMESTAMP_URL")
    timestamp_args = [f"--timestamp={timestamp_url}"] if timestamp_url else ["--timestamp"]

    targets = _targets()
    if not targets:
        raise RuntimeError("No signable macOS artifacts were found")

    for target in targets:
        subprocess.run(
            [codesign, "--force", "--deep", *timestamp_args, "--sign", identity, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    main()
