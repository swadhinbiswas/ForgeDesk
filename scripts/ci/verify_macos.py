from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


VERIFYABLE_SUFFIXES = {"", ".app", ".dmg", ".framework", ".so", ".dylib"}


def main() -> None:
    codesign = shutil.which("codesign")
    if not codesign:
        raise FileNotFoundError("codesign is required for macOS verification")

    artifacts = json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))
    targets = [
        Path(path)
        for path in artifacts
        if Path(path).exists() and (Path(path).is_dir() or Path(path).suffix.lower() in VERIFYABLE_SUFFIXES)
    ]
    if not targets:
        raise RuntimeError("No verifiable macOS artifacts were found")

    for target in targets:
        subprocess.run(
            [codesign, "--verify", "--deep", str(target)],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    main()
