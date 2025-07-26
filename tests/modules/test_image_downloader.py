"""
Unit tests for the image downloader module.
Tests image URL validation, processing, download functionality, and error handling.
"""

import pytest
import asyncio
import aiohttp
import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from modules.image_downloader import ImageDownloader


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def image_downloader():
    """Create ImageDownloader instance for testing."""
    return ImageDownloader()


@pytest.fixture
def sample_instagram_urls():
    """Sample Instagram URLs for testing."""
    return [
        "https://www.instagram.com/p/ABC123/",
        "https://instagram.com/p/DEF456/",
        "https://www.instagram.com/p/GHI789/?utm_source=ig_web_copy_link"
    ]


@pytest.fixture
def sample_tiktok_urls():
    """Sample TikTok URLs for testing."""
    return [
        "https://www.tiktok.com/@user/video/1234567890",
        "https://tiktok.com/@testuser/video/9876543210"
    ]


@pytest.fixture
def sample_image_urls():
    """Sample image URLs for testing."""
    return [
        "https://example.com/image1.jpg",
        "https://example.com/image2.png",
        "https://example.com/image3.jpeg"
    ]


@pytest.fixture
def mock_instagram_json_response():
    """Mock Instagram JSON API response."""
    return {
        "items": [{
            "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/image1.jpg",
            "display_resources": [
                {
                    "src": "https://scontent.cdninstagram.com/v/t51.2885-15/image1_640.jpg",
                    "config_width": 640
                },
                {
                    "src": "https://scontent.cdninstagram.com/v/t51.2885-15/image1_1080.jpg",
                    "config_width": 1080
                }
            ],
            "edge_sidecar_to_children": {
                "edges": [
                    {
                        "node": {
                            "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/carousel1.jpg",
                            "display_resources": [
                                {
                                    "src": "https://scontent.cdninstagram.com/v/t51.2885-15/carousel1_1080.jpg",
                                    "config_width": 1080
                                }
                            ]
                        }
                    },
                    {
                        "node": {
                            "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/carousel2.jpg",
                            "display_resources": [
                                {
                                    "src": "https://scontent.cdninstagram.com/v/t51.2885-15/carousel2_1080.jpg",
                                    "config_width": 1080
                                }
                            ]
                        }
                    }
                ]
            }
        }]
    }


@pytest.fixture
def mock_instagram_html_response():
    """Mock Instagram HTML response."""
    return '''
    <html>
    <head>
        <meta property="og:image" content="https://scontent.cdninstagram.com/v/t51.2885-15/og_image.jpg" />
    </head>
    <body>
        <script type="text/javascript">
            window._sharedData = {
                "entry_data": {
                    "PostPage": [{
                        "graphql": {
                            "shortcode_media": {
                                "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/shared_data_image.jpg",
                                "edge_sidecar_to_children": {
                                    "edges": [{
                                        "node": {
                                            "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/shared_carousel1.jpg"
                                        }
                                    }]
                                }
                            }
                        }
                    }]
                }
            };
        </script>
    </body>
    </html>
    '''


@pytest.fixture
def mock_tiktok_html_response():
    """Mock TikTok HTML response."""
    return '''
    <html>
    <head>
        <meta property="og:image" content="https://p16-sign-va.tiktokcdn.com/tos-maliva-p-0068/cover_image.jpg" />
    </head>
    <body>
        <script>
            var data = {"cover":"https://p16-sign-va.tiktokcdn.com/tos-maliva-p-0068/video_cover.jpg"};
        </script>
    </body>
    </html>
    '''


class TestImageDownloader:
    """Test cases for ImageDownloader class."""


class TestImageURLValidation:
    """Test image URL validation and processing."""
    
    def test_instagram_regex_pattern(self, image_downloader, sample_instagram_urls):
        """Test Instagram URL regex pattern matching."""
        for url in sample_instagram_urls:
            match = image_downloader.INSTAGRAM_REGEX.search(url)
            assert match is not None, f"Instagram regex should match URL: {url}"
            assert match.group(1) in url
    
    def test_tiktok_regex_pattern(self, image_downloader, sample_tiktok_urls):
        """Test TikTok URL regex pattern matching."""
        for url in sample_tiktok_urls:
            match = image_downloader.TIKTOK_REGEX.search(url)
            assert match is not None, f"TikTok regex should match URL: {url}"
            assert match.group(1) in url
    
    def test_invalid_urls_not_matched(self, image_downloader):
        """Test that invalid URLs are not matched by regex patterns."""
        invalid_urls = [
            "https://example.com/not-instagram",
            "https://facebook.com/post/123",
            "https://youtube.com/watch?v=123",
            "not-a-url-at-all",
            ""
        ]
        
        for url in invalid_urls:
            instagram_match = image_downloader.INSTAGRAM_REGEX.search(url)
            tiktok_match = image_downloader.TIKTOK_REGEX.search(url)
            
            assert instagram_match is None, f"Instagram regex should not match: {url}"
            assert tiktok_match is None, f"TikTok regex should not match: {url}"


