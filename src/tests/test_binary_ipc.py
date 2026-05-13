import os
import urllib.parse
from pathlib import Path

from forge.api.fs import FileSystemAPI


def test_asset_url_generation():

    # We allow the /tmp directory for testing
    allowed_dirs = [Path("/tmp").resolve()]

    # Initialize the FileSystemAPI
    fs = FileSystemAPI(base_path=Path("/tmp"), permissions=True, allowed_dirs=allowed_dirs)

    # Test 1: Generate asset url for a valid path
    test_file_path = "/tmp/data model.png"

    # Just touch the file so resolve() won't complain if strict
    os.makedirs("/tmp", exist_ok=True)
    with open(test_file_path, "w") as f:
        f.write("test")

    url = fs.asset_url(test_file_path)

    assert url.startswith("forge-asset://")

    # Ensure it's URL encoded (spaces become %20)
    assert "%20" in url

    # Should decode back to the correct path
    decoded = urllib.parse.unquote(url.replace("forge-asset://", ""))

    # It might have a leading slash so we strip it if needed or check endswith
    assert decoded.endswith(test_file_path) or decoded == test_file_path


if __name__ == "__main__":
    test_asset_url_generation()
