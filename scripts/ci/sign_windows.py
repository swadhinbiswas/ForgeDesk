from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


SIGNABLE_SUFFIXES = {".exe", ".msi", ".dll"}


def main() -> None:
    signtool = shutil.which("signtool")
    if not signtool:
        raise FileNotFoundError("signtool is required for Windows signing")

    cert_path = os.environ["FORGE_WINDOWS_CERT_PATH"]
    cert_password = os.environ["FORGE_WINDOWS_CERT_PASSWORD"]
    timestamp_url = os.environ.get("FORGE_WINDOWS_TIMESTAMP_URL")
    artifacts = [Path(path) for path in json.loads(os.environ.get("FORGE_BUILD_ARTIFACTS", "[]"))]
    targets = [path for path in artifacts if path.exists() and path.suffix.lower() in SIGNABLE_SUFFIXES]
    if not targets:
        raise RuntimeError("No signable Windows artifacts were found")

    for target in targets:
        command = [signtool, "sign", "/fd", "SHA256", "/f", cert_path, "/p", cert_password]
        if timestamp_url:
            command.extend(["/tr", timestamp_url, "/td", "SHA256"])
        command.append(str(target))
        subprocess.run(command, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    main()
