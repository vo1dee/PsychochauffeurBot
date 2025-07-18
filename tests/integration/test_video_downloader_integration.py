"""
Integration tests for video downloader functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import CallbackContext

from modules.video_downloader import VideoDownloader, Platform, DownloadConfig, setup_video_handlers
from modules.error_handler import ErrorHandler


class TestVideoDownloaderIntegration:
    """Integration tests for video downloader."""
    
    @pytest.fixture
    def video_downloader(self):
        """Create a video downloader instance."""
        def mock_extract_urls(text):
            return ["https://www.tiktok.com/@user/video/123456789"]
        
        return VideoDownloader(extract_urls_func=mock_extract_urls)
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update."""
        user = User(id=123, first_name="Test", is_bot=False)
        chat = Chat(id=-1001234567890, type="supergroup")
        
        # Create a mock message with proper bot association
        message = Mock()
        message.message_id = 1
        message.date = None
        message.chat = chat
        message.from_user = user
        message.text = "Check out this video: https://www.tiktok.com/@user/video/123456789"
        message.reply_text = AsyncMock()
        message.reply_sticker = AsyncMock()
        message.delete = AsyncMock()
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock callback context."""
        context = Mock(spec=CallbackContext)
        context.bot = Mock()
        context.bot.send_video = AsyncMock()
        context.bot.send_message = AsyncMock()
        return context
    
    def test_video_downloader_initialization(self, video_downloader):
        """Test video downloader initialization."""
        assert video_downloader is not None
        assert hasattr(video_downloader, 'extract_urls')
        assert callable(video_downloader.extract_urls)
    
    def test_platform_detection(self, video_downloader):
        """Test platform detection from URLs."""
        tiktok_url = "https://www.tiktok.com/@user/video/123456789"
        platform = video_downloader._get_platform(tiktok_url)
        
        assert platform == Platform.TIKTOK
    
    def test_download_config_creation(self):
        """Test download configuration creation."""
        config = DownloadConfig(
            format="mp4",
            headers={"User-Agent": "test"},
            max_height=720,
            max_retries=3,
            extra_args=["--no-playlist"]
        )
        
        assert config.format == "mp4"
        assert config.headers["User-Agent"] == "test"
        assert config.max_height == 720
        assert config.max_retries == 3
        assert "--no-playlist" in config.extra_args
    
    @pytest.mark.asyncio
    async def test_url_extraction(self, video_downloader):
        """Test URL extraction from messages."""
        text = "Check out this video: https://www.tiktok.com/@user/video/123456789"
        urls = video_downloader.extract_urls(text)
        
        assert len(urls) == 1
        from urllib.parse import urlparse
        assert urlparse(urls[0]).hostname == "www.tiktok.com"
    
    @pytest.mark.asyncio
    async def test_download_process_mock(self, video_downloader, mock_update, mock_context):
        """Test the download process with mocked external calls."""
        # Mock the file existence check
        with patch('os.path.exists', return_value=True):
            with patch.object(video_downloader, 'download_video') as mock_download:
                mock_download.return_value = ('/tmp/test_video.mp4', 'Test Video')
                
                with patch.object(video_downloader, '_send_video') as mock_send:
                    mock_send.return_value = None
                    
                    with patch.object(video_downloader, '_cleanup') as mock_cleanup:
                        mock_cleanup.return_value = None
                        
                        await video_downloader.handle_video_link(mock_update, mock_context)
                        
                        mock_download.assert_called_once()
                        mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_download(self, video_downloader, mock_update, mock_context):
        """Test error handling during video download."""
        with patch.object(video_downloader, 'download_video') as mock_download:
            mock_download.side_effect = Exception("Download failed")
            
            with patch.object(video_downloader, '_handle_processing_error') as mock_error:
                mock_error.return_value = None
                
                with patch.object(video_downloader, '_cleanup') as mock_cleanup:
                    mock_cleanup.return_value = None
                    
                    await video_downloader.handle_video_link(mock_update, mock_context)
                    
                    mock_error.assert_called_once()
    
    def test_setup_video_handlers(self):
        """Test video handler setup."""
        mock_application = Mock()
        mock_application.add_handler = Mock()
        mock_application.bot_data = {}  # Add bot_data as a dictionary
        
        def mock_extract_urls(text):
            return []
        
        setup_video_handlers(mock_application, extract_urls_func=mock_extract_urls)
        
        # Should add handlers to the application
        assert mock_application.add_handler.called


class TestVideoDownloaderErrorHandling:
    """Test error handling in video downloader."""
    
    @pytest.fixture
    def video_downloader(self):
        """Create a video downloader instance."""
        def mock_extract_urls(text):
            return ["https://www.tiktok.com/@user/video/123456789"]
        
        return VideoDownloader(extract_urls_func=mock_extract_urls)
    
    @pytest.mark.asyncio
    async def test_invalid_url_handling(self, video_downloader):
        """Test handling of invalid URLs."""
        invalid_url = "not_a_valid_url"
        
        with patch.object(video_downloader, 'download_video') as mock_download:
            mock_download.return_value = (None, None)
            
            result = await video_downloader.download_video(invalid_url)
            
            assert result == (None, None)
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, video_downloader):
        """Test handling of network errors."""
        with patch.object(video_downloader, 'download_video') as mock_download:
            mock_download.side_effect = ConnectionError("Network error")
            
            with pytest.raises(ConnectionError):
                await video_downloader.download_video("https://example.com/video")
    
    def test_unsupported_platform_handling(self, video_downloader):
        """Test handling of unsupported platforms."""
        unsupported_url = "https://unsupported-platform.com/video/123"
        platform = video_downloader._get_platform(unsupported_url)
        
        assert platform == Platform.OTHER


class TestVideoDownloaderPerformance:
    """Performance tests for video downloader."""
    
    @pytest.fixture
    def video_downloader(self):
        """Create a video downloader instance."""
        def mock_extract_urls(text):
            return ["https://www.tiktok.com/@user/video/123456789"]
        
        return VideoDownloader(extract_urls_func=mock_extract_urls)
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads(self, video_downloader):
        """Test handling of concurrent download requests."""
        urls = [
            "https://www.tiktok.com/@user/video/1",
            "https://www.tiktok.com/@user/video/2",
            "https://www.tiktok.com/@user/video/3"
        ]
        
        async def mock_download(url):
            await asyncio.sleep(0.1)  # Simulate download time
            return (f'/tmp/{url.split("/")[-1]}.mp4', 'Test Video')
        
        with patch.object(video_downloader, 'download_video', side_effect=mock_download):
            tasks = [video_downloader.download_video(url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 3
            assert all(result[0] is not None for result in results)
    
    @pytest.mark.asyncio
    async def test_download_timeout_handling(self, video_downloader):
        """Test handling of download timeouts."""
        async def slow_download(url):
            await asyncio.sleep(10)  # Very slow download
            return (None, None)
        
        with patch.object(video_downloader, 'download_video', side_effect=slow_download):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    video_downloader.download_video("https://example.com/video"),
                    timeout=1.0
                )