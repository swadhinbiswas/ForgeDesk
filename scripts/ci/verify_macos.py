from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

VERIFYABLE_SUFFIXES = {"", ".app", ".dmg", ".framework", ".so", ".dylib"}


def _select_targets() -> list[Path]:
    artifacts = json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))
    candidates = [Path(path) for path in artifacts]
    return [
        path
        for path in candidates
        if path.exists() and (path.is_dir() or path.suffix.lower() in VERIFYABLE_SUFFIXES)
    ]


def main() -> None:
    codesign = shutil.which("codesign")
    if not codesign:
        raise FileNotFoundError("codesign is required for macOS verification")

    targets = _select_targets()
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
