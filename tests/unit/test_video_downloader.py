import unittest
import sys
import os
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import asyncio
import pytest

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from modules.utils import extract_urls
from modules.video_downloader import VideoDownloader, Platform


class TestVideoDownloader(unittest.TestCase):
    """Test cases for the VideoDownloader class."""

    def setUp(self):
        """Set up test environment."""

        def mock_extract_urls(text):
            return ["https://www.tiktok.com/@user/video/123456789"]

        self.video_downloader = VideoDownloader(extract_urls_func=mock_extract_urls)

    def test_initialization(self):
        """Test VideoDownloader initialization."""
        self.assertIsNotNone(self.video_downloader)
        self.assertTrue(callable(self.video_downloader.extract_urls))

    def test_platform_detection(self):
        """Test platform detection from URLs."""
        tiktok_url = "https://www.tiktok.com/@user/video/123456789"
        platform = self.video_downloader._get_platform(tiktok_url)

        self.assertEqual(platform, Platform.TIKTOK)

    def test_extract_music_url_from_ffm_cd_payload(self):
        """Should decode ffm-style `cd` payload and extract Spotify URL."""
        spotify_url = "https://open.spotify.com/track/abc123"
        payload = json.dumps({"destUrl": spotify_url}).encode("utf-8")
        cd_value = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")

        extracted = self.video_downloader._extract_music_url_from_cd_param(cd_value)
        self.assertEqual(extracted, spotify_url)

    def test_normalize_music_platform_url_from_query_param(self):
        """Should extract encoded platform URL from generic wrapper query params."""
        wrapped_url = (
            "https://example.com/redirect"
            "?url=https%3A%2F%2Fopen.spotify.com%2Ftrack%2Fabc123%3Fsi%3Dxyz"
        )

        normalized = asyncio.run(
            self.video_downloader.normalize_music_platform_url(wrapped_url)
        )
        self.assertEqual(normalized, "https://open.spotify.com/track/abc123?si=xyz")

    def test_extract_spotify_artist_from_description(self):
        """Should parse artist from Spotify-style description string."""
        description = "Listen to Test Song on Spotify. Song · Test Artist · 2026"
        artist = self.video_downloader._extract_spotify_artist_from_description(
            description
        )
        self.assertEqual(artist, "Test Artist")

    def test_compose_display_title_deduplicates_artist_prefix(self):
        """Should not duplicate artist when track already includes artist prefix."""
        meta = {
            "artist": "Test Artist",
            "track": "Test Artist - Test Song",
            "title": "Test Artist - Test Song",
            "uploader": "Test Artist - Topic",
            "webpage_url": "https://youtube.com/watch?v=abc",
        }
        display_title, performer, _ = self.video_downloader._compose_display_title(meta)
        self.assertEqual(display_title, "Test Artist - Test Song")
        self.assertEqual(performer, "Test Artist")

    @unittest.skip("This test requires network access")
    def test_download_video(self):
        """Test video download functionality."""
        # This is a placeholder for a real test that would require network access
        pass


# Run the tests
if __name__ == "__main__":
    unittest.main()
