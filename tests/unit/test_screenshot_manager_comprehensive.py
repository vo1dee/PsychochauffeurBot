"""
Comprehensive unit tests for ScreenshotManager functionality.

This module provides comprehensive testing for the ScreenshotManager class including:
- Screenshot generation and error handling
- Directory management and permissions
- Freshness validation
- Tool availability checks
- Error recovery scenarios

Requirements addressed: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
"""

import pytest
import asyncio
import sys
import os
import tempfile
import shutil
import subprocess
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.utils import ScreenshotManager
from modules.const import Config, KYIV_TZ
from tests.base_test_classes import AsyncBaseTestCase


class TestScreenshotManagerComprehensive(AsyncBaseTestCase):
    """Comprehensive test cases for ScreenshotManager class."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.original_screenshot_dir = Config.SCREENSHOT_DIR
        Config.SCREENSHOT_DIR = os.path.join(self.temp_dir, 'screenshots')
        
        # Reset singleton instance for testing
        ScreenshotManager._instance = None
        self.manager = ScreenshotManager()
    
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
        # Restore original screenshot directory
        Config.SCREENSHOT_DIR = self.original_screenshot_dir
        
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Reset singleton instance
        ScreenshotManager._instance = None
    
    def test_screenshot_manager_singleton(self):
        """Test that ScreenshotManager is a singleton."""
        manager1 = ScreenshotManager()
        manager2 = ScreenshotManager()
        
        assert manager1 is manager2
        assert id(manager1) == id(manager2)
    
    def test_screenshot_manager_initialization(self):
        """Test ScreenshotManager initialization."""
        assert self.manager.timezone is not None
        assert self.manager.schedule_time is not None
        assert self.manager.FRESHNESS_THRESHOLD_HOURS == 6
    
    def test_check_wkhtmltoimage_availability_success(self):
        """Test successful wkhtmltoimage availability check."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            result = self.manager._check_wkhtmltoimage_availability()
            
            assert result is True
            mock_run.assert_called_once()
    
    def test_check_wkhtmltoimage_availability_failure(self):
        """Test wkhtmltoimage availability check failure scenarios."""
        # Test command not found
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = self.manager._check_wkhtmltoimage_availability()
            assert result is False
        
        # Test command returns non-zero exit code
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            result = self.manager._check_wkhtmltoimage_availability()
            assert result is False
        
        # Test timeout
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('cmd', 10)):
            result = self.manager._check_wkhtmltoimage_availability()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_ensure_screenshot_directory_success(self):
        """Test successful screenshot directory creation."""
        # Ensure directory doesn't exist initially
        if os.path.exists(Config.SCREENSHOT_DIR):
            shutil.rmtree(Config.SCREENSHOT_DIR)
        
        result = await self.manager.ensure_screenshot_directory()
        
        assert result is True
        assert os.path.exists(Config.SCREENSHOT_DIR)
        assert os.path.isdir(Config.SCREENSHOT_DIR)
        assert os.access(Config.SCREENSHOT_DIR, os.R_OK | os.W_OK | os.X_OK)
    
    @pytest.mark.asyncio
    async def test_ensure_screenshot_directory_already_exists(self):
        """Test screenshot directory handling when it already exists."""
        # Create directory first
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        result = await self.manager.ensure_screenshot_directory()
        
        assert result is True
        assert os.path.exists(Config.SCREENSHOT_DIR)
    
    @pytest.mark.asyncio
    async def test_ensure_screenshot_directory_permission_error(self):
        """Test screenshot directory creation with permission errors."""
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            result = await self.manager.ensure_screenshot_directory()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_ensure_screenshot_directory_file_exists_as_directory(self):
        """Test handling when a file exists where directory should be."""
        # Create a file where directory should be
        os.makedirs(os.path.dirname(Config.SCREENSHOT_DIR), exist_ok=True)
        with open(Config.SCREENSHOT_DIR, 'w') as f:
            f.write('test')
        
        result = await self.manager.ensure_screenshot_directory()
        
        assert result is False
    
    def test_get_screenshot_path(self):
        """Test screenshot path generation."""
        path = self.manager.get_screenshot_path()
        
        assert path.startswith(Config.SCREENSHOT_DIR)
        assert path.endswith('.png')
        assert 'flares_' in path
        assert '_kyiv.png' in path
        
        # Check date format in path
        kyiv_time = datetime.now(KYIV_TZ)
        expected_date = kyiv_time.strftime('%Y-%m-%d')
        assert expected_date in path
    
    def test_validate_screenshot_freshness_fresh_screenshot(self):
        """Test freshness validation for fresh screenshot."""
        # Create a fresh screenshot file
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'test_fresh.png')
        
        with open(screenshot_path, 'w') as f:
            f.write('test screenshot')
        
        # Set modification time to 1 hour ago (fresh)
        one_hour_ago = datetime.now().timestamp() - 3600
        os.utime(screenshot_path, (one_hour_ago, one_hour_ago))
        
        result = self.manager.validate_screenshot_freshness(screenshot_path)
        
        assert result is True
    
    def test_validate_screenshot_freshness_stale_screenshot(self):
        """Test freshness validation for stale screenshot."""
        # Create a stale screenshot file
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'test_stale.png')
        
        with open(screenshot_path, 'w') as f:
            f.write('test screenshot')
        
        # Set modification time to 8 hours ago (stale)
        eight_hours_ago = datetime.now().timestamp() - (8 * 3600)
        os.utime(screenshot_path, (eight_hours_ago, eight_hours_ago))
        
        result = self.manager.validate_screenshot_freshness(screenshot_path)
        
        assert result is False
    
    def test_validate_screenshot_freshness_nonexistent_file(self):
        """Test freshness validation for nonexistent file."""
        nonexistent_path = os.path.join(Config.SCREENSHOT_DIR, 'nonexistent.png')
        
        result = self.manager.validate_screenshot_freshness(nonexistent_path)
        
        assert result is False
    
    def test_validate_screenshot_freshness_error_handling(self):
        """Test freshness validation error handling."""
        with patch('os.path.exists', return_value=True):
            with patch('os.path.getmtime', side_effect=OSError("Permission denied")):
                result = self.manager.validate_screenshot_freshness('test_path')
                assert result is False
    
    def test_get_latest_screenshot_success(self):
        """Test getting latest screenshot when files exist."""
        # Create screenshot directory and files
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        # Create multiple screenshot files with different timestamps
        files = ['screenshot1.png', 'screenshot2.png', 'screenshot3.png']
        file_paths = []
        
        for i, filename in enumerate(files):
            file_path = os.path.join(Config.SCREENSHOT_DIR, filename)
            with open(file_path, 'w') as f:
                f.write(f'screenshot {i}')
            
            # Set different creation times
            timestamp = datetime.now().timestamp() - (i * 3600)  # Each file 1 hour older
            os.utime(file_path, (timestamp, timestamp))
            file_paths.append(file_path)
        
        result = self.manager.get_latest_screenshot()
        
        assert result is not None
        assert result in file_paths
        assert result.endswith('.png')
    
    def test_get_latest_screenshot_no_directory(self):
        """Test getting latest screenshot when directory doesn't exist."""
        # Ensure directory doesn't exist
        if os.path.exists(Config.SCREENSHOT_DIR):
            shutil.rmtree(Config.SCREENSHOT_DIR)
        
        result = self.manager.get_latest_screenshot()
        
        assert result is None
    
    def test_get_latest_screenshot_no_files(self):
        """Test getting latest screenshot when no PNG files exist."""
        # Create empty directory
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        
        # Create non-PNG file
        with open(os.path.join(Config.SCREENSHOT_DIR, 'not_a_screenshot.txt'), 'w') as f:
            f.write('not a screenshot')
        
        result = self.manager.get_latest_screenshot()
        
        assert result is None
    
    def test_get_latest_screenshot_error_handling(self):
        """Test get_latest_screenshot error handling."""
        with patch('os.path.exists', return_value=True):
            with patch('os.listdir', side_effect=OSError("Permission denied")):
                result = self.manager.get_latest_screenshot()
                assert result is None
    
    @pytest.mark.asyncio
    async def test_get_current_screenshot_fresh_exists(self):
        """Test get_current_screenshot when fresh screenshot exists."""
        # Create fresh screenshot
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'fresh_screenshot.png')
        
        with open(screenshot_path, 'w') as f:
            f.write('fresh screenshot')
        
        # Set modification time to 1 hour ago (fresh)
        one_hour_ago = datetime.now().timestamp() - 3600
        os.utime(screenshot_path, (one_hour_ago, one_hour_ago))
        
        with patch.object(self.manager, 'get_latest_screenshot', return_value=screenshot_path):
            result = await self.manager.get_current_screenshot()
            
            assert result == screenshot_path
    
    @pytest.mark.asyncio
    async def test_get_current_screenshot_stale_regenerate(self):
        """Test get_current_screenshot when stale screenshot needs regeneration."""
        # Create stale screenshot
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        old_screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'old_screenshot.png')
        new_screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'new_screenshot.png')
        
        with open(old_screenshot_path, 'w') as f:
            f.write('old screenshot')
        
        # Set modification time to 8 hours ago (stale)
        eight_hours_ago = datetime.now().timestamp() - (8 * 3600)
        os.utime(old_screenshot_path, (eight_hours_ago, eight_hours_ago))
        
        with patch.object(self.manager, 'get_latest_screenshot', return_value=old_screenshot_path):
            with patch.object(self.manager, 'take_screenshot', return_value=new_screenshot_path) as mock_take:
                result = await self.manager.get_current_screenshot()
                
                assert result == new_screenshot_path
                mock_take.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_current_screenshot_no_existing(self):
        """Test get_current_screenshot when no screenshot exists."""
        new_screenshot_path = os.path.join(Config.SCREENSHOT_DIR, 'new_screenshot.png')
        
        with patch.object(self.manager, 'get_latest_screenshot', return_value=None):
            with patch.object(self.manager, 'take_screenshot', return_value=new_screenshot_path) as mock_take:
                result = await self.manager.get_current_screenshot()
                
                assert result == new_screenshot_path
                mock_take.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_current_screenshot_directory_creation_fails(self):
        """Test get_current_screenshot when directory creation fails."""
        with patch.object(self.manager, 'ensure_screenshot_directory', return_value=False):
            result = await self.manager.get_current_screenshot()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_simple_success(self):
        """Test simple screenshot taking success."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        # Mock imgkit and config
        mock_config = Mock()
        self.manager.config = mock_config
        
        with patch('imgkit.from_url') as mock_imgkit:
            with patch('os.path.exists', return_value=True):
                with patch('os.path.getsize', return_value=5000):  # 5KB file
                    with patch('os.rename'):
                        result = await self.manager.take_screenshot_simple(url, output_path)
                        
                        assert result == output_path
                        mock_imgkit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_take_screenshot_simple_no_config(self):
        """Test simple screenshot taking when config is None."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        self.manager.config = None
        
        result = await self.manager.take_screenshot_simple(url, output_path)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_simple_imgkit_error(self):
        """Test simple screenshot taking with imgkit error."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        mock_config = Mock()
        self.manager.config = mock_config
        
        with patch('imgkit.from_url', side_effect=Exception("imgkit error")):
            result = await self.manager.take_screenshot_simple(url, output_path)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_success(self):
        """Test successful screenshot taking."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=True):
            with patch.object(self.manager, 'ensure_screenshot_directory', return_value=True):
                with patch.object(self.manager, 'take_screenshot_simple', return_value=output_path):
                    with patch.object(self.manager, '_validate_screenshot_content', return_value=True):
                        result = await self.manager.take_screenshot(url, output_path)
                        
                        assert result == output_path
    
    @pytest.mark.asyncio
    async def test_take_screenshot_tool_unavailable(self):
        """Test screenshot taking when tool is unavailable."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=False):
            result = await self.manager.take_screenshot(url, output_path)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_invalid_inputs(self):
        """Test screenshot taking with invalid inputs."""
        # Test empty URL
        result = await self.manager.take_screenshot("", "output.png")
        assert result is None
        
        # Test empty output path
        result = await self.manager.take_screenshot("https://example.com", "")
        assert result is None
        
        # Test None inputs
        result = await self.manager.take_screenshot(None, "output.png")
        assert result is None
        
        result = await self.manager.take_screenshot("https://example.com", None)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_directory_creation_fails(self):
        """Test screenshot taking when directory creation fails."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=True):
            with patch.object(self.manager, 'ensure_screenshot_directory', return_value=False):
                result = await self.manager.take_screenshot(url, output_path)
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_take_screenshot_with_retries(self):
        """Test screenshot taking with retry logic."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        # Mock to fail first time, succeed second time
        call_count = 0
        
        async def mock_take_simple(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Fail first time
            return output_path  # Succeed second time
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=True):
            with patch.object(self.manager, 'ensure_screenshot_directory', return_value=True):
                with patch.object(self.manager, 'take_screenshot_simple', side_effect=mock_take_simple):
                    with patch.object(self.manager, '_validate_screenshot_content', return_value=True):
                        result = await self.manager.take_screenshot(url, output_path, max_retries=3)
                        
                        assert result == output_path
                        assert call_count >= 1
    
    def test_screenshot_manager_thread_safety(self):
        """Test ScreenshotManager thread safety."""
        import threading
        
        instances = []
        
        def create_instance():
            instance = ScreenshotManager()
            instances.append(instance)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all instances are the same (singleton)
        assert len(instances) == 5
        for instance in instances:
            assert instance is instances[0]
    
    @pytest.mark.asyncio
    async def test_screenshot_manager_performance(self):
        """Test ScreenshotManager performance with multiple operations."""
        import time
        
        # Test multiple path generations
        start_time = time.time()
        paths = []
        for _ in range(100):
            path = self.manager.get_screenshot_path()
            paths.append(path)
        path_generation_time = time.time() - start_time
        
        assert path_generation_time < 1.0  # Should complete within 1 second
        assert len(set(paths)) <= 2  # Should have at most 2 unique paths (date might change)
        
        # Test multiple freshness validations
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        test_file = os.path.join(Config.SCREENSHOT_DIR, 'perf_test.png')
        with open(test_file, 'w') as f:
            f.write('test')
        
        start_time = time.time()
        for _ in range(100):
            self.manager.validate_screenshot_freshness(test_file)
        validation_time = time.time() - start_time
        
        assert validation_time < 1.0  # Should complete within 1 second
    
    @pytest.mark.asyncio
    async def test_screenshot_manager_memory_usage(self):
        """Test ScreenshotManager memory usage doesn't grow excessively."""
        import gc
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Perform many operations
        for i in range(100):
            path = self.manager.get_screenshot_path()
            self.manager.validate_screenshot_freshness(path)
            await self.manager.ensure_screenshot_directory()
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage shouldn't grow significantly
        object_growth = final_objects - initial_objects
        assert object_growth < 50, f"Memory usage grew by {object_growth} objects"


