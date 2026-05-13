from unittest.mock import MagicMock, patch

import pytest

from forge.api.opener import OpenerAPI


@pytest.fixture
def opener():
    return OpenerAPI()


@patch("webbrowser.open")
def test_open_url(mock_open, opener):
    res = opener.open_url("https://example.com")
    assert res["ok"] is True
    mock_open.assert_called_once_with("https://example.com")


@patch("subprocess.Popen")
@patch("sys.platform", "linux")
def test_reveal_in_folder_linux(mock_popen, opener):
    with patch("os.path.exists", return_value=True):
        res = opener.reveal_in_folder("/tmp/some_file.txt")
        assert res.get("ok") is True, res.get("error")
        mock_popen.assert_called_once()


@patch("subprocess.Popen")
@patch("forge.api.opener.sys")
def test_open_path_windows(mock_sys, mock_popen, opener):
    """Test open_path on Windows by mocking the sys module inside opener."""
    mock_sys.platform = "win32"
    mock_startfile = MagicMock()
    MagicMock()

    with (
        patch("os.path.exists", return_value=True),
        patch("os.path.abspath", return_value="C:\\test.txt"),
        patch("forge.api.opener.os.startfile", mock_startfile, create=True),
    ):
        res = opener.open_path("C:\\test.txt")
        assert res.get("ok") is True, res.get("error")


def test_open_path_nonexistent(opener):
    """Test that opening a nonexistent path returns an error."""
    with patch("os.path.exists", return_value=False):
        res = opener.open_path("/nonexistent/path")
        assert res.get("ok") is False
        assert "not found" in res.get("error", "").lower()


def test_open_url_invalid(opener):
    """Test that a failing URL open returns an error."""
    with patch("webbrowser.open", side_effect=Exception("browser error")):
        res = opener.open_url("not-a-url")
        assert res.get("ok") is False
        assert "browser error" in res.get("error", "")
