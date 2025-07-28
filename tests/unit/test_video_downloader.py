import unittest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import asyncio
import pytest

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

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
        
    @unittest.skip("This test requires network access")
    def test_download_video(self):
        """Test video download functionality."""
        # This is a placeholder for a real test that would require network access
        pass

# Run the tests
if __name__ == '__main__':
    unittest.main()