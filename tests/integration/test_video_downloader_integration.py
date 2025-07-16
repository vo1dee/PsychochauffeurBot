"""
Integration tests for video downloader services.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import httpx

from modules.video_downloader import VideoDownloader, VideoInfo, DownloadResult
from modules.error_handler import StandardError


class TestVideoDownloaderIntegration:
    """Integration tests for video downloader."""
    
    @pytest.fixture
    def temp_download_dir(self):
        """Create a temporary download directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def video_downloader(self, temp_download_dir):
        """Create a VideoDownloader instance."""
        return VideoDownloader(download_dir=temp_download_dir)
    
    @pytest.mark.asyncio
    async def test_youtube_video_info_extraction(self, video_downloader):
        """Test extracting video information from YouTube."""
        # Mock yt-dlp response
        mock_info = {
            'title': 'Test Video Title',
            'duration': 120,
            'uploader': 'Test Channel',
            'view_count': 1000,
            'upload_date': '20240101',
            'formats': [
                {'format_id': '18', 'ext': 'mp4', 'height': 360},
                {'format_id': '22', 'ext': 'mp4', 'height': 720}
            ]
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            video_info = await video_downloader.get_video_info(
                'https://www.youtube.com/watch?v=test123'
            )
            
            assert isinstance(video_info, VideoInfo)
            assert video_info.title == 'Test Video Title'
            assert video_info.duration == 120
            assert video_info.uploader == 'Test Channel'
            assert video_info.view_count == 1000
            assert len(video_info.available_formats) == 2
    
    @pytest.mark.asyncio
    async def test_youtube_video_download(self, video_downloader, temp_download_dir):
        """Test downloading a video from YouTube."""
        # Mock successful download
        mock_info = {
            'title': 'Test Video',
            'duration': 60,
            'uploader': 'Test Channel',
            'id': 'test123'
        }
        
        # Create a fake downloaded file
        fake_file_path = temp_download_dir / 'test_video.mp4'
        fake_file_path.write_bytes(b'fake video content')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            # Mock the file path resolution
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                result = await video_downloader.download_video(
                    'https://www.youtube.com/watch?v=test123'
                )
                
                assert isinstance(result, DownloadResult)
                assert result.success is True
                assert result.file_path == str(fake_file_path)
                assert result.title == 'Test Video'
                assert result.file_size > 0
    
    @pytest.mark.asyncio
    async def test_twitter_video_download(self, video_downloader, temp_download_dir):
        """Test downloading a video from Twitter."""
        mock_info = {
            'title': 'Twitter Video',
            'duration': 30,
            'uploader': 'twitter_user',
            'id': 'twitter123'
        }
        
        fake_file_path = temp_download_dir / 'twitter_video.mp4'
        fake_file_path.write_bytes(b'fake twitter video')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                result = await video_downloader.download_video(
                    'https://twitter.com/user/status/123456789'
                )
                
                assert result.success is True
                assert result.title == 'Twitter Video'
                assert 'twitter' in result.platform.lower()
    
    @pytest.mark.asyncio
    async def test_instagram_video_download(self, video_downloader, temp_download_dir):
        """Test downloading a video from Instagram."""
        mock_info = {
            'title': 'Instagram Video',
            'duration': 45,
            'uploader': 'instagram_user',
            'id': 'instagram123'
        }
        
        fake_file_path = temp_download_dir / 'instagram_video.mp4'
        fake_file_path.write_bytes(b'fake instagram video')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                result = await video_downloader.download_video(
                    'https://www.instagram.com/p/ABC123/'
                )
                
                assert result.success is True
                assert result.title == 'Instagram Video'
    
    @pytest.mark.asyncio
    async def test_tiktok_video_download(self, video_downloader, temp_download_dir):
        """Test downloading a video from TikTok."""
        mock_info = {
            'title': 'TikTok Video',
            'duration': 15,
            'uploader': 'tiktok_user',
            'id': 'tiktok123'
        }
        
        fake_file_path = temp_download_dir / 'tiktok_video.mp4'
        fake_file_path.write_bytes(b'fake tiktok video')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                result = await video_downloader.download_video(
                    'https://www.tiktok.com/@user/video/123456789'
                )
                
                assert result.success is True
                assert result.title == 'TikTok Video'
    
    @pytest.mark.asyncio
    async def test_unsupported_platform(self, video_downloader):
        """Test handling of unsupported platforms."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Unsupported URL")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://unsupported-platform.com/video/123'
            )
            
            assert result.success is False
            assert 'unsupported' in result.error.lower() or 'failed' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, video_downloader):
        """Test handling of network errors during download."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Network error")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=test123'
            )
            
            assert result.success is False
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_download_with_quality_preference(self, video_downloader, temp_download_dir):
        """Test downloading with specific quality preferences."""
        mock_info = {
            'title': 'HD Test Video',
            'duration': 180,
            'uploader': 'Test Channel',
            'id': 'hd_test123',
            'formats': [
                {'format_id': '18', 'ext': 'mp4', 'height': 360, 'filesize': 1000000},
                {'format_id': '22', 'ext': 'mp4', 'height': 720, 'filesize': 3000000},
                {'format_id': '37', 'ext': 'mp4', 'height': 1080, 'filesize': 5000000}
            ]
        }
        
        fake_file_path = temp_download_dir / 'hd_video.mp4'
        fake_file_path.write_bytes(b'fake hd video content')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                # Test downloading with HD preference
                result = await video_downloader.download_video(
                    'https://www.youtube.com/watch?v=test123',
                    quality='720p'
                )
                
                assert result.success is True
                assert result.title == 'HD Test Video'
    
    @pytest.mark.asyncio
    async def test_download_with_audio_only(self, video_downloader, temp_download_dir):
        """Test downloading audio-only content."""
        mock_info = {
            'title': 'Audio Content',
            'duration': 240,
            'uploader': 'Audio Channel',
            'id': 'audio123'
        }
        
        fake_file_path = temp_download_dir / 'audio.mp3'
        fake_file_path.write_bytes(b'fake audio content')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                result = await video_downloader.download_video(
                    'https://www.youtube.com/watch?v=test123',
                    audio_only=True
                )
                
                assert result.success is True
                assert result.file_path.endswith('.mp3')
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads(self, video_downloader, temp_download_dir):
        """Test handling multiple concurrent downloads."""
        async def mock_download(url: str, video_id: str):
            mock_info = {
                'title': f'Video {video_id}',
                'duration': 60,
                'uploader': 'Test Channel',
                'id': video_id
            }
            
            fake_file_path = temp_download_dir / f'video_{video_id}.mp4'
            fake_file_path.write_bytes(f'fake video {video_id}'.encode())
            
            with patch('yt_dlp.YoutubeDL') as mock_ytdl:
                mock_instance = Mock()
                mock_instance.extract_info.return_value = mock_info
                mock_instance.download.return_value = None
                mock_ytdl.return_value.__enter__.return_value = mock_instance
                
                with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_file_path):
                    return await video_downloader.download_video(url)
        
        # Start multiple concurrent downloads
        urls = [
            f'https://www.youtube.com/watch?v=test{i}'
            for i in range(3)
        ]
        
        tasks = [mock_download(url, f'test{i}') for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(result.success for result in results)
        assert all(f'Video test{i}' == results[i].title for i in range(3))
    
    @pytest.mark.asyncio
    async def test_download_size_limit(self, video_downloader):
        """Test download size limit enforcement."""
        mock_info = {
            'title': 'Large Video',
            'duration': 3600,  # 1 hour
            'uploader': 'Test Channel',
            'id': 'large123',
            'filesize': 1000000000  # 1GB
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            # Set a small size limit
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=large123',
                max_file_size=100000000  # 100MB limit
            )
            
            assert result.success is False
            assert 'size' in result.error.lower() or 'large' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_download_duration_limit(self, video_downloader):
        """Test download duration limit enforcement."""
        mock_info = {
            'title': 'Long Video',
            'duration': 7200,  # 2 hours
            'uploader': 'Test Channel',
            'id': 'long123'
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            # Set a short duration limit
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=long123',
                max_duration=3600  # 1 hour limit
            )
            
            assert result.success is False
            assert 'duration' in result.error.lower() or 'long' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_playlist_download(self, video_downloader, temp_download_dir):
        """Test downloading from a playlist."""
        mock_playlist_info = {
            'title': 'Test Playlist',
            'entries': [
                {
                    'title': 'Video 1',
                    'duration': 60,
                    'uploader': 'Test Channel',
                    'id': 'video1'
                },
                {
                    'title': 'Video 2',
                    'duration': 90,
                    'uploader': 'Test Channel',
                    'id': 'video2'
                }
            ]
        }
        
        # Create fake files for each video
        for i in range(2):
            fake_file = temp_download_dir / f'video_{i+1}.mp4'
            fake_file.write_bytes(f'fake video {i+1} content'.encode())
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_playlist_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            results = await video_downloader.download_playlist(
                'https://www.youtube.com/playlist?list=test123'
            )
            
            assert len(results) == 2
            assert all(result.success for result in results)
            assert results[0].title == 'Video 1'
            assert results[1].title == 'Video 2'
    
    @pytest.mark.asyncio
    async def test_download_with_subtitles(self, video_downloader, temp_download_dir):
        """Test downloading video with subtitles."""
        mock_info = {
            'title': 'Video with Subtitles',
            'duration': 120,
            'uploader': 'Test Channel',
            'id': 'subtitles123',
            'subtitles': {
                'en': [{'ext': 'vtt', 'url': 'http://example.com/subtitles.vtt'}]
            }
        }
        
        fake_video_path = temp_download_dir / 'video_with_subs.mp4'
        fake_video_path.write_bytes(b'fake video with subtitles')
        
        fake_sub_path = temp_download_dir / 'video_with_subs.en.vtt'
        fake_sub_path.write_bytes(b'WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest subtitle')
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_info
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=fake_video_path):
                result = await video_downloader.download_video(
                    'https://www.youtube.com/watch?v=subtitles123',
                    download_subtitles=True
                )
                
                assert result.success is True
                assert result.has_subtitles is True
                assert fake_sub_path.exists()


