from unittest.mock import MagicMock

from forge.channels import ChannelManager


def test_channel_manager_create():
    cm = ChannelManager()
    channel_id = cm.create("test_channel")
    assert isinstance(channel_id, str)
    assert channel_id in cm._channels


def test_channel_push():
    cm = ChannelManager()
    mock_proxy = MagicMock()
    channel_id = cm.create("test_channel", mock_proxy)

    success = cm.send(channel_id, {"data": 123})
    assert success is True
    mock_proxy.evaluate_script.assert_called_once()
    script = mock_proxy.evaluate_script.call_args[0][0]
    assert "channel_id" in script
    assert "123" in script


def test_channel_close():
    cm = ChannelManager()
    mock_proxy = MagicMock()
    channel_id = cm.create("test_channel", mock_proxy)

    success = cm.close(channel_id)
    assert success is True
    assert cm._channels[channel_id].closed is True

    mock_proxy.evaluate_script.assert_called_once()
    script = mock_proxy.evaluate_script.call_args[0][0]
    assert '"done":true' in script


def test_channel_manager_close_all():
    cm = ChannelManager()
    c1 = cm.create("c1")
    c2 = cm.create("c2")
    cm.close_all()
    assert cm._channels[c1].closed is True
    assert cm._channels[c2].closed is True
