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

    @staticmethod
    def _shazam_session(responses):
        """Mock aiohttp session answering by URL substring: {needle: (status, payload)}."""

        class MockResponse:
            def __init__(self, status, payload):
                self.status = status
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self, content_type=None):
                return self._payload

        class MockSession:
            def __init__(self):
                self.requested = []

            def get(self, url, *args, **kwargs):
                self.requested.append(url)
                for needle, (status, payload) in responses.items():
                    if needle in url:
                        return MockResponse(status, payload)
                return MockResponse(404, None)

        return MockSession()

    def test_shazam_is_song_only_platform(self):
        """Shazam links are recognised, but excluded from chat auto-download."""
        from modules.const import MusicPlatforms

        url = "https://www.shazam.com/track/40001020/poppin-them-thangs?referrer=share"
        self.assertTrue(self.video_downloader._is_music_platform_url(url))
        self.assertTrue(self.video_downloader._is_shazam_url(url))
        self.assertFalse(
            self.video_downloader._is_shazam_url("https://notshazam.com/track/1")
        )
        self.assertNotIn("shazam.com", MusicPlatforms.AUTO_DOWNLOAD_DOMAINS)

    def test_resolve_shazam_track_uses_api_and_itunes_duration(self):
        """/track/<id> links resolve via the Shazam API, duration via iTunes."""
        session = self._shazam_session(
            {
                "amp.shazam.com": (
                    200,
                    {
                        "title": "Poppin' Them Thangs",
                        "subtitle": "G-Unit",
                        "hub": {
                            "actions": [
                                {"type": "applemusicplay", "id": "1444177186"},
                                {"type": "uri", "uri": "https://example.com/a.m4a"},
                            ]
                        },
                    },
                ),
                "itunes.apple.com": (
                    200,
                    {
                        "results": [
                            {
                                "wrapperType": "track",
                                "trackName": "Poppin' Them Thangs",
                                "artistName": "G-Unit",
                                "trackTimeMillis": 240800,
                            }
                        ]
                    },
                ),
            }
        )

        result = asyncio.run(
            self.video_downloader._resolve_shazam(
                session,
                "https://www.shazam.com/track/40001020/poppin-them-thangs?referrer=share",
            )
        )
        self.assertEqual(result, ("Poppin' Them Thangs", "G-Unit", 240))
        self.assertTrue(session.requested[0].endswith("/track/40001020"))

    def test_resolve_shazam_track_without_duration(self):
        """A failed iTunes lookup must not lose the Shazam title/artist."""
        session = self._shazam_session(
            {"amp.shazam.com": (200, {"title": "DtMF", "subtitle": "Bad Bunny"})}
        )
        result = asyncio.run(
            self.video_downloader._resolve_shazam(
                session, "https://www.shazam.com/uk-ua/track/808381470/dtmf"
            )
        )
        self.assertEqual(result, ("DtMF", "Bad Bunny", None))

    def test_resolve_shazam_song_link_uses_itunes(self):
        """/song/<apple music id> links resolve via the iTunes lookup API."""
        session = self._shazam_session(
            {
                "itunes.apple.com": (
                    200,
                    {
                        "results": [
                            {
                                "wrapperType": "track",
                                "trackName": "DtMF",
                                "artistName": "Bad Bunny",
                                "trackTimeMillis": 237117,
                            }
                        ]
                    },
                )
            }
        )
        result = asyncio.run(
            self.video_downloader._resolve_shazam(
                session, "https://www.shazam.com/song/1787023936/dtmf"
            )
        )
        self.assertEqual(result, ("DtMF", "Bad Bunny", 237))
        self.assertEqual(len(session.requested), 1)

    def test_resolve_shazam_unknown_track(self):
        """Unknown ids (204) and non-track URLs resolve to nothing."""
        session = self._shazam_session({"amp.shazam.com": (204, None)})
        for url in (
            "https://www.shazam.com/track/99999999999/nothing",
            "https://www.shazam.com/charts/top-200/world",
        ):
            result = asyncio.run(self.video_downloader._resolve_shazam(session, url))
            self.assertEqual(result, (None, None, None))

    @staticmethod
    def _service_session_factory(health, download=None, file_bytes=b"mp3-bytes"):
        """Build a fake aiohttp.ClientSession class for the download service.

        Returns (factory, calls); calls collects (method, url, json) tuples.
        """
        calls = []

        class Content:
            async def iter_chunked(self, size):
                yield file_bytes

        class MockResponse:
            def __init__(self, status, payload=None):
                self.status = status
                self._payload = payload
                self.content = Content()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self, content_type=None):
                return self._payload

        class MockSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, url, **kwargs):
                calls.append(("GET", url, None))
                if url.endswith("/health"):
                    return MockResponse(200, health)
                return MockResponse(200)

            def post(self, url, json=None, **kwargs):
                calls.append(("POST", url, json))
                return MockResponse(200, download)

        return MockSession, calls

    def _configure_service(self):
        self.video_downloader.service_url = "https://ytdl.example.com"
        self.video_downloader.api_key = "key"

    def test_service_audio_download_success(self):
        """Audio goes through the service when it advertises audio_only."""
        self._configure_service()
        factory, calls = self._service_session_factory(
            health={"capabilities": {"audio_only": True}},
            download={
                "success": True,
                "audio_only": True,
                "file_path": "abc12345.mp3",
                "title": "G-Unit - Poppin' Them Thangs (Explicit Version)",
                "uploader": "GUnitVEVO",
                "duration": 248,
                "video_id": "lc0zKB88XPM",
                "webpage_url": "https://www.youtube.com/watch?v=lc0zKB88XPM",
            },
        )
        with tempfile.TemporaryDirectory() as music_dir, patch(
            "modules.video_downloader.MUSIC_DIR", music_dir
        ), patch("modules.video_downloader.aiohttp.ClientSession", factory):
            filename, title, performer, webpage_url, video_id = asyncio.run(
                self.video_downloader._download_youtube_by_url(
                    "https://www.youtube.com/watch?v=lc0zKB88XPM"
                )
            )
            self.assertEqual(filename, os.path.join(music_dir, "abc12345.mp3"))
            with open(filename, "rb") as f:
                self.assertEqual(f.read(), b"mp3-bytes")

        self.assertIn("Poppin' Them Thangs", title)
        self.assertEqual(webpage_url, "https://www.youtube.com/watch?v=lc0zKB88XPM")
        self.assertEqual(video_id, "lc0zKB88XPM")
        post = next(c for c in calls if c[0] == "POST")
        self.assertEqual(post[1], "https://ytdl.example.com/download")
        self.assertTrue(post[2]["audio_only"])
        self.assertIn(("GET", "https://ytdl.example.com/files/abc12345.mp3", None), calls)

    def test_service_audio_skipped_when_capability_missing(self):
        """An older service (no capability flag) must not be sent audio requests."""
        self._configure_service()
        factory, calls = self._service_session_factory(health={"status": "healthy"})
        with patch("modules.video_downloader.aiohttp.ClientSession", factory):
            result = asyncio.run(
                self.video_downloader._download_audio_from_service("ytsearch1:x")
            )
            # Second call uses the cached answer instead of asking /health again.
            asyncio.run(
                self.video_downloader._download_audio_from_service("ytsearch1:x")
            )
        self.assertEqual(result, (None, None, None, None, None))
        self.assertEqual([c[0] for c in calls], ["GET"])

    def test_service_audio_rejects_video_response(self):
        """A response without the audio_only marker is treated as a failure."""
        self._configure_service()
        factory, calls = self._service_session_factory(
            health={"capabilities": {"audio_only": True}},
            download={"success": True, "file_path": "abc12345.mp4", "title": "x"},
        )
        with patch("modules.video_downloader.aiohttp.ClientSession", factory):
            result = asyncio.run(
                self.video_downloader._download_audio_from_service("ytsearch1:x")
            )
        self.assertEqual(result, (None, None, None, None, None))
        self.assertFalse(any("/files/" in c[1] for c in calls))

    def test_download_by_url_falls_back_to_local_ytdlp(self):
        """When the service cannot do audio, local yt-dlp is still used."""
        self.video_downloader._download_audio_from_service = AsyncMock(
            return_value=(None, None, None, None, None)
        )
        self.video_downloader._run_yt_dlp_subprocess = AsyncMock(
            return_value=(1, b"", b"ERROR: nope")
        )
        result = asyncio.run(
            self.video_downloader._download_youtube_by_url("ytsearch1:x")
        )
        self.assertEqual(result, (None, None, None, None, None))
        self.video_downloader._run_yt_dlp_subprocess.assert_awaited_once()

    def test_fast_youtube_search_is_flat(self):
        """Search must not extract each result (blocked on datacenter IPs)."""
        line = json.dumps({"id": "abc", "title": "T", "uploader": "U", "duration": 10})
        self.video_downloader._run_yt_dlp_subprocess = AsyncMock(
            return_value=(0, line.encode(), b"")
        )
        results = asyncio.run(self.video_downloader.fast_youtube_search("q", limit=3))
        cmd = self.video_downloader._run_yt_dlp_subprocess.await_args.args[0]
        self.assertIn("--flat-playlist", cmd)
        self.assertNotIn("--skip-download", cmd)
        self.assertEqual(results[0]["id"], "abc")

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