class TestVideoDownloaderErrorHandling:
    """Test error handling in video downloader integration."""
    
    @pytest.fixture
    def video_downloader(self):
        """Create a VideoDownloader instance."""
        return VideoDownloader()
    
    @pytest.mark.asyncio
    async def test_invalid_url_handling(self, video_downloader):
        """Test handling of invalid URLs."""
        invalid_urls = [
            'not_a_url',
            'http://invalid-domain.fake/video',
            'https://www.youtube.com/watch?v=',  # Missing video ID
            ''
        ]
        
        for url in invalid_urls:
            result = await video_downloader.download_video(url)
            assert result.success is False
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_private_video_handling(self, video_downloader):
        """Test handling of private/unavailable videos."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Private video")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=private123'
            )
            
            assert result.success is False
            assert 'private' in result.error.lower() or 'unavailable' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_geo_blocked_content(self, video_downloader):
        """Test handling of geo-blocked content."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Video not available in your country")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=geoblocked123'
            )
            
            assert result.success is False
            assert 'country' in result.error.lower() or 'region' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_copyright_claimed_content(self, video_downloader):
        """Test handling of copyright-claimed content."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Copyright claim")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=copyright123'
            )
            
            assert result.success is False
            assert 'copyright' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, video_downloader):
        """Test handling of rate limiting from platforms."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = Exception("Too many requests")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=ratelimited123'
            )
            
            assert result.success is False
            assert 'rate' in result.error.lower() or 'requests' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_disk_space_error(self, video_downloader):
        """Test handling of insufficient disk space."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.download.side_effect = OSError("No space left on device")
            mock_instance.extract_info.return_value = {
                'title': 'Test Video',
                'duration': 60,
                'id': 'diskspace123'
            }
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=diskspace123'
            )
            
            assert result.success is False
            assert 'space' in result.error.lower() or 'disk' in result.error.lower()


class TestVideoDownloaderPerformance:
    """Performance tests for video downloader integration."""
    
    @pytest.fixture
    def video_downloader(self):
        """Create a VideoDownloader instance."""
        return VideoDownloader()
    
    @pytest.mark.asyncio
    async def test_download_timeout_handling(self, video_downloader):
        """Test handling of download timeouts."""
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            
            async def slow_extract_info(*args, **kwargs):
                await asyncio.sleep(10)  # Simulate very slow response
                return {'title': 'Slow Video', 'duration': 60, 'id': 'slow123'}
            
            mock_instance.extract_info.side_effect = slow_extract_info
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            # Set a short timeout
            start_time = asyncio.get_event_loop().time()
            result = await video_downloader.download_video(
                'https://www.youtube.com/watch?v=slow123',
                timeout=1.0
            )
            end_time = asyncio.get_event_loop().time()
            
            # Should timeout quickly
            assert end_time - start_time < 2.0
            assert result.success is False
            assert 'timeout' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_download_limits(self, video_downloader):
        """Test concurrent download limits."""
        download_count = 0
        
        async def mock_download_with_counter(*args, **kwargs):
            nonlocal download_count
            download_count += 1
            await asyncio.sleep(0.1)  # Simulate download time
            return {
                'title': f'Video {download_count}',
                'duration': 60,
                'id': f'concurrent{download_count}'
            }
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = mock_download_with_counter
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            # Try to start many downloads simultaneously
            urls = [f'https://www.youtube.com/watch?v=test{i}' for i in range(10)]
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=Path('/fake/path.mp4')):
                tasks = [video_downloader.download_video(url) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should handle concurrent downloads gracefully
            successful_results = [r for r in results if isinstance(r, DownloadResult) and r.success]
            assert len(successful_results) > 0  # At least some should succeed
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_large_downloads(self, video_downloader):
        """Test memory usage during large file downloads."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Mock a large file download
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = {
                'title': 'Large Video',
                'duration': 3600,
                'filesize': 1000000000,  # 1GB
                'id': 'large123'
            }
            mock_instance.download.return_value = None
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with patch.object(video_downloader, '_find_downloaded_file', return_value=Path('/fake/large.mp4')):
                result = await video_downloader.download_video(
                    'https://www.youtube.com/watch?v=large123'
                )
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for mocked download)
        assert memory_increase < 100 * 1024 * 1024  # 100MB
        
        # Clean up any remaining references
        del result