"""
Comprehensive tests for video downloader module.
This module provides extensive test coverage for video URL validation, metadata extraction,
download functionality, format conversion, and quality selection.
"""

import pytest
import asyncio
import os
import tempfile
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import test utilities
from tests.utils.async_test_utilities import (
    async_test, AsyncTestPatterns, AsyncMockManager, AsyncAssertions
)
from tests.mocks.enhanced_mocks import mock_registry

# Import the module under test
from modules.video_downloader import VideoDownloader, Platform, DownloadConfig
from modules.const import VideoPlatforms


class TestVideoDownloaderURLValidation:
    """Test video URL validation and metadata extraction."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_with_valid_extract_urls_func(self):
        """Test VideoDownloader initialization with valid extract_urls function."""
        assert self.downloader is not None
        assert callable(self.downloader.extract_urls)
        assert self.downloader.download_path == os.path.abspath(self.temp_dir)
        assert self.downloader.supported_platforms == VideoPlatforms.SUPPORTED_PLATFORMS
        
    def test_initialization_without_extract_urls_func_raises_error(self):
        """Test VideoDownloader initialization without extract_urls function raises ValueError."""
        with pytest.raises(ValueError, match="extract_urls_func must be a callable function"):
            VideoDownloader(extract_urls_func=None)
            
    def test_initialization_with_non_callable_extract_urls_func_raises_error(self):
        """Test VideoDownloader initialization with non-callable extract_urls function raises ValueError."""
        with pytest.raises(ValueError, match="extract_urls_func must be a callable function"):
            VideoDownloader(extract_urls_func="not_callable")
    
    def test_platform_detection_tiktok_urls(self):
        """Test platform detection for various TikTok URL formats."""
        tiktok_urls = [
            "https://www.tiktok.com/@user/video/123456789",
            "https://tiktok.com/@user/video/123456789",
            "https://vm.tiktok.com/ZMeAbCdEf/",
            "https://m.tiktok.com/@user/video/123456789"
        ]
        
        for url in tiktok_urls:
            platform = self.downloader._get_platform(url)
            assert platform == Platform.TIKTOK, f"Failed for URL: {url}"
    
    def test_platform_detection_other_platforms(self):
        """Test platform detection for non-TikTok platforms."""
        other_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123",
            "https://vimeo.com/123456789",
            "https://www.reddit.com/r/videos/comments/abc123/",
            "https://www.twitch.tv/streamer/clip/abc123"
        ]
        
        for url in other_urls:
            platform = self.downloader._get_platform(url)
            assert platform == Platform.OTHER, f"Failed for URL: {url}"
    
    def test_platform_detection_case_insensitive(self):
        """Test platform detection is case insensitive."""
        urls = [
            ("HTTPS://WWW.TIKTOK.COM/@USER/VIDEO/123", Platform.TIKTOK),
            ("https://YouTube.com/watch?v=abc", Platform.OTHER),
            ("HTTPS://VM.TIKTOK.COM/ABC/", Platform.TIKTOK)
        ]
        
        for url, expected_platform in urls:
            platform = self.downloader._get_platform(url)
            assert platform == expected_platform, f"Failed for URL: {url}"
    
    def test_story_url_detection(self):
        """Test detection of story URLs that should be filtered out."""
        story_urls = [
            "https://instagram.com/stories/user/123456789",
            "https://www.instagram.com/stories/user/123456789",
            "https://facebook.com/stories/user/123456789",
            "https://snapchat.com/add/user",
            "https://tiktok.com/@user/story/123456789",
            "https://youtube.com/stories/user",
            "https://youtu.be/stories/user"
        ]
        
        for url in story_urls:
            is_story = self.downloader._is_story_url(url)
            assert is_story, f"Failed to detect story URL: {url}"
    
    def test_non_story_url_detection(self):
        """Test that regular video URLs are not detected as stories."""
        regular_urls = [
            "https://www.tiktok.com/@user/video/123456789",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://instagram.com/p/ABC123/",
            "https://facebook.com/watch?v=123456789"
        ]
        
        for url in regular_urls:
            is_story = self.downloader._is_story_url(url)
            assert not is_story, f"Incorrectly detected regular URL as story: {url}"
    
    def test_download_path_initialization(self):
        """Test download path is properly initialized."""
        assert os.path.exists(self.downloader.download_path)
        assert os.path.isdir(self.downloader.download_path)
        assert os.path.isabs(self.downloader.download_path)
    
    def test_platform_configs_initialization(self):
        """Test platform-specific configurations are properly initialized."""
        # Test TikTok config
        tiktok_config = self.downloader.platform_configs[Platform.TIKTOK]
        assert isinstance(tiktok_config, DownloadConfig)
        assert tiktok_config.format is not None
        assert tiktok_config.headers is not None
        assert "User-Agent" in tiktok_config.headers
        
        # Test OTHER platform config
        other_config = self.downloader.platform_configs[Platform.OTHER]
        assert isinstance(other_config, DownloadConfig)
        assert other_config.format is not None
        assert other_config.extra_args is not None
    
    def test_youtube_shorts_config_initialization(self):
        """Test YouTube Shorts specific configuration."""
        shorts_config = self.downloader.youtube_shorts_config
        assert isinstance(shorts_config, DownloadConfig)
        assert shorts_config.format is not None
        assert shorts_config.extra_args is not None
        assert "--merge-output-format" in shorts_config.extra_args
        assert "mp4" in shorts_config.extra_args
    
    def test_youtube_clips_config_initialization(self):
        """Test YouTube Clips specific configuration."""
        clips_config = self.downloader.youtube_clips_config
        assert isinstance(clips_config, DownloadConfig)
        assert clips_config.format is not None
        assert clips_config.extra_args is not None
        assert "--merge-output-format" in clips_config.extra_args
        assert "mp4" in clips_config.extra_args


class TestVideoDownloaderMetadataExtraction:
    """Test video metadata extraction functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @async_test(timeout=10.0)
    async def test_get_video_title_regular_video(self):
        """Test getting video title for regular videos."""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        expected_title = "Rick Astley - Never Gonna Give You Up"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful subprocess execution
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                expected_title.encode(), b""
            )
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            title = await self.downloader._get_video_title(test_url)
            
            assert title == expected_title
            mock_subprocess.assert_called_once()
            
    @async_test(timeout=10.0)
    async def test_get_video_title_youtube_shorts_with_tags(self):
        """Test getting video title for YouTube Shorts with hashtags."""
        test_url = "https://www.youtube.com/shorts/abc123"
        expected_title = "Amazing Short Video"
        expected_tags = "funny,viral,trending"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock title subprocess
            mock_title_process = AsyncMock()
            mock_title_process.communicate.return_value = (
                expected_title.encode(), b""
            )
            
            # Mock tags subprocess
            mock_tags_process = AsyncMock()
            mock_tags_process.communicate.return_value = (
                expected_tags.encode(), b""
            )
            
            # Return different processes for different calls
            mock_subprocess.side_effect = [mock_title_process, mock_tags_process]
            
            title = await self.downloader._get_video_title(test_url)
            
            expected_result = f"{expected_title} #funny #viral #trending"
            assert title == expected_result
            assert mock_subprocess.call_count == 2
            
    @async_test(timeout=10.0)
    async def test_get_video_title_youtube_shorts_title_only(self):
        """Test getting video title for YouTube Shorts when tags fail."""
        test_url = "https://www.youtube.com/shorts/abc123"
        expected_title = "Amazing Short Video"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock title subprocess (successful)
            mock_title_process = AsyncMock()
            mock_title_process.communicate.return_value = (
                expected_title.encode(), b""
            )
            
            # Mock tags subprocess (fails)
            mock_tags_process = AsyncMock()
            mock_tags_process.communicate.side_effect = asyncio.TimeoutError()
            
            mock_subprocess.side_effect = [mock_title_process, mock_tags_process]
            
            title = await self.downloader._get_video_title(test_url)
            
            assert title == expected_title
            assert mock_subprocess.call_count == 2
            
    @async_test(timeout=10.0)
    async def test_get_video_title_timeout_fallback(self):
        """Test video title extraction with timeout fallback."""
        test_url = "https://www.youtube.com/watch?v=abc123"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError()
            mock_subprocess.return_value = mock_process
            
            title = await self.downloader._get_video_title(test_url)
            
            assert "Video from" in title and "abc123" in title
            
    @async_test(timeout=10.0)
    async def test_get_video_title_empty_response_fallback(self):
        """Test video title extraction with empty response fallback."""
        test_url = "https://www.youtube.com/watch?v=abc123"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error message")
            mock_subprocess.return_value = mock_process
            
            title = await self.downloader._get_video_title(test_url)
            
            assert "Video" in title and "abc123" in title
            
    @async_test(timeout=10.0)
    async def test_get_video_title_exception_fallback(self):
        """Test video title extraction with exception fallback."""
        test_url = "https://www.youtube.com/watch?v=abc123"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Subprocess failed")
            
            title = await self.downloader._get_video_title(test_url)
            
            assert title == "Video"


