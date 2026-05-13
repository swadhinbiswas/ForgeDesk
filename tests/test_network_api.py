from unittest.mock import MagicMock, patch

import pytest

from forge.builtins.network import BuiltinNetworkAPI


@pytest.fixture
def network():
    mock_app = MagicMock()

    plugin = BuiltinNetworkAPI()
    plugin.app = mock_app
    return plugin


@patch("forge.builtins.network.requests.get")
def test_http_get(mock_get, network):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    mock_get.return_value = mock_response

    res = network.http_get("https://example.com")
    assert res.get("ok") is True, res.get("error")
    assert res.get("status") == 200
    mock_get.assert_called_once_with("https://example.com", timeout=30.0)


@patch("forge.builtins.network.requests.post")
def test_http_post_json(mock_post, network):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"created": True}
    mock_post.return_value = mock_response

    res = network.http_post_json("https://example.com", {"data": 123})
    assert res.get("ok") is True, res.get("error")
    assert res.get("status") == 201
    assert res.get("json", {}).get("created") is True
