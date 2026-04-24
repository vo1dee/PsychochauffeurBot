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
from modules.video_downloader import VideoDownloader, Platform, LowConfidenceMatchError


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

    def test_extract_spotify_title_artist_from_description(self):
        """Should parse both title and artist from Spotify description."""
        description = "Listen to Test Song on Spotify. Song · Test Artist · 2026"
        title, artist = (
            self.video_downloader._extract_spotify_title_artist_from_description(
                description
            )
        )
        self.assertEqual(title, "Test Song")
        self.assertEqual(artist, "Test Artist")

    def test_extract_spotify_track_id(self):
        """Should parse track id from Spotify track URL."""
        track_id = self.video_downloader._extract_spotify_track_id(
            "https://open.spotify.com/track/6P598fMrBAbflbqavz3wki?si=bb3b1880be2a442f"
        )
        self.assertEqual(track_id, "6P598fMrBAbflbqavz3wki")

    def test_normalize_spotify_title(self):
        """Should trim Spotify-specific suffixes from title."""
        normalized = self.video_downloader._normalize_spotify_title(
            "Very Noise - song and lyrics by IGORRR | Spotify"
        )
        self.assertEqual(normalized, "Very Noise")

    def test_is_generic_spotify_title(self):
        """Should detect generic Spotify page titles."""
        self.assertTrue(
            self.video_downloader._is_generic_spotify_title(
                "Spotify - Web Player: Music for everyone"
            )
        )
        self.assertFalse(self.video_downloader._is_generic_spotify_title("ADHD"))

    def test_resolve_spotify_prefers_scraped_metadata_on_mismatch(self):
        """Should prefer scraped metadata when oEmbed returns conflicting title."""

        class MockResponse:
            def __init__(self, payload):
                self.status = 200
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self, content_type=None):
                return self._payload

        class MockSession:
            def __init__(self, payload):
                self.payload = payload

            def get(self, *args, **kwargs):
                return MockResponse(self.payload)

        session = MockSession({"title": "2025 - ADHD", "author_name": "2025"})
        self.video_downloader._resolve_spotify_track_via_open_api = AsyncMock(
            return_value=(None, None, None)
        )
        self.video_downloader._resolve_spotify_via_embed = AsyncMock(
            return_value=(None, None, None)
        )
        self.video_downloader._scrape_spotify_metadata = AsyncMock(
            return_value=("ADHD", "IGORRR")
        )

        title, artist, duration = asyncio.run(
            self.video_downloader._resolve_spotify(
                session,
                "https://open.spotify.com/track/6P598fMrBAbflbqavz3wki",
            )
        )
        self.assertEqual(title, "ADHD")
        self.assertEqual(artist, "IGORRR")
        self.assertIsNone(duration)

    def test_resolve_spotify_falls_back_to_oembed_when_scrape_empty(self):
        """Should still return oEmbed metadata if scraping cannot resolve title."""

        class MockResponse:
            def __init__(self, payload):
                self.status = 200
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self, content_type=None):
                return self._payload

        class MockSession:
            def __init__(self, payload):
                self.payload = payload

            def get(self, *args, **kwargs):
                return MockResponse(self.payload)

        session = MockSession({"title": "Track Name", "author_name": "Artist Name"})
        self.video_downloader._resolve_spotify_track_via_open_api = AsyncMock(
            return_value=(None, None, None)
        )
        self.video_downloader._resolve_spotify_via_embed = AsyncMock(
            return_value=(None, None, None)
        )
        self.video_downloader._scrape_spotify_metadata = AsyncMock(
            return_value=(None, None)
        )

        title, artist, duration = asyncio.run(
            self.video_downloader._resolve_spotify(
                session, "https://open.spotify.com/track/example"
            )
        )
        self.assertEqual(title, "Track Name")
        self.assertEqual(artist, "Artist Name")
        self.assertIsNone(duration)

    def test_resolve_spotify_returns_duration_from_web_api(self):
        """Should propagate duration_s from the Web API path."""

        class MockSession:
            def get(self, *args, **kwargs):
                raise AssertionError("session.get should not be called when Web API succeeds")

        session = MockSession()
        self.video_downloader._resolve_spotify_track_via_open_api = AsyncMock(
            return_value=("ADHD", "Igorrr", 197)
        )

        title, artist, duration = asyncio.run(
            self.video_downloader._resolve_spotify(
                session,
                "https://open.spotify.com/track/6P598fMrBAbflbqavz3wki",
            )
        )
        self.assertEqual(title, "ADHD")
        self.assertEqual(artist, "Igorrr")
        self.assertEqual(duration, 197)

    def test_resolve_spotify_via_embed_parses_next_data(self):
        """Should extract title, artist, and duration from __NEXT_DATA__ JSON blob."""
        next_data = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "name": "ADHD",
                                "artists": [
                                    {"name": "Igorrr", "uri": "spotify:artist:abc"}
                                ],
                                "duration": 197000,
                            }
                        }
                    }
                }
            }
        }
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(next_data)
            + "</script>"
        )

        class MockResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def text(self):
                return html

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        title, artist, duration = asyncio.run(
            self.video_downloader._resolve_spotify_via_embed(MockSession(), "6P598fMrBAbflbqavz3wki")
        )
        self.assertEqual(title, "ADHD")
        self.assertEqual(artist, "Igorrr")
        self.assertEqual(duration, 197)

    def test_resolve_spotify_via_embed_multi_artist(self):
        """Should join multiple artist names with ', '."""
        next_data = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "name": "Collab Track",
                                "artists": [
                                    {"name": "Artist A"},
                                    {"name": "Artist B"},
                                ],
                                "duration": 180000,
                            }
                        }
                    }
                }
            }
        }
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(next_data)
            + "</script>"
        )

        class MockResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def text(self):
                return html

        class MockSession:
            def get(self, *args, **kwargs):
                return MockResponse()

        title, artist, duration = asyncio.run(
            self.video_downloader._resolve_spotify_via_embed(MockSession(), "collab123")
        )
        self.assertEqual(title, "Collab Track")
        self.assertEqual(artist, "Artist A, Artist B")
        self.assertEqual(duration, 180)

    # ── _pick_best_youtube_candidate tests ────────────────────────────────────

    def test_pick_best_candidate_selects_correct_over_popular_wrong(self):
        """Should select the Igorrr upload over the more-popular PinkPantheress hit when
        expected_artist and expected_duration are known."""
        # Igorrr - ADHD (2025): ~197s
        igorrr_candidate = {
            "id": "igorrr_id",
            "title": "Igorrr - ADHD",
            "artist": "Igorrr",
            "uploader": "Igorrr - Topic",
            "duration": 197,
            "webpage_url": "https://youtube.com/watch?v=igorrr_id",
        }
        # PinkPantheress - ADHD: ~120s, totally different artist
        pink_candidate = {
            "id": "pink_id",
            "title": "PinkPantheress - ADHD",
            "artist": "PinkPantheress",
            "uploader": "PinkPantheress",
            "duration": 120,
            "webpage_url": "https://youtube.com/watch?v=pink_id",
        }
        result = VideoDownloader._pick_best_youtube_candidate(
            [pink_candidate, igorrr_candidate],
            expected_title="ADHD",
            expected_artist="Igorrr",
            expected_duration_s=197,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "igorrr_id")

    def test_pick_best_candidate_rejects_low_confidence(self):
        """Should return None when all candidates have wrong duration AND no artist overlap."""
        wrong_candidate = {
            "id": "wrong_id",
            "title": "ADHD",
            "artist": "PinkPantheress",
            "uploader": "PinkPantheress",
            "duration": 120,  # expected ~197s → >15s miss
            "webpage_url": "https://youtube.com/watch?v=wrong_id",
        }
        result = VideoDownloader._pick_best_youtube_candidate(
            [wrong_candidate],
            expected_title="ADHD",
            expected_artist="Igorrr",
            expected_duration_s=197,
        )
        self.assertIsNone(result)

    def test_pick_best_candidate_no_rejection_when_duration_unknown(self):
        """Should return best candidate even when duration is unknown (no gate fires)."""
        candidate = {
            "id": "cand_id",
            "title": "ADHD",
            "artist": "PinkPantheress",
            "uploader": "PinkPantheress",
            "duration": 120,
            "webpage_url": "https://youtube.com/watch?v=cand_id",
        }
        result = VideoDownloader._pick_best_youtube_candidate(
            [candidate],
            expected_title="ADHD",
            expected_artist="Igorrr",
            expected_duration_s=None,  # duration unknown
        )
        # Gate doesn't fire without expected_duration_s → returns the only candidate
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "cand_id")

    def test_pick_best_candidate_topic_channel_tiebreaker(self):
        """Should prefer '- Topic' uploader channel when scores are otherwise close."""
        base_candidate = {
            "id": "base_id",
            "title": "Test Song",
            "artist": "Test Artist",
            "uploader": "Test Artist",
            "duration": 200,
            "webpage_url": "https://youtube.com/watch?v=base_id",
        }
        topic_candidate = {
            "id": "topic_id",
            "title": "Test Song",
            "artist": "Test Artist",
            "uploader": "Test Artist - Topic",
            "duration": 200,
            "webpage_url": "https://youtube.com/watch?v=topic_id",
        }
        result = VideoDownloader._pick_best_youtube_candidate(
            [base_candidate, topic_candidate],
            expected_title="Test Song",
            expected_artist="Test Artist",
            expected_duration_s=200,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "topic_id")

    def test_pick_best_candidate_multi_artist_split(self):
        """Should match when expected_artist has multiple artists separated by comma."""
        candidate = {
            "id": "collab_id",
            "title": "Collab",
            "artist": "Artist A",
            "uploader": "Artist A - Topic",
            "duration": 180,
            "webpage_url": "https://youtube.com/watch?v=collab_id",
        }
        # expected_artist includes both; candidate only lists one — should still match
        result = VideoDownloader._pick_best_youtube_candidate(
            [candidate],
            expected_title="Collab",
            expected_artist="Artist A, Artist B",
            expected_duration_s=180,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "collab_id")

    # ── Existing display-title / metadata tests ───────────────────────────────

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

    def test_compose_display_title_deduplicates_title_prefix_chain(self):
        """Should collapse title-only duplicate artist prefix chain."""
        meta = {
            "artist": None,
            "track": None,
            "title": "Test Artist - Test Artist - Test Song",
            "uploader": "",
            "webpage_url": "https://youtube.com/watch?v=abc",
        }
        display_title, performer, _ = self.video_downloader._compose_display_title(meta)
        self.assertEqual(display_title, "Test Artist - Test Song")
        self.assertEqual(performer, "Test Artist")

    def test_compose_display_title_deduplicates_uploader_fallback(self):
        """Should avoid Artist - Artist - Song in uploader fallback path."""
        meta = {
            "artist": None,
            "track": None,
            "title": "Test Artist - Test Song",
            "uploader": "Test Artist - Topic",
            "webpage_url": "https://youtube.com/watch?v=abc",
        }
        display_title, performer, _ = self.video_downloader._compose_display_title(meta)
        self.assertEqual(display_title, "Test Artist - Test Song")
        self.assertEqual(performer, "Test Artist")

    def test_normalize_telegram_audio_metadata_strips_performer_prefix(self):
        """Telegram audio title should be track-only when performer is set."""
        title, performer = self.video_downloader._normalize_telegram_audio_metadata(
            "Test Artist - Test Song", "Test Artist"
        )
        self.assertEqual(title, "Test Song")
        self.assertEqual(performer, "Test Artist")

    @unittest.skip("This test requires network access")
    def test_download_video(self):
        """Test video download functionality."""
        # This is a placeholder for a real test that would require network access
        pass


# Run the tests
if __name__ == "__main__":
    unittest.main()
