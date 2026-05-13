import os
import sys
from pathlib import Path


def expand_path(p: str) -> Path:
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    if p.startswith("$APPDATA"):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "~\\AppData\\Roaming")
            p = p.replace("$APPDATA", appdata)
        elif sys.platform == "darwin":
            p = p.replace("$APPDATA", "~/Library/Application Support")
        else:
            p = p.replace("$APPDATA", "~/.config")
        p = os.path.expanduser(p)
    return Path(p).resolve()
