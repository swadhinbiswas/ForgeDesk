"""
Forge File System API.

Provides safe file system operations for Forge applications.
All operations are synchronous and raise exceptions on errors.

Security:
    - All paths are validated to prevent directory traversal
    - Absolute paths outside the allowed directory are blocked
    - Symlinks are resolved and validated
"""

from __future__ import annotations

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
            appdata = os.environ.get("APPDATA", "~\\AppData\\Roaming")
            p = p.replace("$APPDATA", appdata)
        elif sys.platform == "darwin":
            p = p.replace("$APPDATA", "~/Library/Application Support")
        else:
            p = p.replace("$APPDATA", "~/.config")
        p = os.path.expanduser(p)
    return Path(p).resolve()

class FileSystemAPI:
    """
    __forge_capability__ = "filesystem"
    File system API for Forge applications with Strict Scopes.
    """

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
        if '\x00' in path:
            raise ValueError("Invalid path: null byte detected")

        # Automatically expand $VARs using our strict logic so UI can pass "$APPDATA/file.txt"
        if path.startswith("$") or path.startswith("~"):
            input_path = _expand_path_var(path)
            # This makes it absolute, so we override to allow it as it's an explicit scope intent.
            allow_absolute = True
        else:
            input_path = Path(path)
        
        if input_path.is_absolute():
            if not allow_absolute:
                input_path = Path(path.lstrip("/\\"))
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

    def read(self, path: str, max_size: int = 10 * 1024 * 1024) -> str:
        """
        Read the contents of a file.

        Args:
            path: Path to the file to read.
            max_size: Maximum file size to read (default 10MB) to prevent DoS.

        Returns:
            The file contents as a string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            PermissionError: If the file cannot be read.
            IsADirectoryError: If the path is a directory.
            ValueError: If the file is too large.
        """
        resolved = self._resolve_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if resolved.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")

        # Check file size before reading
        file_size = resolved.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File too large: {file_size} bytes (max: {max_size})"
            )

        return resolved.read_text(encoding="utf-8")

    def read_binary(self, path: str, max_size: int = 50 * 1024 * 1024) -> bytes:
        """
        Read the contents of a binary file.

        Args:
            path: Path to the file to read.
            max_size: Maximum file size to read (default 50MB).

        Returns:
            The file contents as bytes.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is too large.
        """
        resolved = self._resolve_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if resolved.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")

        file_size = resolved.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File too large: {file_size} bytes (max: {max_size})"
            )

        return resolved.read_bytes()

    def write(self, path: str, content: str) -> None:
        """
        Write content to a file.

        Creates parent directories if they don't exist.

        Args:
            path: Path to the file to write.
            content: The content to write to the file.

        Raises:
            PermissionError: If the file cannot be written.
            IsADirectoryError: If the path is a directory.
            ValueError: If the path is invalid.
        """
        resolved = self._resolve_path(path, mode='write')

        if resolved.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding="utf-8")

    def write_binary(self, path: str, content: bytes) -> None:
        """
        Write binary content to a file.

        Args:
            path: Path to the file to write.
            content: The binary content to write.

        Raises:
            PermissionError: If the file cannot be written.
            IsADirectoryError: If the path is a directory.
        """
        resolved = self._resolve_path(path, mode='write')

        if resolved.is_dir():
            raise IsADirectoryError(f"Path is a directory: {path}")

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(content)

    def exists(self, path: str) -> bool:
        """
        Check if a file or directory exists.

        Args:
            path: Path to check.

        Returns:
            True if the path exists and is accessible, False otherwise.
        """
        try:
            resolved = self._resolve_path(path)
            return resolved.exists()
        except (ValueError, OSError):
            return False

    def list_dir(self, path: str, include_hidden: bool = False) -> List[dict]:
        """
        List the contents of a directory.

        Args:
            path: Path to the directory to list.
            include_hidden: If True, include hidden files (starting with .).

        Returns:
            List of dicts with file info: {name, is_file, size, modified}.

        Raises:
            NotADirectoryError: If the path is not a directory.
            FileNotFoundError: If the directory doesn't exist.
        """
        resolved = self._resolve_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not resolved.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        items = []
        for item in resolved.iterdir():
            # Skip hidden files unless requested
            if not include_hidden and item.name.startswith('.'):
                continue

            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except (OSError, PermissionError):
                # Skip items we can't access
                continue

        return items

    def list(self, path: str, include_hidden: bool = False) -> List[dict]:
        """
        Compatibility alias for listing directory contents.

        Args:
            path: Path to the directory to list.
            include_hidden: If True, include hidden files.

        Returns:
            Directory contents.
        """
        return self.list_dir(path, include_hidden=include_hidden)

    def delete(self, path: str, recursive: bool = False) -> None:
        """
        Delete a file or directory.

        Args:
            path: Path to delete.
            recursive: If True, delete directories recursively.

        Raises:
            FileNotFoundError: If the path doesn't exist.
            OSError: If deletion fails.
            ValueError: If trying to delete base directory.
        """
        resolved = self._resolve_path(path, mode='write')

        if not resolved.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Prevent deleting the base directory
        if resolved == self._base_path:
            raise ValueError("Cannot delete the base directory")

        if resolved.is_dir():
            if recursive:
                import shutil
                shutil.rmtree(resolved)
            else:
                resolved.rmdir()
        else:
            resolved.unlink()

    def mkdir(self, path: str, parents: bool = True) -> None:
        """
        Create a directory.

        Args:
            path: Path to the directory to create.
            parents: If True, create parent directories as needed.

        Raises:
            FileExistsError: If the directory already exists.
            ValueError: If the path is invalid.
        """
        resolved = self._resolve_path(path, mode='write')
        resolved.mkdir(parents=parents, exist_ok=False)

    def is_file(self, path: str) -> bool:
        """
        Check if a path is a file.

        Args:
            path: Path to check.

        Returns:
            True if the path is a file, False otherwise.
        """
        try:
            resolved = self._resolve_path(path)
            return resolved.is_file()
        except (ValueError, OSError):
            return False

    def is_dir(self, path: str) -> bool:
        """
        Check if a path is a directory.

        Args:
            path: Path to check.

        Returns:
            True if the path is a directory, False otherwise.
        """
        try:
            resolved = self._resolve_path(path)
            return resolved.is_dir()
        except (ValueError, OSError):
            return False

    def get_base_path(self) -> Path:
        """
        Get the base path for this FileSystemAPI instance.

        Returns:
            The base Path object.
        """
        return self._base_path