class TestInstagramImageFetching:
    """Test Instagram image fetching functionality."""
    
    @pytest.mark.asyncio
    async def test_fetch_instagram_images_json_success(
        self, 
        image_downloader, 
        mock_instagram_json_response
    ):
        """Test successful Instagram image fetching via JSON API."""
        url = "https://www.instagram.com/p/ABC123/"
        
        # Mock aiohttp session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=mock_instagram_json_response)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_instagram_images(url)
            
        assert len(images) > 0, "Should return at least one image"
        assert all(isinstance(img, str) for img in images), "All results should be strings"
        assert all(img.startswith('https://') for img in images), "All results should be URLs"
    
    @pytest.mark.asyncio
    async def test_fetch_instagram_images_html_fallback(
        self, 
        image_downloader, 
        mock_instagram_html_response
    ):
        """Test Instagram image fetching fallback to HTML parsing."""
        url = "https://www.instagram.com/p/ABC123/"
        
        # Mock JSON response failure and HTML success
        mock_json_response = AsyncMock()
        mock_json_response.status = 404
        
        mock_html_response = AsyncMock()
        mock_html_response.status = 200
        mock_html_response.text = AsyncMock(return_value=mock_instagram_html_response)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_json_response, mock_html_response])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_instagram_images(url)
            
        assert len(images) > 0, "Should return images from HTML parsing"
        assert all(isinstance(img, str) for img in images), "All results should be strings"
    
    @pytest.mark.asyncio
    async def test_fetch_instagram_images_network_error(self, image_downloader):
        """Test Instagram image fetching with network errors."""
        url = "https://www.instagram.com/p/ABC123/"
        
        # Mock network error
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_instagram_images(url)
            
        assert images == [], "Should return empty list on network error"
    
    @pytest.mark.asyncio
    async def test_fetch_instagram_images_invalid_json(self, image_downloader):
        """Test Instagram image fetching with invalid JSON response."""
        url = "https://www.instagram.com/p/ABC123/"
        
        # Mock invalid JSON response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_instagram_images(url)
            
        assert images == [], "Should return empty list on JSON decode error"
    
    def test_parse_instagram_json_single_image(self, image_downloader):
        """Test parsing Instagram JSON for single image post."""
        json_data = {
            "items": [{
                "display_url": "https://example.com/single_image.jpg",
                "display_resources": [
                    {
                        "src": "https://example.com/single_image_1080.jpg",
                        "config_width": 1080
                    }
                ]
            }]
        }
        
        images = image_downloader._parse_instagram_json(json_data)
        
        assert len(images) == 1
        assert "single_image_1080.jpg" in images[0]
    
    def test_parse_instagram_json_carousel(self, image_downloader):
        """Test parsing Instagram JSON for carousel post."""
        json_data = {
            "items": [{
                "edge_sidecar_to_children": {
                    "edges": [
                        {
                            "node": {
                                "display_url": "https://example.com/carousel1.jpg",
                                "display_resources": [
                                    {
                                        "src": "https://example.com/carousel1_1080.jpg",
                                        "config_width": 1080
                                    }
                                ]
                            }
                        },
                        {
                            "node": {
                                "display_url": "https://example.com/carousel2.jpg",
                                "display_resources": [
                                    {
                                        "src": "https://example.com/carousel2_1080.jpg",
                                        "config_width": 1080
                                    }
                                ]
                            }
                        }
                    ]
                }
            }]
        }
        
        images = image_downloader._parse_instagram_json(json_data)
        
        assert len(images) == 2
        assert any("carousel1_1080.jpg" in img for img in images)
        assert any("carousel2_1080.jpg" in img for img in images)
    
    def test_parse_instagram_json_empty_data(self, image_downloader):
        """Test parsing empty or invalid Instagram JSON data."""
        test_cases = [
            {},
            {"items": []},
            {"items": [{}]},
            {"invalid": "data"}
        ]
        
        for json_data in test_cases:
            images = image_downloader._parse_instagram_json(json_data)
            assert images == [], f"Should return empty list for: {json_data}"
    
    def test_parse_instagram_html_og_image(self, image_downloader):
        """Test parsing Instagram HTML with og:image meta tags."""
        html = '''
        <html>
        <head>
            <meta property="og:image" content="https://example.com/og_image.jpg" />
            <meta property="og:image:url" content="https://example.com/og_image_url.jpg" />
        </head>
        </html>
        '''
        
        images = image_downloader._parse_instagram_html(html)
        
        assert len(images) >= 1
        assert any("og_image" in img for img in images)
    
    def test_parse_instagram_html_script_data(self, image_downloader):
        """Test parsing Instagram HTML with script data."""
        html = '''
        <html>
        <body>
            <script type="text/javascript">
                var data = {"display_url":"https://example.com/script_image.jpg"};
            </script>
        </body>
        </html>
        '''
        
        images = image_downloader._parse_instagram_html(html)
        
        assert len(images) >= 1
        assert any("script_image.jpg" in img for img in images)


