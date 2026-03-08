"""
Tests for Forge File System API.

Includes security tests for path traversal prevention.
"""

import pytest
import tempfile
from pathlib import Path

from forge.api.fs import FileSystemAPI


class TestFileSystemAPI:
    """Tests for FileSystemAPI class."""

    @pytest.fixture
    def fs_api(self, tmp_path: Path) -> FileSystemAPI:
        """Create a FileSystemAPI instance with a temp base directory."""
        return FileSystemAPI(base_path=tmp_path)

    @pytest.fixture
    def sample_files(self, tmp_path: Path) -> Path:
        """Create sample files for testing."""
        # Create test structure
        (tmp_path / "subdir").mkdir()
        (tmp_path / "test.txt").write_text("Hello, World!")
        (tmp_path / "subdir" / "nested.txt").write_text("Nested content")
        return tmp_path

    def test_read_file(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test reading a file."""
        content = fs_api.read("test.txt")
        assert content == "Hello, World!"

    def test_read_nonexistent(self, fs_api: FileSystemAPI) -> None:
        """Test reading a non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            fs_api.read("nonexistent.txt")

    def test_read_directory(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test reading a directory raises error."""
        with pytest.raises(IsADirectoryError):
            fs_api.read("subdir")

    def test_write_file(self, fs_api: FileSystemAPI) -> None:
        """Test writing to a file."""
        fs_api.write("output.txt", "Test content")
        assert (fs_api.get_base_path() / "output.txt").read_text() == "Test content"

    def test_write_creates_parent_dirs(self, fs_api: FileSystemAPI) -> None:
        """Test that write creates parent directories."""
        fs_api.write("nested/deep/file.txt", "Content")
        assert (fs_api.get_base_path() / "nested" / "deep" / "file.txt").exists()

    def test_write_to_directory_raises(self, fs_api: FileSystemAPI) -> None:
        """Test writing to a directory path raises error."""
        (fs_api.get_base_path() / "mydir").mkdir()
        with pytest.raises(IsADirectoryError):
            fs_api.write("mydir", "content")

    def test_exists(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test checking if a file exists."""
        assert fs_api.exists("test.txt") is True
        assert fs_api.exists("nonexistent.txt") is False

    def test_list_dir(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test listing directory contents."""
        items = fs_api.list_dir(".")
        names = [item["name"] for item in items]
        assert "test.txt" in names
        assert "subdir" in names

    def test_list_dir_returns_file_info(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test that list_dir returns detailed file info."""
        items = fs_api.list_dir(".")
        test_file = next((i for i in items if i["name"] == "test.txt"), None)
        assert test_file is not None
        assert test_file["is_file"] is True
        assert test_file["size"] == 13  # "Hello, World!"

    def test_list_nonexistent_dir(self, fs_api: FileSystemAPI) -> None:
        """Test listing a non-existent directory."""
        with pytest.raises(FileNotFoundError):
            fs_api.list_dir("nonexistent")

    def test_list_file_as_dir(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test listing a file as directory raises error."""
        with pytest.raises(NotADirectoryError):
            fs_api.list_dir("test.txt")

    def test_delete_file(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test deleting a file."""
        fs_api.delete("test.txt")
        assert fs_api.exists("test.txt") is False

    def test_delete_nonexistent(self, fs_api: FileSystemAPI) -> None:
        """Test deleting a non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            fs_api.delete("nonexistent.txt")

    def test_mkdir(self, fs_api: FileSystemAPI) -> None:
        """Test creating a directory."""
        fs_api.mkdir("newdir")
        assert (fs_api.get_base_path() / "newdir").is_dir()

    def test_mkdir_already_exists(self, fs_api: FileSystemAPI) -> None:
        """Test creating a directory that exists raises error."""
        (fs_api.get_base_path() / "existing").mkdir()
        with pytest.raises(FileExistsError):
            fs_api.mkdir("existing")

    def test_is_file(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test checking if path is a file."""
        assert fs_api.is_file("test.txt") is True
        assert fs_api.is_file("subdir") is False

    def test_is_dir(self, fs_api: FileSystemAPI, sample_files: Path) -> None:
        """Test checking if path is a directory."""
        assert fs_api.is_dir("subdir") is True
        assert fs_api.is_dir("test.txt") is False


class TestFileSystemAPISecurity:
    """Security tests for FileSystemAPI."""

    @pytest.fixture
    def fs_api(self, tmp_path: Path) -> FileSystemAPI:
        """Create a FileSystemAPI instance with a temp base directory."""
        return FileSystemAPI(base_path=tmp_path)

    def test_path_traversal_dotdot(self, fs_api: FileSystemAPI) -> None:
        """Test that ../ path traversal is blocked."""
        with pytest.raises(ValueError, match="outside allowed"):
            fs_api.read("../../../etc/passwd")

    def test_path_traversal_absolute(self, fs_api: FileSystemAPI) -> None:
        """Test that absolute paths outside base are blocked."""
        with pytest.raises(ValueError, match="not allowed|outside allowed"):
            fs_api.read("/etc/passwd")

    def test_null_byte_in_path(self, fs_api: FileSystemAPI) -> None:
        """Test that null bytes in path are rejected."""
        with pytest.raises(ValueError, match="null byte"):
            fs_api.read("test\x00.txt")

    def test_empty_path(self, fs_api: FileSystemAPI) -> None:
        """Test that empty path is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            fs_api.read("")

    def test_cannot_delete_base_dir(self, fs_api: FileSystemAPI) -> None:
        """Test that deleting the base directory is blocked."""
        with pytest.raises(ValueError, match="Cannot delete"):
            fs_api.delete(".")

    def test_symlink_outside_base(self, fs_api: FileSystemAPI, tmp_path: Path) -> None:
        """Test that symlinks pointing outside base are blocked."""
        # Create a file outside base
        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_text("Outside content")

        # Create symlink inside base pointing outside
        symlink_path = fs_api.get_base_path() / "link.txt"
        try:
            symlink_path.symlink_to(outside_file)

            # Accessing through symlink should be blocked
            with pytest.raises(ValueError, match="outside allowed"):
                fs_api.read("link.txt")
        except OSError, NotImplementedError:
            # Symlinks not supported on this system
            pytest.skip("Symlinks not supported")

    def test_allowed_dirs_extension(self, tmp_path: Path) -> None:
        """Test that allowed_dirs can grant access to specific directories."""
        # Create an additional allowed directory
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        (allowed_dir / "file.txt").write_text("Allowed content")

        # Create API with the allowed directory as the base path and
        # the extra directory in allowed_dirs so _is_path_allowed passes.
        base = tmp_path / "base"
        base.mkdir()

        fs_api = FileSystemAPI(base_path=base, allowed_dirs=[allowed_dir])

        # The file is inside allowed_dir, which is in allowed_dirs.
        # Use a relative path from base that resolves via _resolve_path
        # with allow_absolute=True -- but since read() only calls
        # _resolve_path(path) without allow_absolute, we need to
        # verify via the internal method that the allowed_dirs work.
        # The public API for accessing allowed_dirs paths is via
        # _resolve_path directly (e.g., from custom command handlers).
        resolved = fs_api._resolve_path(str(allowed_dir / "file.txt"), allow_absolute=True)
        assert resolved == (allowed_dir / "file.txt").resolve()
        assert resolved.read_text() == "Allowed content"
