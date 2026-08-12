from unittest.mock import Mock

from modules.video_cache import VideoCache, normalize_url


def test_normalize_url_removes_social_tracking_and_aliases():
    assert (
        normalize_url("https://TikTok.com/a/?is_from_webapp=1#x")
        == "https://tiktok.com/a"
    )
    assert normalize_url("https://fixupx.com/user/status/1") == normalize_url(
        "https://x.com/user/status/1/"
    )
    assert normalize_url("https://twitter.com/user/status/1") == normalize_url(
        "https://x.com/user/status/1"
    )
    assert normalize_url("https://toinstagram.com/p/a") == "https://instagram.com/p/a"


def test_normalize_url_preserves_youtube_identity():
    assert (
        normalize_url("https://youtube.com/watch?v=A&t=5&si=x")
        == "https://youtube.com/watch?v=A"
    )
    assert normalize_url("https://youtube.com/watch?v=A") != normalize_url(
        "https://youtube.com/watch?v=B"
    )
    assert normalize_url("https://youtube.com/shorts/A") == normalize_url(
        "https://youtu.be/A"
    )
    assert normalize_url("https://youtu.be/shorts/A") == normalize_url(
        "https://youtube.com/watch?v=A"
    )
    assert normalize_url("https://youtube.com/watch?feature=share") == (
        "https://youtube.com/watch?feature=share"
    )
    assert normalize_url("garbage\\") == "garbage"


def test_cache_persists_and_evicts_equivalent_urls(tmp_path):
    path = tmp_path / "video-cache.json"
    cache = VideoCache(str(path))
    cache.set("https://fixupx.com/user/status/1", "file-1", "Title", "video")
    assert cache.get("https://x.com/user/status/1")["file_id"] == "file-1"
    assert (
        VideoCache(str(path)).get("https://twitter.com/user/status/1")["title"]
        == "Title"
    )
    cache.evict("https://x.com/user/status/1")
    assert cache.get("https://fixupx.com/user/status/1") is None


def test_cache_tolerates_invalid_data_and_writes(tmp_path, monkeypatch):
    corrupted = tmp_path / "bad.json"
    corrupted.write_text("not json")
    cache = VideoCache(str(corrupted))
    assert cache.get("https://example.com") is None
    cache.set("https://example.com", Mock(), "title", "video")
    cache.set("https://example.com", "", "title", "video")
    cache.set("https://example.com", "id", "title", "audio")
    assert cache.get("https://example.com") is None

    monkeypatch.setattr("modules.video_cache._CAP", 1)
    cache.set("https://example.com/one", "one", "one", "video")
    cache.set("https://example.com/two", "two", "two", "photo")
    assert cache.get("https://example.com/one") is None
    assert cache.get("https://example.com/two")["media_kind"] == "photo"


def test_cache_unwritable_path_never_raises(tmp_path):
    cache = VideoCache(str(tmp_path / "missing" / "video-cache.json"))
    cache.set("https://example.com", "id", "title", "video")
    cache.evict("https://example.com")
