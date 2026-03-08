"""
Pytest configuration and fixtures for Forge tests.
"""

import pytest
import sys
import os

# Add the forge-framework to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def test_dir(tmp_path_factory):
    """Create a temporary directory for test files."""
    return tmp_path_factory.mktemp("test_files")


@pytest.fixture
def sample_text_file(test_dir):
    """Create a sample text file."""
    file_path = test_dir / "sample.txt"
    file_path.write_text("This is sample content for testing.\n")
    return file_path


@pytest.fixture
def sample_json_file(test_dir):
    """Create a sample JSON file."""
    import json
    file_path = test_dir / "sample.json"
    file_path.write_text(json.dumps({"key": "value", "number": 42}))
    return file_path