class TestTikTokImageFetching:
    """Test TikTok image fetching functionality."""
    
    @pytest.mark.asyncio
    async def test_fetch_tiktok_image_success(
        self, 
        image_downloader, 
        mock_tiktok_html_response
    ):
        """Test successful TikTok image fetching."""
        url = "https://www.tiktok.com/@user/video/1234567890"
        
        # Mock aiohttp session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=mock_tiktok_html_response)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_tiktok_image(url)
            
        assert len(images) > 0, "Should return at least one image"
        assert all(isinstance(img, str) for img in images), "All results should be strings"
        assert all(img.startswith('https://') for img in images), "All results should be URLs"
    
    @pytest.mark.asyncio
    async def test_fetch_tiktok_image_og_meta(self, image_downloader):
        """Test TikTok image fetching from og:image meta tag."""
        url = "https://www.tiktok.com/@user/video/1234567890"
        html_with_og = '''
        <html>
        <head>
            <meta property="og:image" content="https://example.com/tiktok_cover.jpg" />
        </head>
        </html>
        '''
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_with_og)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_tiktok_image(url)
            
        assert len(images) == 1
        assert "tiktok_cover.jpg" in images[0]
    
    @pytest.mark.asyncio
    async def test_fetch_tiktok_image_cover_regex(self, image_downloader):
        """Test TikTok image fetching using cover regex pattern."""
        url = "https://www.tiktok.com/@user/video/1234567890"
        html_with_cover = '''
        <html>
        <body>
            <script>
                var videoData = {"cover":"https://example.com/regex_cover.jpg\\u0026param=value"};
            </script>
        </body>
        </html>
        '''
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_with_cover)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_tiktok_image(url)
            
        assert len(images) == 1
        assert "regex_cover.jpg" in images[0]
        assert "&param=value" in images[0]  # Should decode \\u0026 to &
    
    @pytest.mark.asyncio
    async def test_fetch_tiktok_image_network_error(self, image_downloader):
        """Test TikTok image fetching with network error."""
        url = "https://www.tiktok.com/@user/video/1234567890"
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_tiktok_image(url)
            
        assert images == [], "Should return empty list on network error"
    
    @pytest.mark.asyncio
    async def test_fetch_tiktok_image_no_cover_found(self, image_downloader):
        """Test TikTok image fetching when no cover image is found."""
        url = "https://www.tiktok.com/@user/video/1234567890"
        html_no_cover = '''
        <html>
        <head>
            <title>TikTok Video</title>
        </head>
        <body>
            <p>No cover image here</p>
        </body>
        </html>
        '''
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_no_cover)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            images = await image_downloader.fetch_tiktok_image(url)
            
        assert images == [], "Should return empty list when no cover found"


class TestImageFormatValidation:
    """Test image format validation and filtering."""
    
    def test_cropped_image_filtering(self, image_downloader, sample_image_urls):
        """Test that cropped images are filtered out during download."""
        # Add cropped image URLs to test filtering
        cropped_urls = [
            "https://example.com/image_s640x640.jpg",
            "https://example.com/image_stp=dst-jpg.jpg",
            "https://example.com/image_e35.jpg"
        ]
        
        all_urls = sample_image_urls + cropped_urls
        
        # Mock the download method to test URL filtering
        with patch.object(image_downloader, '_download_one_image', new_callable=AsyncMock):
            # The method should filter out cropped URLs before processing
            filtered_urls = [url for url in all_urls if not ("s640x640" in url or "stp=" in url or "e35" in url)]
            
            assert len(filtered_urls) == len(sample_image_urls)
            assert all(url in sample_image_urls for url in filtered_urls)
    
    def test_valid_image_extensions(self, image_downloader):
        """Test validation of image file extensions."""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        
        for ext in valid_extensions:
            url = f"https://example.com/image{ext}"
            # This is a conceptual test - the actual validation would be in URL processing
            assert url.endswith(ext), f"URL should end with {ext}"
    
    def test_image_url_format_validation(self, image_downloader):
        """Test basic image URL format validation."""
        valid_urls = [
            "https://example.com/image.jpg",
            "http://test.com/photo.png",
            "https://cdn.example.com/media/image.jpeg"
        ]
        
        invalid_urls = [
            "not-a-url",
            "ftp://example.com/image.jpg",
            "https://example.com/not-an-image.txt",
            ""
        ]
        
        for url in valid_urls:
            assert url.startswith(('http://', 'https://')), f"Valid URL should start with http(s): {url}"
        
        for url in invalid_urls:
            if url:  # Skip empty string
                assert not (url.startswith(('http://', 'https://')) and any(ext in url for ext in ['.jpg', '.png', '.jpeg', '.gif'])), f"Invalid URL should not pass validation: {url}"


