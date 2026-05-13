import re

with open("/home/swadhin/Forge/forge-framework/forge/api/fs.py") as f:
    orig = f.read()

# I am going to replace the imports and FileSystemAPI class completely up to _resolve_path ending.
import_and_class_start = """from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Set, Any, Union

from forge.config import FileSystemPermissions

def _expand_path_var(p: str) -> Path:
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    if p.startswith("$APPDATA"):
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "~\\\\AppData\\\\Roaming")
            p = p.replace("$APPDATA", appdata)
        elif sys.platform == "darwin":
            p = p.replace("$APPDATA", "~/Library/Application Support")
        else:
            p = p.replace("$APPDATA", "~/.config")
        p = os.path.expanduser(p)
    return Path(p).resolve()

class FileSystemAPI:
    \"\"\"
    __forge_capability__ = "filesystem"
    File system API for Forge applications with Strict Scopes.
    \"\"\"

    def __init__(
        self,
        base_path: Path | None = None,
        permissions: Union[bool, FileSystemPermissions] = True,
    ) -> None:
        self._base_path = base_path.resolve() if base_path else Path.cwd().resolve()

        self._read_dirs: List[Path] = []
        self._write_dirs: List[Path] = []

        if isinstance(permissions, bool) and permissions:
            self._read_dirs.append(self._base_path)
            self._write_dirs.append(self._base_path)
        elif hasattr(permissions, 'read'):
            for p in getattr(permissions, 'read', []):
                self._read_dirs.append(_expand_path_var(p))
            for p in getattr(permissions, 'write', []):
                self._write_dirs.append(_expand_path_var(p))

    def _is_path_allowed(self, resolved_path: Path, mode: str = "read") -> bool:
        allowed = self._write_dirs if mode == "write" else self._read_dirs
        for allowed_dir in allowed:
            try:
                resolved_path.relative_to(allowed_dir)
                return True
            except ValueError:
                continue
        return False

    def _resolve_path(self, path: str, mode: str = "read", allow_absolute: bool = False) -> Path:
        if not path:
            raise ValueError("Path cannot be empty")
        if '\\x00' in path:
            raise ValueError("Invalid path: null byte detected")

        input_path = Path(path)

        if input_path.is_absolute():
            if not allow_absolute:
                input_path = Path(path.lstrip("/\\\\"))
                resolved = (self._base_path / input_path).resolve()
            else:
                resolved = input_path.resolve()
        else:
            resolved = (self._base_path / input_path).resolve()

        if not self._is_path_allowed(resolved, mode=mode):
            raise ValueError(
                f"Access denied: Path '{path}' resolves to '{resolved}' "
                f"which is outside allowed {mode} directories."
            )

        return resolved
"""

orig_parts = orig.split("def read(self, path: str, max_size: int = 10 * 1024 * 1024) -> str:", 1)

new_content = (
    orig[: orig.find("from __future__ import annotations")]
    + import_and_class_start
    + "\n    def read(self, path: str, max_size: int = 10 * 1024 * 1024) -> str:"
    + orig_parts[1]
)

# Now we need to update all calls to self._resolve_path to pass mode="write" where appropriate
new_content = new_content.replace(
    "resolved = self._resolve_path(path)", "resolved = self._resolve_path(path, mode='write')"
)
# That's too aggressive, let's just do it manually with regex.

new_content2 = new_content


# manually doing write operations:
def fix_func(func_name, content, mode):
    pattern = (
        f"def {func_name}\\(.*?\\).*?:.*?resolved = self._resolve_path\\(path(?:, mode='write')?\\)"
    )
    match = re.search(pattern, content, re.DOTALL)
    if match:
        repl = match.group(0).replace(
            "self._resolve_path(path)", f"self._resolve_path(path, mode='{mode}')"
        )
        repl = repl.replace(
            "self._resolve_path(path, mode='write', mode='write'",
            "self._resolve_path(path, mode='write'",
        )
        repl = repl.replace(
            "self._resolve_path(path, mode='write', mode='read'",
            "self._resolve_path(path, mode='read'",
        )
        return content[: match.start()] + repl + content[match.end() :]
    return content


# Initial replace was bad, let's restart replacing:
new_content = (
    orig[: orig.find("from __future__ import annotations")]
    + import_and_class_start
    + "\n    def read(self, path: str, max_size: int = 10 * 1024 * 1024) -> str:"
    + orig_parts[1]
)

for func in ["write", "write_binary", "delete", "mkdir"]:
    new_content = fix_func(func, new_content, "write")

with open("/home/swadhin/Forge/forge-framework/forge/api/fs.py", "w") as f:
    f.write(new_content)
