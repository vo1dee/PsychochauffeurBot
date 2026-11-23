import os

from modules.video_downloader import VideoDownloader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_COOKIES = os.path.join(PROJECT_ROOT, "data", "youtube_cookies.txt")
ROOT_COOKIES = os.path.join(PROJECT_ROOT, "youtube_cookies.txt")


def _path(monkeypatch, existing):
    monkeypatch.setattr(os.path, "isfile", lambda p: p in existing)
    return VideoDownloader.__new__(VideoDownloader)._youtube_cookies_path()


def test_env_var_wins(monkeypatch, tmp_path):
    env_file = str(tmp_path / "yt.txt")
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", env_file)
    assert _path(monkeypatch, {env_file, DATA_COOKIES}) == env_file


def test_missing_env_file_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/nope/yt.txt")
    assert _path(monkeypatch, {DATA_COOKIES}) is None


def test_data_dir_before_project_root(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    assert _path(monkeypatch, {DATA_COOKIES, ROOT_COOKIES}) == DATA_COOKIES


def test_project_root_fallback(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    assert _path(monkeypatch, {ROOT_COOKIES}) == ROOT_COOKIES


def test_none_when_absent(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    assert _path(monkeypatch, set()) is None