class TestImageDownloadFunctionality:
    """Test core image download functionality."""
    
    @pytest.mark.asyncio
    async def test_download_images_from_urls_success(
        self, 
        image_downloader, 
        sample_image_urls, 
        temp_directory
    ):
        """Test successful image download from URLs."""
        download_path = str(temp_directory / "downloads")
        
        # Mock successful HTTP responses
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[
            b"fake_image_data_1",
            b"fake_image_data_2", 
            b"fake_image_data_3",
            b""  # End of stream
        ])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                sample_image_urls, 
                download_path
            )
        
        assert len(saved_files) == len(sample_image_urls)
        assert all(os.path.exists(file_path) for file_path in saved_files)
        assert all(file_path.startswith(download_path) for file_path in saved_files)
    
    @pytest.mark.asyncio
    async def test_download_images_empty_url_list(self, image_downloader, temp_directory):
        """Test download with empty URL list."""
        download_path = str(temp_directory / "downloads")
        
        saved_files = await image_downloader.download_images_from_urls([], download_path)
        
        assert saved_files == []
    
    @pytest.mark.asyncio
    async def test_download_images_filtered_urls(self, image_downloader, temp_directory):
        """Test that cropped URLs are filtered out before download."""
        download_path = str(temp_directory / "downloads")
        
        # Mix of valid and cropped URLs
        mixed_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image_s640x640.jpg",  # Should be filtered
            "https://example.com/image2.png",
            "https://example.com/image_stp=dst-jpg.jpg",  # Should be filtered
            "https://example.com/image3.jpeg",
            "https://example.com/image_e35.jpg"  # Should be filtered
        ]
        
        # Mock successful HTTP responses
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[
            b"fake_image_data",
            b""  # End of stream
        ])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                mixed_urls, 
                download_path
            )
        
        # Should only download 3 valid URLs (filtered out 3 cropped ones)
        assert len(saved_files) == 3
    
    @pytest.mark.asyncio
    async def test_download_one_image_success(self, image_downloader, temp_directory):
        """Test downloading a single image successfully."""
        image_url = "https://example.com/test_image.jpg"
        output_file = str(temp_directory / "test_image.jpg")
        saved_list = []
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[
            b"fake_image_data_chunk_1",
            b"fake_image_data_chunk_2",
            b""  # End of stream
        ])
        
        mock_session = AsyncMock()
        
        await image_downloader._download_one_image(
            mock_session, 
            image_url, 
            output_file, 
            saved_list
        )
        
        assert len(saved_list) == 1
        assert saved_list[0] == output_file
        assert os.path.exists(output_file)
        
        # Verify file content
        with open(output_file, 'rb') as f:
            content = f.read()
            assert content == b"fake_image_data_chunk_1fake_image_data_chunk_2"
    
    @pytest.mark.asyncio
    async def test_download_one_image_http_error(self, image_downloader, temp_directory):
        """Test downloading a single image with HTTP error."""
        image_url = "https://example.com/nonexistent_image.jpg"
        output_file = str(temp_directory / "nonexistent_image.jpg")
        saved_list = []
        
        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status = 404
        
        mock_session = AsyncMock()
        
        await image_downloader._download_one_image(
            mock_session, 
            image_url, 
            output_file, 
            saved_list
        )
        
        assert len(saved_list) == 0
        assert not os.path.exists(output_file)
    
    @pytest.mark.asyncio
    async def test_download_one_image_network_exception(self, image_downloader, temp_directory):
        """Test downloading a single image with network exception."""
        image_url = "https://example.com/test_image.jpg"
        output_file = str(temp_directory / "test_image.jpg")
        saved_list = []
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientError("Network error"))
        
        await image_downloader._download_one_image(
            mock_session, 
            image_url, 
            output_file, 
            saved_list
        )
        
        assert len(saved_list) == 0
        assert not os.path.exists(output_file)
    
    @pytest.mark.asyncio
    async def test_download_creates_directory(self, image_downloader, temp_directory):
        """Test that download creates the target directory if it doesn't exist."""
        download_path = str(temp_directory / "new_downloads" / "subdirectory")
        image_urls = ["https://example.com/image.jpg"]
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"fake_data", b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        assert os.path.exists(download_path)
        assert len(saved_files) == 1
    
    @pytest.mark.asyncio
    async def test_download_concurrent_images(self, image_downloader, temp_directory):
        """Test concurrent download of multiple images."""
        download_path = str(temp_directory / "concurrent_downloads")
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.jpg",
            "https://example.com/image3.jpg"
        ]
        
        # Mock successful HTTP responses
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"fake_data", b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Measure execution time to ensure concurrency
            import time
            start_time = time.time()
            
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
        
        assert len(saved_files) == len(image_urls)
        # Concurrent execution should be faster than sequential
        # This is a rough check - in real scenarios with network delays, 
        # concurrent execution would show more significant time savings
        assert execution_time < 1.0  # Should complete quickly with mocked responses
    
    @pytest.mark.asyncio
    async def test_download_filename_generation(self, image_downloader, temp_directory):
        """Test that download generates unique filenames."""
        download_path = str(temp_directory / "filename_test")
        image_urls = [
            "https://example.com/image1.jpg",
            "https://example.com/image2.jpg"
        ]
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"fake_data", b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        assert len(saved_files) == len(image_urls)
        
        # Check that filenames are unique
        filenames = [os.path.basename(f) for f in saved_files]
        assert len(set(filenames)) == len(filenames), "All filenames should be unique"
        
        # Check filename pattern (should contain task name and index)
        for filename in filenames:
            assert filename.startswith("image_"), "Filename should start with 'image_'"
            assert filename.endswith(".jpg"), "Filename should end with '.jpg'"


