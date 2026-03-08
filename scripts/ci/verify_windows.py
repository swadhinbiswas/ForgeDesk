from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import os


VERIFYABLE_SUFFIXES = {".exe", ".msi", ".dll"}


def main() -> None:
    signtool = shutil.which("signtool")
    if not signtool:
        raise FileNotFoundError("signtool is required for Windows verification")

    artifacts = [Path(path) for path in json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))]
    targets = [path for path in artifacts if path.exists() and path.suffix.lower() in VERIFYABLE_SUFFIXES]
    if not targets:
        raise RuntimeError("No verifiable Windows artifacts were found")

    for target in targets:
        subprocess.run([signtool, "verify", "/pa", str(target)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    main()