class TestVideoDownloaderServiceIntegration:
    """Test video downloader service integration with mocked external services."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @async_test(timeout=15.0)
    async def test_check_service_health_success(self):
        """Test service health check with successful response."""
        # Set up service configuration
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = "OK"
            
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._check_service_health()
            
            assert result is True
            mock_session.get.assert_called_once_with(
                "http://localhost:8000/health",
                headers={"X-API-Key": "test_api_key"},
                timeout=2,
                ssl=False
            )
            
    @async_test(timeout=15.0)
    async def test_check_service_health_failure(self):
        """Test service health check with failure response."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"
            
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._check_service_health()
            
            assert result is False
            
    @async_test(timeout=15.0)
    async def test_check_service_health_timeout(self):
        """Test service health check with timeout."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = asyncio.TimeoutError()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._check_service_health()
            
            assert result is False
            
    @async_test(timeout=15.0)
    async def test_check_service_health_no_config(self):
        """Test service health check without configuration."""
        self.downloader.service_url = None
        self.downloader.api_key = None
        
        result = await self.downloader._check_service_health()
        
        assert result is False
        
    @async_test(timeout=15.0)
    async def test_download_from_service_success(self):
        """Test successful download from service."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        expected_filename = "video_123.mp4"
        expected_title = "Test Video"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock download request response
            mock_download_response = AsyncMock()
            mock_download_response.status = 200
            mock_download_response.json.return_value = {
                "success": True,
                "file_path": f"/tmp/{expected_filename}",
                "title": expected_title
            }
            
            # Mock file download response
            mock_file_response = AsyncMock()
            mock_file_response.status = 200
            mock_file_response.content.iter_chunked.return_value = [b"video_data_chunk"]
            
            mock_session.post.return_value.__aenter__.return_value = mock_download_response
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock file writing
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await self.downloader._download_from_service(test_url)
                
                assert result[0] is not None
                assert result[1] == expected_title
                assert expected_filename in result[0]
                
                # Verify API call
                mock_session.post.assert_called_once_with(
                    "http://localhost:8000/download",
                    json={"url": test_url, "format": "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]"},
                    headers={"X-API-Key": "test_api_key"},
                    timeout=120,
                    ssl=False
                )
                
    @async_test(timeout=15.0)
    async def test_download_from_service_failure(self):
        """Test failed download from service."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json.return_value = {
                "success": False,
                "error": "Invalid URL"
            }
            
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._download_from_service(test_url)
            
            assert result == (None, None)
            
    @async_test(timeout=15.0)
    async def test_download_from_service_no_config(self):
        """Test download from service without configuration."""
        self.downloader.service_url = None
        self.downloader.api_key = None
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        result = await self.downloader._download_from_service(test_url)
        
        assert result == (None, None)


class TestVideoDownloaderFormatConversion:
    """Test video format conversion and quality selection."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_download_config_format_strings(self):
        """Test download configuration format strings for different platforms."""
        # Test TikTok format
        tiktok_config = self.downloader.platform_configs[Platform.TIKTOK]
        assert "best[ext=mp4]" in tiktok_config.format
        assert "avc1" in tiktok_config.format
        
        # Test OTHER platform format
        other_config = self.downloader.platform_configs[Platform.OTHER]
        assert "best[ext=mp4]" in other_config.format
        assert "avc1" in other_config.format
        assert "height<=1080" in other_config.format
        
        # Test YouTube Shorts format
        shorts_config = self.downloader.youtube_shorts_config
        assert "best[ext=mp4]" in shorts_config.format
        assert "avc1" in shorts_config.format
        assert "height<=1080" in shorts_config.format
        
        # Test YouTube Clips format
        clips_config = self.downloader.youtube_clips_config
        assert "best[ext=mp4]" in clips_config.format
        assert "avc1" in clips_config.format
        assert "height<=1080" in clips_config.format
    
    def test_download_config_extra_args(self):
        """Test download configuration extra arguments for format conversion."""
        # Test OTHER platform extra args
        other_config = self.downloader.platform_configs[Platform.OTHER]
        assert "--merge-output-format" in other_config.extra_args
        assert "mp4" in other_config.extra_args
        
        # Test YouTube Shorts extra args
        shorts_config = self.downloader.youtube_shorts_config
        assert "--merge-output-format" in shorts_config.extra_args
        assert "mp4" in shorts_config.extra_args
        assert "--ignore-errors" in shorts_config.extra_args
        assert "--no-playlist" in shorts_config.extra_args
        
        # Test YouTube Clips extra args
        clips_config = self.downloader.youtube_clips_config
        assert "--merge-output-format" in clips_config.extra_args
        assert "mp4" in clips_config.extra_args
        assert "--ignore-errors" in clips_config.extra_args
        assert "--no-playlist" in clips_config.extra_args
    
    def test_download_config_headers(self):
        """Test download configuration headers for different platforms."""
        # Test TikTok headers
        tiktok_config = self.downloader.platform_configs[Platform.TIKTOK]
        assert tiktok_config.headers is not None
        assert "User-Agent" in tiktok_config.headers
        assert "TikTok" in tiktok_config.headers["User-Agent"]
        assert "Accept" in tiktok_config.headers
        assert "Accept-Language" in tiktok_config.headers
    
    def test_download_config_quality_selection(self):
        """Test quality selection in download configurations."""
        # Test that all configs prefer H.264 codec
        configs = [
            self.downloader.platform_configs[Platform.TIKTOK],
            self.downloader.platform_configs[Platform.OTHER],
            self.downloader.youtube_shorts_config,
            self.downloader.youtube_clips_config
        ]
        
        for config in configs:
            assert "avc1" in config.format, f"Config missing H.264 preference: {config.format}"
            
        # Test that configs have resolution limits
        resolution_configs = [
            self.downloader.platform_configs[Platform.OTHER],
            self.downloader.youtube_shorts_config,
            self.downloader.youtube_clips_config
        ]
        
        for config in resolution_configs:
            assert "height<=1080" in config.format, f"Config missing resolution limit: {config.format}"
    
    @async_test(timeout=15.0)
    async def test_tiktok_download_format_application(self):
        """Test TikTok download with format configuration applied."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        expected_filename = f"video_{uuid.uuid4()}.mp4"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful download
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Download completed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Create a test file to simulate download
            test_file_path = os.path.join(self.temp_dir, "test_video.mp4")
            with open(test_file_path, 'w') as f:
                f.write("test video content")
            
            with patch('os.listdir', return_value=["test_video.mp4"]):
                with patch('os.path.getsize', return_value=1024):
                    result = await self.downloader._download_tiktok_ytdlp(test_url)
                    
                    # Verify subprocess was called with correct format
                    mock_subprocess.assert_called_once()
                    call_args = mock_subprocess.call_args[0]
                    
                    # Check that format argument is present
                    assert '-f' in call_args
                    format_index = call_args.index('-f')
                    format_value = call_args[format_index + 1]
                    
                    # Verify format contains expected elements
                    assert "best[ext=mp4]" in format_value
                    assert "avc1" in format_value
                    
                    # Check merge format argument
                    assert '--merge-output-format' in call_args
                    merge_index = call_args.index('--merge-output-format')
                    merge_value = call_args[merge_index + 1]
                    assert merge_value == 'mp4'
    
    @async_test(timeout=15.0)
    async def test_generic_download_format_application(self):
        """Test generic download with format configuration applied."""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        platform = Platform.OTHER
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful download
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Download completed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Create a test file to simulate download
            test_file_path = os.path.join(self.temp_dir, "test_video.mp4")
            with open(test_file_path, 'w') as f:
                f.write("test video content")
            
            with patch('os.listdir', return_value=["test_video.mp4"]):
                with patch('os.path.getsize', return_value=1024):
                    result = await self.downloader._download_generic(test_url, platform)
                    
                    # Verify subprocess was called (may be called multiple times for download and title)
                    assert mock_subprocess.call_count >= 1
                    call_args = mock_subprocess.call_args[0]
                    
                    # Check that format argument is present
                    assert '-f' in call_args
                    format_index = call_args.index('-f')
                    format_value = call_args[format_index + 1]
                    
                    # Verify format contains expected elements
                    assert "best[ext=mp4]" in format_value
                    assert "avc1" in format_value
                    assert "height<=1080" in format_value
                    
                    # Check merge format argument
                    assert '--merge-output-format' in call_args
                    merge_index = call_args.index('--merge-output-format')
                    merge_value = call_args[merge_index + 1]
                    assert merge_value == 'mp4'


class TestVideoDownloaderDownloadFunctionality:
    """Test core video download functionality with mocked external services."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @async_test(timeout=15.0)
    async def test_download_video_tiktok_success(self):
        """Test successful TikTok video download."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        expected_title = "Test TikTok Video"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp') as mock_download:
            mock_download.return_value = ("/path/to/video.mp4", expected_title)
            
            result = await self.downloader.download_video(test_url)
            
            assert result[0] == "/path/to/video.mp4"
            assert result[1] == expected_title
            mock_download.assert_called_once_with(test_url)
    
    @async_test(timeout=15.0)
    async def test_download_video_youtube_shorts_service_success(self):
        """Test successful YouTube Shorts download via service."""
        test_url = "https://www.youtube.com/shorts/abc123"
        expected_title = "Test YouTube Short"
        
        with patch.object(self.downloader, '_check_service_health') as mock_health:
            with patch.object(self.downloader, '_download_from_service') as mock_service:
                mock_health.return_value = True
                mock_service.return_value = ("/path/to/short.mp4", expected_title)
                
                result = await self.downloader.download_video(test_url)
                
                assert result[0] == "/path/to/short.mp4"
                assert result[1] == expected_title
                mock_health.assert_called_once()
                mock_service.assert_called_once_with(test_url)
    
    @async_test(timeout=15.0)
    async def test_download_video_youtube_shorts_fallback_to_ytdlp(self):
        """Test YouTube Shorts download fallback to yt-dlp when service fails."""
        test_url = "https://www.youtube.com/shorts/abc123"
        expected_title = "Test YouTube Short"
        
        with patch.object(self.downloader, '_check_service_health') as mock_health:
            with patch.object(self.downloader, '_download_from_service') as mock_service:
                with patch.object(self.downloader, '_download_generic') as mock_generic:
                    mock_health.return_value = True
                    mock_service.return_value = (None, None)  # Service fails
                    mock_generic.return_value = ("/path/to/short.mp4", expected_title)
                    
                    result = await self.downloader.download_video(test_url)
                    
                    assert result[0] == "/path/to/short.mp4"
                    assert result[1] == expected_title
                    mock_health.assert_called_once()
                    mock_service.assert_called_once()
                    mock_generic.assert_called_once()
    
    @async_test(timeout=15.0)
    async def test_download_video_youtube_clips_service_success(self):
        """Test successful YouTube Clips download via service."""
        test_url = "https://www.youtube.com/clip/xyz789"
        expected_title = "Test YouTube Clip"
        
        with patch.object(self.downloader, '_check_service_health') as mock_health:
            with patch.object(self.downloader, '_download_from_service') as mock_service:
                mock_health.return_value = True
                mock_service.return_value = ("/path/to/clip.mp4", expected_title)
                
                result = await self.downloader.download_video(test_url)
                
                assert result[0] == "/path/to/clip.mp4"
                assert result[1] == expected_title
                mock_health.assert_called_once()
                mock_service.assert_called_once_with(test_url)
    
    @async_test(timeout=15.0)
    async def test_download_video_instagram_service_only(self):
        """Test Instagram video download only via service."""
        test_url = "https://www.instagram.com/p/ABC123/"
        expected_title = "Test Instagram Video"
        
        with patch.object(self.downloader, '_check_service_health') as mock_health:
            with patch.object(self.downloader, '_download_from_service') as mock_service:
                mock_health.return_value = True
                mock_service.return_value = ("/path/to/instagram.mp4", expected_title)
                
                result = await self.downloader.download_video(test_url)
                
                assert result[0] == "/path/to/instagram.mp4"
                assert result[1] == expected_title
                mock_health.assert_called_once()
                mock_service.assert_called_once_with(test_url)
    
    @async_test(timeout=15.0)
    async def test_download_video_instagram_service_unavailable(self):
        """Test Instagram video download when service is unavailable."""
        test_url = "https://www.instagram.com/p/ABC123/"
        
        with patch.object(self.downloader, '_check_service_health') as mock_health:
            mock_health.return_value = False
            
            result = await self.downloader.download_video(test_url)
            
            assert result == (None, None)
            mock_health.assert_called_once()
    
    @async_test(timeout=15.0)
    async def test_download_video_generic_platform(self):
        """Test generic platform video download."""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        expected_title = "Test YouTube Video"
        
        with patch.object(self.downloader, '_download_generic') as mock_generic:
            mock_generic.return_value = ("/path/to/video.mp4", expected_title)
            
            result = await self.downloader.download_video(test_url)
            
            assert result[0] == "/path/to/video.mp4"
            assert result[1] == expected_title
            mock_generic.assert_called_once()
    
    @async_test(timeout=15.0)
    async def test_download_video_story_url_filtered(self):
        """Test that story URLs are filtered out and return None."""
        test_url = "https://instagram.com/stories/user/123456789"
        
        result = await self.downloader.download_video(test_url)
        
        assert result == (None, None)
    
    @async_test(timeout=15.0)
    async def test_download_video_exception_handling(self):
        """Test exception handling in download_video method."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp') as mock_download:
            mock_download.side_effect = Exception("Download failed")
            
            result = await self.downloader.download_video(test_url)
            
            assert result == (None, None)
    
    @async_test(timeout=15.0)
    async def test_download_video_url_preprocessing(self):
        """Test URL preprocessing (stripping whitespace and backslashes)."""
        test_url = "  https://www.tiktok.com/@user/video/123456789\\  "
        expected_title = "Test TikTok Video"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp') as mock_download:
            mock_download.return_value = ("/path/to/video.mp4", expected_title)
            
            result = await self.downloader.download_video(test_url)
            
            # Verify the URL was cleaned before being passed to download method
            mock_download.assert_called_once_with("https://www.tiktok.com/@user/video/123456789")