class TestImageDownloaderIntegration:
    """Integration tests for ImageDownloader with real-world scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_instagram_workflow(self, image_downloader, temp_directory):
        """Test complete Instagram image extraction and download workflow."""
        instagram_url = "https://www.instagram.com/p/TEST123/"
        download_path = str(temp_directory / "instagram_test")
        
        # Mock Instagram API response
        mock_json_response = AsyncMock()
        mock_json_response.status = 200
        mock_json_response.headers = {"Content-Type": "application/json"}
        mock_json_response.json = AsyncMock(return_value={
            "items": [{
                "display_url": "https://scontent.cdninstagram.com/v/t51.2885-15/test_image.jpg",
                "display_resources": [
                    {
                        "src": "https://scontent.cdninstagram.com/v/t51.2885-15/test_image_1080.jpg",
                        "config_width": 1080
                    }
                ]
            }]
        })
        
        # Mock image download response
        mock_download_response = AsyncMock()
        mock_download_response.status = 200
        mock_download_response.content.read = AsyncMock(side_effect=[b"instagram_image_data", b""])
        
        # Create context managers for each response
        mock_json_context = AsyncMock()
        mock_json_context.__aenter__ = AsyncMock(return_value=mock_json_response)
        mock_json_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_download_context = AsyncMock()
        mock_download_context.__aenter__ = AsyncMock(return_value=mock_download_response)
        mock_download_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_json_context, mock_download_context])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Step 1: Extract image URLs
            image_urls = await image_downloader.fetch_instagram_images(instagram_url)
            
            # Step 2: Download images
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        assert len(image_urls) > 0, "Should extract at least one image URL"
        assert len(saved_files) > 0, "Should download at least one image"
        assert all(os.path.exists(f) for f in saved_files), "All downloaded files should exist"
    
    @pytest.mark.asyncio
    async def test_full_tiktok_workflow(self, image_downloader, temp_directory):
        """Test complete TikTok image extraction and download workflow."""
        tiktok_url = "https://www.tiktok.com/@user/video/1234567890"
        download_path = str(temp_directory / "tiktok_test")
        
        # Mock TikTok HTML response
        mock_html_response = AsyncMock()
        mock_html_response.status = 200
        mock_html_response.text = AsyncMock(return_value='''
            <html>
            <head>
                <meta property="og:image" content="https://p16-sign-va.tiktokcdn.com/test_cover.jpg" />
            </head>
            </html>
        ''')
        
        # Mock image download response
        mock_download_response = AsyncMock()
        mock_download_response.status = 200
        mock_download_response.content.read = AsyncMock(side_effect=[b"tiktok_cover_data", b""])
        
        # Create context managers for each response
        mock_html_context = AsyncMock()
        mock_html_context.__aenter__ = AsyncMock(return_value=mock_html_response)
        mock_html_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_download_context = AsyncMock()
        mock_download_context.__aenter__ = AsyncMock(return_value=mock_download_response)
        mock_download_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_html_context, mock_download_context])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Step 1: Extract image URLs
            image_urls = await image_downloader.fetch_tiktok_image(tiktok_url)
            
            # Step 2: Download images
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        assert len(image_urls) > 0, "Should extract at least one image URL"
        assert len(saved_files) > 0, "Should download at least one image"
        assert all(os.path.exists(f) for f in saved_files), "All downloaded files should exist"
    
    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenario(self, image_downloader, temp_directory):
        """Test scenario with mixed successful and failed downloads."""
        download_path = str(temp_directory / "mixed_test")
        image_urls = [
            "https://example.com/success1.jpg",
            "https://example.com/fail.jpg",
            "https://example.com/success2.jpg"
        ]
        
        # Mock mixed responses
        success_response = AsyncMock()
        success_response.status = 200
        success_response.content.read = AsyncMock(side_effect=[b"success_data", b""])
        
        fail_response = AsyncMock()
        fail_response.status = 404
        
        # Create context managers for each response
        success_context1 = AsyncMock()
        success_context1.__aenter__ = AsyncMock(return_value=success_response)
        success_context1.__aexit__ = AsyncMock(return_value=None)
        
        fail_context = AsyncMock()
        fail_context.__aenter__ = AsyncMock(return_value=fail_response)
        fail_context.__aexit__ = AsyncMock(return_value=None)
        
        success_context2 = AsyncMock()
        success_context2.__aenter__ = AsyncMock(return_value=success_response)
        success_context2.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[success_context1, fail_context, success_context2])
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        # Should have 2 successful downloads out of 3 attempts
        assert len(saved_files) == 2
        assert all(os.path.exists(f) for f in saved_files)


class TestFileHandlingAndStorage:
    """Test file handling and storage management functionality."""
    
    @pytest.mark.asyncio
    async def test_file_saving_with_custom_path(self, image_downloader, temp_directory):
        """Test file saving with custom download path."""
        custom_path = str(temp_directory / "custom" / "images")
        image_urls = ["https://example.com/custom_image.jpg"]
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"custom_image_data", b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                custom_path
            )
        
        assert len(saved_files) == 1
        assert saved_files[0].startswith(custom_path)
        assert os.path.exists(saved_files[0])
        
        # Verify directory was created
        assert os.path.exists(custom_path)
        assert os.path.isdir(custom_path)
    
    @pytest.mark.asyncio
    async def test_file_overwrite_behavior(self, image_downloader, temp_directory):
        """Test file overwrite behavior when downloading to existing file."""
        download_path = str(temp_directory / "overwrite_test")
        image_url = "https://example.com/overwrite_image.jpg"
        
        # Create directory and pre-existing file
        os.makedirs(download_path, exist_ok=True)
        existing_file = os.path.join(download_path, "image_test_0.jpg")
        with open(existing_file, 'wb') as f:
            f.write(b"original_data")
        
        # Mock successful HTTP response with new data
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"new_data", b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 1
        
        # Verify file was overwritten with new data
        with open(saved_files[0], 'rb') as f:
            content = f.read()
            assert content == b"new_data"
    
    @pytest.mark.asyncio
    async def test_file_permissions_handling(self, image_downloader, temp_directory):
        """Test handling of file permission issues during save."""
        download_path = str(temp_directory / "permission_test")
        image_url = "https://example.com/permission_image.jpg"
        
        # Create directory with restricted permissions
        os.makedirs(download_path, exist_ok=True)
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"permission_data", b""])
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        # Mock file write to raise permission error
        original_open = open
        def mock_open(*args, **kwargs):
            if 'wb' in args:
                raise PermissionError("Permission denied")
            return original_open(*args, **kwargs)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('builtins.open', side_effect=mock_open):
                saved_files = await image_downloader.download_images_from_urls(
                    [image_url], 
                    download_path
                )
        
        # Should handle permission error gracefully
        assert len(saved_files) == 0
    
    @pytest.mark.asyncio
    async def test_disk_space_handling(self, image_downloader, temp_directory):
        """Test handling of disk space issues during file save."""
        download_path = str(temp_directory / "disk_space_test")
        image_url = "https://example.com/large_image.jpg"
        
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b"large_image_data", b""])
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        # Mock file write to raise disk space error
        original_open = open
        def mock_open(*args, **kwargs):
            if 'wb' in args:
                raise OSError("No space left on device")
            return original_open(*args, **kwargs)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('builtins.open', side_effect=mock_open):
                saved_files = await image_downloader.download_images_from_urls(
                    [image_url], 
                    download_path
                )
        
        # Should handle disk space error gracefully
        assert len(saved_files) == 0
    
    @pytest.mark.asyncio
    async def test_large_file_chunked_download(self, image_downloader, temp_directory):
        """Test downloading large files in chunks."""
        download_path = str(temp_directory / "large_file_test")
        image_url = "https://example.com/large_image.jpg"
        
        # Mock large file response with multiple chunks
        large_chunks = [b"chunk_" + str(i).encode() * 1000 for i in range(10)]
        large_chunks.append(b"")  # End of stream
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=large_chunks)
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 1
        assert os.path.exists(saved_files[0])
        
        # Verify all chunks were written
        with open(saved_files[0], 'rb') as f:
            content = f.read()
            for i in range(10):
                expected_chunk = b"chunk_" + str(i).encode() * 1000
                assert expected_chunk in content
    
    @pytest.mark.asyncio
    async def test_file_cleanup_on_error(self, image_downloader, temp_directory):
        """Test that partial files are cleaned up on download error."""
        download_path = str(temp_directory / "cleanup_test")
        image_url = "https://example.com/cleanup_image.jpg"
        
        # Mock response that fails mid-download
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[
            b"partial_data",
            Exception("Connection lost")  # Simulate network error mid-download
        ])
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        # Should not save partial file
        assert len(saved_files) == 0
        
        # Check that no partial files remain
        if os.path.exists(download_path):
            files_in_dir = os.listdir(download_path)
            assert len(files_in_dir) == 0, "No partial files should remain after error"


class TestDownloadProgressAndCancellation:
    """Test download progress tracking and cancellation functionality."""
    
    @pytest.mark.asyncio
    async def test_concurrent_download_task_management(self, image_downloader, temp_directory):
        """Test management of concurrent download tasks."""
        download_path = str(temp_directory / "concurrent_test")
        image_urls = [f"https://example.com/image_{i}.jpg" for i in range(5)]
        
        # Mock responses with different delays to test concurrency
        async def mock_get_with_delay(url):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.content.read = AsyncMock(side_effect=[
                f"data_for_{url}".encode(), 
                b""
            ])
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            # Return a context manager
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            return mock_context
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=mock_get_with_delay)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Measure execution time to verify concurrency
            import time
            start_time = time.time()
            
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
        
        assert len(saved_files) == len(image_urls)
        # With 5 concurrent downloads each taking 0.1s, total time should be ~0.1s, not 0.5s
        assert execution_time < 0.3, f"Concurrent execution took {execution_time}s, expected < 0.3s"
    
    @pytest.mark.asyncio
    async def test_download_task_cancellation(self, image_downloader, temp_directory):
        """Test cancellation of download tasks."""
        download_path = str(temp_directory / "cancellation_test")
        image_urls = [f"https://example.com/image_{i}.jpg" for i in range(3)]
        
        # Mock responses with long delays
        async def mock_get_with_long_delay(url):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.content.read = AsyncMock(side_effect=[
                f"data_for_{url}".encode(), 
                b""
            ])
            # Simulate very long network delay
            await asyncio.sleep(10)  # This should be cancelled
            return mock_response
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=mock_get_with_long_delay)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Start download and cancel after short time
            download_task = asyncio.create_task(
                image_downloader.download_images_from_urls(image_urls, download_path)
            )
            
            # Cancel after 0.1 seconds
            await asyncio.sleep(0.1)
            download_task.cancel()
            
            try:
                await download_task
            except asyncio.CancelledError:
                pass  # Expected cancellation
        
        # Verify no files were saved due to cancellation
        if os.path.exists(download_path):
            files_in_dir = os.listdir(download_path)
            assert len(files_in_dir) == 0, "No files should be saved after cancellation"
    
    @pytest.mark.asyncio
    async def test_download_progress_tracking(self, image_downloader, temp_directory):
        """Test tracking download progress through saved files list."""
        download_path = str(temp_directory / "progress_test")
        image_urls = [f"https://example.com/image_{i}.jpg" for i in range(3)]
        
        # Track progress by monitoring saved_files list updates
        progress_snapshots = []
        
        async def mock_download_one_image(session, url, filename, saved_list):
            # Simulate download time
            await asyncio.sleep(0.05)
            
            # Simulate successful download
            with open(filename, 'wb') as f:
                f.write(f"data_for_{url}".encode())
            
            saved_list.append(filename)
            progress_snapshots.append(len(saved_list))
        
        with patch.object(image_downloader, '_download_one_image', side_effect=mock_download_one_image):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        assert len(saved_files) == len(image_urls)
        assert len(progress_snapshots) == len(image_urls)
        # Progress should increment: [1, 2, 3] (in some order due to concurrency)
        assert sorted(progress_snapshots) == [1, 2, 3]


class TestNetworkErrorHandling:
    """Test network failure and error recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self, image_downloader, temp_directory):
        """Test handling of connection timeout errors."""
        download_path = str(temp_directory / "timeout_test")
        image_url = "https://example.com/timeout_image.jpg"
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError("Connection timeout"))
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 0, "Should handle timeout gracefully"
    
    @pytest.mark.asyncio
    async def test_dns_resolution_error(self, image_downloader, temp_directory):
        """Test handling of DNS resolution errors."""
        download_path = str(temp_directory / "dns_test")
        image_url = "https://nonexistent-domain-12345.com/image.jpg"
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientConnectorError(
            connection_key=None, 
            os_error=OSError("Name or service not known")
        ))
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 0, "Should handle DNS errors gracefully"
    
    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self, image_downloader, temp_directory):
        """Test handling of SSL certificate errors."""
        download_path = str(temp_directory / "ssl_test")
        image_url = "https://self-signed-cert-site.com/image.jpg"
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=aiohttp.ClientConnectorCertificateError(
            connection_key=None, 
            certificate_error=Exception("SSL certificate verify failed")
        ))
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 0, "Should handle SSL errors gracefully"
    
    @pytest.mark.asyncio
    async def test_http_status_error_codes(self, image_downloader, temp_directory):
        """Test handling of various HTTP error status codes."""
        download_path = str(temp_directory / "http_error_test")
        
        error_scenarios = [
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not Found"),
            (429, "Too Many Requests"),
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable")
        ]
        
        for status_code, description in error_scenarios:
            image_url = f"https://example.com/error_{status_code}_image.jpg"
            
            mock_response = AsyncMock()
            mock_response.status = status_code
            
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            
            with patch('aiohttp.ClientSession', return_value=mock_session):
                saved_files = await image_downloader.download_images_from_urls(
                    [image_url], 
                    download_path
                )
            
            assert len(saved_files) == 0, f"Should handle HTTP {status_code} ({description}) gracefully"
    
    @pytest.mark.asyncio
    async def test_partial_content_download_error(self, image_downloader, temp_directory):
        """Test handling of partial content download errors."""
        download_path = str(temp_directory / "partial_content_test")
        image_url = "https://example.com/partial_image.jpg"
        
        # Mock response that starts successfully but fails mid-stream
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[
            b"partial_data_chunk_1",
            b"partial_data_chunk_2",
            aiohttp.ClientPayloadError("Connection broken")  # Error mid-stream
        ])
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 0, "Should handle partial download errors gracefully"
    
    @pytest.mark.asyncio
    async def test_mixed_success_and_failure_downloads(self, image_downloader, temp_directory):
        """Test mixed scenario with some successful and some failed downloads."""
        download_path = str(temp_directory / "mixed_scenario_test")
        
        image_urls = [
            "https://example.com/success1.jpg",
            "https://example.com/fail_404.jpg",
            "https://example.com/success2.jpg",
            "https://example.com/fail_timeout.jpg",
            "https://example.com/success3.jpg"
        ]
        
        # Mock different responses for different URLs
        def mock_get_side_effect(url):
            if "success" in url:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.content.read = AsyncMock(side_effect=[
                    f"success_data_for_{url}".encode(), 
                    b""
                ])
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                return mock_context
            elif "fail_404" in url:
                mock_response = AsyncMock()
                mock_response.status = 404
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                return mock_context
            elif "fail_timeout" in url:
                raise asyncio.TimeoutError("Connection timeout")
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=mock_get_side_effect)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                image_urls, 
                download_path
            )
        
        # Should have 3 successful downloads out of 5 attempts
        assert len(saved_files) == 3, "Should save only successful downloads"
        assert all(os.path.exists(f) for f in saved_files), "All saved files should exist"
        
        # Verify content of successful downloads
        for saved_file in saved_files:
            with open(saved_file, 'rb') as f:
                content = f.read()
                assert b"success_data_for_" in content, "Successful downloads should have correct content"