class TestScreenshotManagerErrorScenarios(AsyncBaseTestCase):
    """Test error scenarios and edge cases for ScreenshotManager."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.original_screenshot_dir = Config.SCREENSHOT_DIR
        Config.SCREENSHOT_DIR = os.path.join(self.temp_dir, 'screenshots')
        
        # Reset singleton instance for testing
        ScreenshotManager._instance = None
        self.manager = ScreenshotManager()
    
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
        Config.SCREENSHOT_DIR = self.original_screenshot_dir
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        ScreenshotManager._instance = None
    
    @pytest.mark.asyncio
    async def test_concurrent_screenshot_operations(self):
        """Test concurrent screenshot operations."""
        tasks = []
        
        # Create multiple concurrent operations
        for i in range(5):
            task = self.manager.ensure_screenshot_directory()
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed or at least not crash
        for result in results:
            assert not isinstance(result, Exception) or isinstance(result, (OSError, PermissionError))
    
    @pytest.mark.asyncio
    async def test_disk_space_exhaustion_simulation(self):
        """Test behavior when disk space is exhausted."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=True):
            with patch.object(self.manager, 'ensure_screenshot_directory', return_value=True):
                with patch('imgkit.from_url', side_effect=OSError("No space left on device")):
                    result = await self.manager.take_screenshot_simple(url, output_path)
                    
                    assert result is None
    
    @pytest.mark.asyncio
    async def test_network_timeout_simulation(self):
        """Test behavior during network timeouts."""
        url = "https://example.com"
        output_path = os.path.join(Config.SCREENSHOT_DIR, 'test_screenshot.png')
        
        with patch.object(self.manager, '_check_wkhtmltoimage_availability', return_value=True):
            with patch.object(self.manager, 'ensure_screenshot_directory', return_value=True):
                with patch('imgkit.from_url', side_effect=Exception("Network timeout")):
                    result = await self.manager.take_screenshot_simple(url, output_path)
                    
                    assert result is None
    
    def test_corrupted_screenshot_file_handling(self):
        """Test handling of corrupted screenshot files."""
        # Create corrupted file
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        corrupted_path = os.path.join(Config.SCREENSHOT_DIR, 'corrupted.png')
        
        with open(corrupted_path, 'wb') as f:
            f.write(b'corrupted data')
        
        # Test freshness validation on corrupted file
        result = self.manager.validate_screenshot_freshness(corrupted_path)
        
        # Should handle gracefully (return False or True based on timestamp)
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_permission_denied_scenarios(self):
        """Test various permission denied scenarios."""
        # Test directory creation with permission denied
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            result = await self.manager.ensure_screenshot_directory()
            assert result is False
        
        # Test file access with permission denied
        with patch('os.path.getmtime', side_effect=PermissionError("Permission denied")):
            result = self.manager.validate_screenshot_freshness('test_path')
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])