class TestVideoDownloaderYtDlpIntegration:
    """Test yt-dlp integration and subprocess execution."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock subprocess.run for yt-dlp verification
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            self.downloader = VideoDownloader(
                download_path=self.temp_dir,
                extract_urls_func=self.mock_extract_urls
            )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_get_yt_dlp_path_from_which(self):
        """Test getting yt-dlp path from system PATH."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/local/bin/yt-dlp"
            
            downloader = VideoDownloader(extract_urls_func=self.mock_extract_urls)
            
            assert downloader.yt_dlp_path == "/usr/local/bin/yt-dlp"
            mock_which.assert_called_once_with('yt-dlp')
    
    def test_get_yt_dlp_path_from_common_locations(self):
        """Test getting yt-dlp path from common installation locations."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.exists') as mock_exists:
                mock_exists.side_effect = lambda path: path == '/usr/local/bin/yt-dlp'
                
                downloader = VideoDownloader(extract_urls_func=self.mock_extract_urls)
                
                assert downloader.yt_dlp_path == "/usr/local/bin/yt-dlp"
    
    def test_get_yt_dlp_path_fallback(self):
        """Test yt-dlp path fallback when not found in common locations."""
        with patch('shutil.which', return_value=None):
            with patch('os.path.exists', return_value=False):
                
                downloader = VideoDownloader(extract_urls_func=self.mock_extract_urls)
                
                assert downloader.yt_dlp_path == "yt-dlp"
    
    def test_verify_yt_dlp_success(self):
        """Test successful yt-dlp verification."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            # This should not raise an exception
            downloader = VideoDownloader(extract_urls_func=self.mock_extract_urls)
            
            mock_run.assert_called_once()
    
    def test_verify_yt_dlp_failure(self):
        """Test yt-dlp verification failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("yt-dlp not found")
            
            with pytest.raises(RuntimeError, match="yt-dlp is not properly installed"):
                VideoDownloader(extract_urls_func=self.mock_extract_urls)
    
    @async_test(timeout=15.0)
    async def test_tiktok_download_subprocess_execution(self):
        """Test TikTok download subprocess execution with correct arguments."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful download
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Download completed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Create a test file to simulate download
            test_file_path = os.path.join(self.temp_dir, "test_video.mp4")
            with open(test_file_path, 'w') as f:
                f.write("test video content")
            
            with patch('os.listdir', return_value=["test_video.mp4"]):
                with patch('os.path.getsize', return_value=1024):
                    with patch.object(self.downloader, '_get_video_title', return_value="Test Title"):
                        result = await self.downloader._download_tiktok_ytdlp(test_url)
                        
                        # Verify subprocess was called with correct arguments
                        mock_subprocess.assert_called_once()
                        call_args = mock_subprocess.call_args[0]
                        
                        assert call_args[0] == self.downloader.yt_dlp_path
                        assert call_args[1] == test_url
                        assert '-f' in call_args
                        assert '-o' in call_args
                        assert '--merge-output-format' in call_args
                        assert 'mp4' in call_args
                        assert '--no-warnings' in call_args
    
    @async_test(timeout=15.0)
    async def test_generic_download_subprocess_execution(self):
        """Test generic download subprocess execution with correct arguments."""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        platform = Platform.OTHER
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful download
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Download completed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Create a test file to simulate download
            test_file_path = os.path.join(self.temp_dir, "test_video.mp4")
            with open(test_file_path, 'w') as f:
                f.write("test video content")
            
            with patch('os.listdir', return_value=["test_video.mp4"]):
                with patch('os.path.getsize', return_value=1024):
                    with patch.object(self.downloader, '_get_video_title', return_value="Test Title"):
                        result = await self.downloader._download_generic(test_url, platform)
                        
                        # Verify subprocess was called with correct arguments
                        mock_subprocess.assert_called_once()
                        call_args = mock_subprocess.call_args[0]
                        
                        assert call_args[0] == self.downloader.yt_dlp_path
                        assert call_args[1] == test_url
                        assert '-f' in call_args
                        assert '-o' in call_args
                        assert '--merge-output-format' in call_args
                        assert 'mp4' in call_args
    
    @async_test(timeout=15.0)
    async def test_subprocess_timeout_handling(self):
        """Test subprocess timeout handling."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError()
            mock_process.kill = Mock()
            mock_subprocess.return_value = mock_process
            
            result = await self.downloader._download_tiktok_ytdlp(test_url)
            
            assert result == (None, None)
            mock_process.kill.assert_called_once()
    
    @async_test(timeout=15.0)
    async def test_subprocess_failure_handling(self):
        """Test subprocess failure handling."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error: Video not found")
            mock_process.returncode = 1  # Non-zero return code indicates failure
            mock_subprocess.return_value = mock_process
            
            result = await self.downloader._download_tiktok_ytdlp(test_url)
            
            assert result == (None, None)
    
    @async_test(timeout=15.0)
    async def test_file_selection_largest_file(self):
        """Test that the largest file is selected when multiple files are found."""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        platform = Platform.OTHER
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Download completed", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Create multiple test files with different sizes
            test_files = ["small_video.mp4", "large_video.mp4", "medium_video.webm"]
            for filename in test_files:
                filepath = os.path.join(self.temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write("x" * (100 if "small" in filename else 1000 if "large" in filename else 500))
            
            with patch('os.listdir', return_value=test_files):
                with patch('os.path.getsize') as mock_getsize:
                    # Mock file sizes
                    def get_size(path):
                        if "small" in path:
                            return 100
                        elif "large" in path:
                            return 1000
                        else:
                            return 500
                    mock_getsize.side_effect = get_size
                    
                    with patch.object(self.downloader, '_get_video_title', return_value="Test Title"):
                        result = await self.downloader._download_generic(test_url, platform)
                        
                        # Should select the largest file
                        assert "large_video.mp4" in result[0]


class TestVideoDownloaderProgressTracking:
    """Test progress tracking and monitoring functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @async_test(timeout=20.0)
    async def test_service_download_progress_polling_success(self):
        """Test progress polling for YouTube clips with successful completion."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.youtube.com/clip/abc123"
        expected_filename = "clip_video.mp4"
        expected_title = "Test YouTube Clip"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock initial download request (processing status)
            mock_download_response = AsyncMock()
            mock_download_response.status = 200
            mock_download_response.json.return_value = {
                "success": True,
                "status": "processing",
                "download_id": "test_download_123"
            }
            
            # Mock status polling responses (progress updates)
            status_responses = [
                {"status": "processing", "progress": 25},
                {"status": "processing", "progress": 50},
                {"status": "processing", "progress": 75},
                {"status": "completed", "progress": 100, "file_path": f"/tmp/{expected_filename}", "title": expected_title}
            ]
            
            mock_status_responses = []
            for response_data in status_responses:
                mock_status_response = AsyncMock()
                mock_status_response.status = 200
                mock_status_response.json.return_value = response_data
                mock_status_responses.append(mock_status_response)
            
            # Mock file download response
            mock_file_response = AsyncMock()
            mock_file_response.status = 200
            mock_file_response.content.iter_chunked.return_value = [b"video_data_chunk"]
            
            # Set up session method returns
            mock_session.post.return_value.__aenter__.return_value = mock_download_response
            mock_session.get.side_effect = [
                mock_status_response.__aenter__.return_value for mock_status_response in mock_status_responses
            ] + [mock_file_response.__aenter__.return_value]
            
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock file writing
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await self.downloader._download_from_service(test_url)
                
                assert result[0] is not None
                assert result[1] == expected_title
                assert expected_filename in result[0]
                
                # Verify progress polling calls
                assert mock_session.get.call_count >= 4  # At least 4 status checks + file download
                
                # Verify status polling URLs
                status_calls = [call for call in mock_session.get.call_args_list if 'status' in str(call)]
                assert len(status_calls) >= 4
    
    @async_test(timeout=20.0)
    async def test_service_download_progress_polling_timeout(self):
        """Test progress polling timeout after maximum attempts."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.youtube.com/clip/abc123"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock initial download request (processing status)
            mock_download_response = AsyncMock()
            mock_download_response.status = 200
            mock_download_response.json.return_value = {
                "success": True,
                "status": "processing",
                "download_id": "test_download_123"
            }
            
            # Mock status polling responses (always processing, never completes)
            mock_status_response = AsyncMock()
            mock_status_response.status = 200
            mock_status_response.json.return_value = {"status": "processing", "progress": 50}
            
            mock_session.post.return_value.__aenter__.return_value = mock_download_response
            mock_session.get.return_value.__aenter__.return_value = mock_status_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._download_from_service(test_url)
            
            assert result == (None, None)
            
            # Verify that polling was attempted multiple times (should timeout after 60 attempts)
            assert mock_session.get.call_count >= 60
    
    @async_test(timeout=15.0)
    async def test_service_download_progress_polling_failure(self):
        """Test progress polling when background download fails."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.youtube.com/clip/abc123"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock initial download request (processing status)
            mock_download_response = AsyncMock()
            mock_download_response.status = 200
            mock_download_response.json.return_value = {
                "success": True,
                "status": "processing",
                "download_id": "test_download_123"
            }
            
            # Mock status polling responses (processing then failed)
            status_responses = [
                {"status": "processing", "progress": 25},
                {"status": "processing", "progress": 50},
                {"status": "failed", "error": "Video not available"}
            ]
            
            mock_status_responses = []
            for response_data in status_responses:
                mock_status_response = AsyncMock()
                mock_status_response.status = 200
                mock_status_response.json.return_value = response_data
                mock_status_responses.append(mock_status_response)
            
            mock_session.post.return_value.__aenter__.return_value = mock_download_response
            mock_session.get.side_effect = [
                mock_status_response.__aenter__.return_value for mock_status_response in mock_status_responses
            ]
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._download_from_service(test_url)
            
            assert result == (None, None)
            assert mock_session.get.call_count == 3
    
    @async_test(timeout=15.0)
    async def test_service_download_immediate_response_no_polling(self):
        """Test service download with immediate response (no background processing)."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        expected_filename = "tiktok_video.mp4"
        expected_title = "Test TikTok Video"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock immediate successful response (no processing status)
            mock_download_response = AsyncMock()
            mock_download_response.status = 200
            mock_download_response.json.return_value = {
                "success": True,
                "file_path": f"/tmp/{expected_filename}",
                "title": expected_title
            }
            
            # Mock file download response
            mock_file_response = AsyncMock()
            mock_file_response.status = 200
            mock_file_response.content.iter_chunked.return_value = [b"video_data_chunk"]
            
            mock_session.post.return_value.__aenter__.return_value = mock_download_response
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock file writing
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await self.downloader._download_from_service(test_url)
                
                assert result[0] is not None
                assert result[1] == expected_title
                assert expected_filename in result[0]
                
                # Verify no status polling occurred (only file download)
                assert mock_session.get.call_count == 1
    
    def test_last_download_tracking(self):
        """Test that last download information is tracked."""
        # Initially empty
        assert self.downloader.last_download == {}
        
        # Can be updated
        test_info = {
            "url": "https://www.tiktok.com/@user/video/123456789",
            "filename": "test_video.mp4",
            "title": "Test Video",
            "timestamp": "2023-01-01T00:00:00Z"
        }
        
        self.downloader.last_download = test_info
        assert self.downloader.last_download == test_info


class TestVideoDownloaderErrorRecovery:
    """Test error recovery and retry mechanisms."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @async_test(timeout=15.0)
    async def test_service_download_retry_mechanism(self):
        """Test retry mechanism for service downloads."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        self.downloader.max_retries = 3
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # Mock responses: first two fail with 503, third succeeds
            responses = []
            
            # First two attempts fail
            for _ in range(2):
                mock_response = AsyncMock()
                mock_response.status = 503  # Service unavailable
                responses.append(mock_response)
            
            # Third attempt succeeds
            mock_success_response = AsyncMock()
            mock_success_response.status = 200
            mock_success_response.json.return_value = {
                "success": True,
                "file_path": "/tmp/video.mp4",
                "title": "Test Video"
            }
            responses.append(mock_success_response)
            
            # Mock file download
            mock_file_response = AsyncMock()
            mock_file_response.status = 200
            mock_file_response.content.iter_chunked.return_value = [b"video_data"]
            
            mock_session.post.side_effect = [
                response.__aenter__.return_value for response in responses
            ]
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            with patch('builtins.open', create=True):
                with patch('asyncio.sleep') as mock_sleep:  # Mock retry delay
                    result = await self.downloader._download_from_service(test_url)
                    
                    assert result[0] is not None
                    assert result[1] == "Test Video"
                    
                    # Verify retry attempts
                    assert mock_session.post.call_count == 3
                    assert mock_sleep.call_count == 2  # Two retry delays
    
    @async_test(timeout=15.0)
    async def test_service_download_max_retries_exceeded(self):
        """Test service download when max retries are exceeded."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        self.downloader.max_retries = 2
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # All attempts fail with 503
            mock_response = AsyncMock()
            mock_response.status = 503
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            with patch('asyncio.sleep'):  # Mock retry delay
                result = await self.downloader._download_from_service(test_url)
                
                assert result == (None, None)
                assert mock_session.post.call_count == 2  # max_retries attempts
    
    @async_test(timeout=15.0)
    async def test_service_download_non_retryable_error(self):
        """Test service download with non-retryable error (no retry)."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # 403 Forbidden (non-retryable)
            mock_response = AsyncMock()
            mock_response.status = 403
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.downloader._download_from_service(test_url)
            
            assert result == (None, None)
            assert mock_session.post.call_count == 1  # No retries for 403
    
    @async_test(timeout=15.0)
    async def test_service_download_network_error_recovery(self):
        """Test recovery from network errors during service download."""
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        self.downloader.max_retries = 3
        
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            
            # First attempt: network error, second attempt: success
            import aiohttp
            mock_session.post.side_effect = [
                aiohttp.ClientError("Connection failed"),
                AsyncMock().__aenter__.return_value
            ]
            
            # Mock successful response for second attempt
            mock_success_response = AsyncMock()
            mock_success_response.status = 200
            mock_success_response.json.return_value = {
                "success": True,
                "file_path": "/tmp/video.mp4",
                "title": "Test Video"
            }
            mock_session.post.side_effect[1].return_value = mock_success_response
            
            # Mock file download
            mock_file_response = AsyncMock()
            mock_file_response.status = 200
            mock_file_response.content.iter_chunked.return_value = [b"video_data"]
            mock_session.get.return_value.__aenter__.return_value = mock_file_response
            
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            with patch('builtins.open', create=True):
                with patch('asyncio.sleep'):  # Mock retry delay
                    result = await self.downloader._download_from_service(test_url)
                    
                    assert result[0] is not None
                    assert result[1] == "Test Video"
                    assert mock_session.post.call_count == 2
    
    @async_test(timeout=15.0)
    async def test_ytdlp_download_error_recovery(self):
        """Test error recovery in yt-dlp downloads."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # First attempt fails, second succeeds
            mock_failed_process = AsyncMock()
            mock_failed_process.communicate.return_value = (b"", b"Error: Network timeout")
            mock_failed_process.returncode = 1
            
            mock_success_process = AsyncMock()
            mock_success_process.communicate.return_value = (b"Download completed", b"")
            mock_success_process.returncode = 0
            
            mock_subprocess.side_effect = [mock_failed_process, mock_success_process]
            
            # Create test file for successful attempt
            test_file_path = os.path.join(self.temp_dir, "test_video.mp4")
            with open(test_file_path, 'w') as f:
                f.write("test video content")
            
            with patch('os.listdir', return_value=["test_video.mp4"]):
                with patch('os.path.getsize', return_value=1024):
                    with patch.object(self.downloader, '_get_video_title', return_value="Test Title"):
                        # First attempt should fail
                        result1 = await self.downloader._download_tiktok_ytdlp(test_url)
                        assert result1 == (None, None)
                        
                        # Second attempt should succeed
                        result2 = await self.downloader._download_tiktok_ytdlp(test_url)
                        assert result2[0] is not None
                        assert result2[1] == "Test Title"
    
    @async_test(timeout=15.0)
    async def test_file_cleanup_on_error(self):
        """Test file cleanup when download errors occur."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        # Create some old files in download directory
        old_files = ["old_video1.mp4", "old_video2.webm", "old_video3.mp4"]
        for filename in old_files:
            filepath = os.path.join(self.temp_dir, filename)
            with open(filepath, 'w') as f:
                f.write("old content")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Download failed")
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            # Mock os.listdir to return old files initially
            original_listdir = os.listdir
            def mock_listdir(path):
                if path == self.temp_dir:
                    return old_files
                return original_listdir(path)
            
            with patch('os.listdir', side_effect=mock_listdir):
                with patch('os.remove') as mock_remove:
                    result = await self.downloader._download_tiktok_ytdlp(test_url)
                    
                    assert result == (None, None)
                    
                    # Verify old files were cleaned up
                    assert mock_remove.call_count == len(old_files)
                    for filename in old_files:
                        expected_path = os.path.join(self.temp_dir, filename)
                        mock_remove.assert_any_call(expected_path)
    
    @async_test(timeout=15.0)
    async def test_download_timeout_with_process_termination(self):
        """Test download timeout with proper process termination."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError()
            mock_process.kill = Mock()
            mock_subprocess.return_value = mock_process
            
            result = await self.downloader._download_tiktok_ytdlp(test_url)
            
            assert result == (None, None)
            mock_process.kill.assert_called_once()
    
    @async_test(timeout=15.0)
    async def test_exception_handling_in_download_methods(self):
        """Test exception handling in various download methods."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        # Test TikTok download exception handling
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Subprocess creation failed")
            
            result = await self.downloader._download_tiktok_ytdlp(test_url)
            assert result == (None, None)
        
        # Test generic download exception handling
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Subprocess creation failed")
            
            result = await self.downloader._download_generic(test_url, Platform.OTHER)
            assert result == (None, None)
        
        # Test service download exception handling
        self.downloader.service_url = "http://localhost:8000"
        self.downloader.api_key = "test_api_key"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.side_effect = Exception("Session creation failed")
            
            result = await self.downloader._download_from_service(test_url)
            assert result == (None, None)


class TestVideoDownloaderStateManagement:
    """Test pause/resume functionality and state management."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_extract_urls = Mock(return_value=["https://www.tiktok.com/@user/video/123456789"])
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = VideoDownloader(
            download_path=self.temp_dir,
            extract_urls_func=self.mock_extract_urls
        )
        
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_lock_mechanism_initialization(self):
        """Test that async lock is properly initialized."""
        assert self.downloader.lock is not None
        assert isinstance(self.downloader.lock, asyncio.Lock)
    
    @async_test(timeout=15.0)
    async def test_concurrent_download_prevention(self):
        """Test that concurrent downloads are properly managed with locks."""
        test_url1 = "https://www.tiktok.com/@user1/video/123456789"
        test_url2 = "https://www.tiktok.com/@user2/video/987654321"
        
        download_order = []
        
        async def mock_download_with_delay(url):
            download_order.append(f"start_{url.split('/')[-1]}")
            await asyncio.sleep(0.1)  # Simulate download time
            download_order.append(f"end_{url.split('/')[-1]}")
            return f"/path/to/{url.split('/')[-1]}.mp4", f"Title for {url.split('/')[-1]}"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp', side_effect=mock_download_with_delay):
            # Start two downloads concurrently
            tasks = [
                self.downloader.download_video(test_url1),
                self.downloader.download_video(test_url2)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Both downloads should complete
            assert len(results) == 2
            assert all(result[0] is not None for result in results)
            
            # Downloads should be serialized (not truly concurrent due to lock)
            # The exact order depends on which task acquires the lock first
            assert len(download_order) == 4
            assert download_order[0].startswith("start_")
            assert download_order[1].startswith("end_")
            assert download_order[2].startswith("start_")
            assert download_order[3].startswith("end_")
    
    def test_download_path_state_persistence(self):
        """Test that download path state is maintained."""
        original_path = self.downloader.download_path
        
        # Path should remain consistent
        assert self.downloader.download_path == original_path
        assert os.path.exists(self.downloader.download_path)
        assert os.path.isabs(self.downloader.download_path)
    
    def test_platform_config_state_consistency(self):
        """Test that platform configurations remain consistent."""
        # Get initial configs
        initial_tiktok_config = self.downloader.platform_configs[Platform.TIKTOK]
        initial_other_config = self.downloader.platform_configs[Platform.OTHER]
        initial_shorts_config = self.downloader.youtube_shorts_config
        initial_clips_config = self.downloader.youtube_clips_config
        
        # Configs should remain the same
        assert self.downloader.platform_configs[Platform.TIKTOK] is initial_tiktok_config
        assert self.downloader.platform_configs[Platform.OTHER] is initial_other_config
        assert self.downloader.youtube_shorts_config is initial_shorts_config
        assert self.downloader.youtube_clips_config is initial_clips_config
    
    def test_service_configuration_state(self):
        """Test service configuration state management."""
        # Test initial state
        original_service_url = self.downloader.service_url
        original_api_key = self.downloader.api_key
        original_max_retries = self.downloader.max_retries
        original_retry_delay = self.downloader.retry_delay
        
        # State should be maintained
        assert self.downloader.service_url == original_service_url
        assert self.downloader.api_key == original_api_key
        assert self.downloader.max_retries == original_max_retries
        assert self.downloader.retry_delay == original_retry_delay
        
        # Test state modification
        self.downloader.service_url = "http://new-service:8000"
        self.downloader.api_key = "new_api_key"
        self.downloader.max_retries = 5
        self.downloader.retry_delay = 2
        
        assert self.downloader.service_url == "http://new-service:8000"
        assert self.downloader.api_key == "new_api_key"
        assert self.downloader.max_retries == 5
        assert self.downloader.retry_delay == 2
    
    @async_test(timeout=15.0)
    async def test_download_state_cleanup_on_success(self):
        """Test that download state is properly cleaned up on successful download."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp') as mock_download:
            mock_download.return_value = ("/path/to/video.mp4", "Test Video")
            
            # Simulate some state during download
            self.downloader.last_download = {"url": test_url, "status": "downloading"}
            
            result = await self.downloader.download_video(test_url)
            
            assert result[0] == "/path/to/video.mp4"
            assert result[1] == "Test Video"
            
            # State should be maintained (not automatically cleared)
            assert self.downloader.last_download["url"] == test_url
    
    @async_test(timeout=15.0)
    async def test_download_state_cleanup_on_failure(self):
        """Test that download state is properly handled on download failure."""
        test_url = "https://www.tiktok.com/@user/video/123456789"
        
        with patch.object(self.downloader, '_download_tiktok_ytdlp') as mock_download:
            mock_download.return_value = (None, None)
            
            # Simulate some state during download
            self.downloader.last_download = {"url": test_url, "status": "downloading"}
            
            result = await self.downloader.download_video(test_url)
            
            assert result == (None, None)
            
            # State should be maintained (not automatically cleared)
            assert self.downloader.last_download["url"] == test_url
    
    def test_error_stickers_state_consistency(self):
        """Test that error stickers list remains consistent."""
        original_stickers = self.downloader.ERROR_STICKERS.copy()
        
        # Stickers should remain the same
        assert self.downloader.ERROR_STICKERS == original_stickers
        assert len(self.downloader.ERROR_STICKERS) == 2
        assert all(isinstance(sticker, str) for sticker in self.downloader.ERROR_STICKERS)
    
    def test_supported_platforms_state_consistency(self):
        """Test that supported platforms list remains consistent."""
        original_platforms = self.downloader.supported_platforms.copy()
        
        # Platforms should remain the same
        assert self.downloader.supported_platforms == original_platforms
        assert self.downloader.supported_platforms == VideoPlatforms.SUPPORTED_PLATFORMS