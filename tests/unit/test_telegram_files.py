from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import telegram_files as tf


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_BASE_URL", raising=False)


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE_URL", "http://telegram-bot-api:8081/")


def test_cloud_limits(cloud):
    assert not tf.local_bot_api_enabled()
    assert tf.max_upload_bytes() == 50 * tf.MB
    assert tf.max_upload_label() == "50MB"
    assert tf.upload_timeouts(1500 * tf.MB)["read_timeout"] == 60


def test_local_limits(local):
    assert tf.local_bot_api_url() == "http://telegram-bot-api:8081"
    assert tf.max_upload_bytes() == 2000 * tf.MB
    assert tf.max_upload_label() == "2000MB"


def test_local_read_timeout_scales_with_size(local):
    assert tf.upload_timeouts(10 * tf.MB)["read_timeout"] == 70
    assert tf.upload_timeouts(1500 * tf.MB)["read_timeout"] == 1560
    assert tf.upload_timeouts(10_000 * tf.MB)["read_timeout"] == 3600
    assert tf.upload_timeouts(0, read=120)["read_timeout"] == 120


def test_media_input_uses_path_only_in_local_mode(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")

    local_input = tf.media_input(f, SimpleNamespace(local_mode=True))
    assert local_input == Path(f)
    tf.close_media_input(local_input)  # no-op for paths

    handle = tf.media_input(f, SimpleNamespace(local_mode=False))
    try:
        assert handle.read() == b"x"
    finally:
        tf.close_media_input(handle)
    assert handle.closed