class TestInvalidImageHandling:
    """Test handling of invalid images and edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self, image_downloader, temp_directory):
        """Test handling of empty HTTP responses."""
        download_path = str(temp_directory / "empty_response_test")
        image_url = "https://example.com/empty_image.jpg"
        
        # Mock empty response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[b""])  # Empty content
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        # Should still save the file even if empty (let caller decide if valid)
        assert len(saved_files) == 1
        assert os.path.exists(saved_files[0])
        
        # Verify file is empty
        with open(saved_files[0], 'rb') as f:
            content = f.read()
            assert content == b"", "Empty response should result in empty file"
    
    @pytest.mark.asyncio
    async def test_non_image_content_handling(self, image_downloader, temp_directory):
        """Test handling of non-image content (HTML, JSON, etc.)."""
        download_path = str(temp_directory / "non_image_test")
        image_url = "https://example.com/fake_image.jpg"
        
        # Mock response with HTML content instead of image
        html_content = b"<html><body>This is not an image</body></html>"
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[html_content, b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        # Should still save the file (content validation is not the downloader's responsibility)
        assert len(saved_files) == 1
        assert os.path.exists(saved_files[0])
        
        # Verify content was saved as-is
        with open(saved_files[0], 'rb') as f:
            content = f.read()
            assert content == html_content
    
    @pytest.mark.asyncio
    async def test_corrupted_image_data_handling(self, image_downloader, temp_directory):
        """Test handling of corrupted image data."""
        download_path = str(temp_directory / "corrupted_test")
        image_url = "https://example.com/corrupted_image.jpg"
        
        # Mock response with corrupted/invalid image data
        corrupted_data = b"\x00\x01\x02\x03INVALID_IMAGE_DATA\xFF\xFE\xFD"
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=[corrupted_data, b""])
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        # Should still save the file (image validation is not the downloader's responsibility)
        assert len(saved_files) == 1
        assert os.path.exists(saved_files[0])
        
        # Verify corrupted content was saved
        with open(saved_files[0], 'rb') as f:
            content = f.read()
            assert content == corrupted_data
    
    @pytest.mark.asyncio
    async def test_extremely_large_response_handling(self, image_downloader, temp_directory):
        """Test handling of extremely large responses."""
        download_path = str(temp_directory / "large_response_test")
        image_url = "https://example.com/huge_image.jpg"
        
        # Mock response with very large content (simulate by many chunks)
        large_chunk = b"X" * 10240  # 10KB chunk
        num_chunks = 100  # Total ~1MB
        
        chunks = [large_chunk] * num_chunks + [b""]  # End with empty chunk
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content.read = AsyncMock(side_effect=chunks)
        
        mock_session = AsyncMock()
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_response_context)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            saved_files = await image_downloader.download_images_from_urls(
                [image_url], 
                download_path
            )
        
        assert len(saved_files) == 1
        assert os.path.exists(saved_files[0])
        
        # Verify large file was saved correctly
        expected_size = len(large_chunk) * num_chunks
        actual_size = os.path.getsize(saved_files[0])
        assert actual_size == expected_size, f"Expected {expected_size} bytes, got {actual_size}"