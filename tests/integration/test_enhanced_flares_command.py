"""
Integration tests for enhanced flares command with screenshot generation scenarios.

This module provides comprehensive integration testing for the enhanced flares command including:
- Screenshot generation and management
- Tool availability checks
- Error handling and recovery
- Performance monitoring
- External service integration

Requirements addressed: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5
"""

import pytest
import asyncio
import sys
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.enhanced_flares_command import EnhancedFlaresCommand, enhanced_flares_command
from modules.utils import ScreenshotManager
from modules.const import Config, KYIV_TZ
from tests.base_test_classes import AsyncBaseTestCase


class TestEnhancedFlaresCommandIntegration(AsyncBaseTestCase):
    """Integration tests for enhanced flares command with real screenshot scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.enhanced_flares = EnhancedFlaresCommand()
        self.chat_id = -1001234567890
        self.user_id = 12345
        self.username = "testuser"
        
        # Set up temporary directory for screenshots
        self.temp_dir = tempfile.mkdtemp()
        self.original_screenshot_dir = Config.SCREENSHOT_DIR
        Config.SCREENSHOT_DIR = os.path.join(self.temp_dir, 'screenshots')
        
        # Reset ScreenshotManager singleton
        ScreenshotManager._instance = None
    
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
    
    def create_mock_update_and_context(self):
        """Create mock update and context objects."""
        # Create mock user
        mock_user = Mock()
        mock_user.id = self.user_id
        mock_user.username = self.username
        
        # Create mock chat
        mock_chat = Mock()
        mock_chat.id = self.chat_id
        
        # Create mock message
        mock_message = AsyncMock()
        mock_message.reply_text = AsyncMock()
        mock_message.delete = AsyncMock()
        
        # Create mock update
        mock_update = Mock()
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        # Create mock bot
        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock()
        
        # Create mock context
        mock_context = Mock()
        mock_context.bot = mock_bot
        
        return mock_update, mock_context
    
    def create_fresh_screenshot(self, filename='fresh_screenshot.png'):
        """Create a fresh screenshot file for testing."""
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, filename)
        
        # Create a dummy PNG file
        with open(screenshot_path, 'wb') as f:
            # Write minimal PNG header
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        # Set modification time to 1 hour ago (fresh)
        one_hour_ago = datetime.now().timestamp() - 3600
        os.utime(screenshot_path, (one_hour_ago, one_hour_ago))
        
        return screenshot_path
    
    def create_stale_screenshot(self, filename='stale_screenshot.png'):
        """Create a stale screenshot file for testing."""
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, filename)
        
        # Create a dummy PNG file
        with open(screenshot_path, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        # Set modification time to 8 hours ago (stale)
        eight_hours_ago = datetime.now().timestamp() - (8 * 3600)
        os.utime(screenshot_path, (eight_hours_ago, eight_hours_ago))
        
        return screenshot_path
    
    @pytest.mark.asyncio
    async def test_flares_command_fresh_screenshot_success(self):
        """Test successful flares command with fresh screenshot."""
        mock_update, mock_context = self.create_mock_update_and_context()
        fresh_screenshot = self.create_fresh_screenshot()
        
        # Mock configuration and dependencies
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command
                await self.enhanced_flares.flares_command(mock_update, mock_context)
                
                # Verify photo was sent
                mock_context.bot.send_photo.assert_called_once()
                call_args = mock_context.bot.send_photo.call_args
                
                assert call_args[1]['chat_id'] == self.chat_id
                assert 'caption' in call_args[1]
                caption = call_args[1]['caption']
                assert "🌞 Прогноз сонячних спалахів" in caption
                assert "актуальний" in caption
    
    @pytest.mark.asyncio
    async def test_flares_command_stale_screenshot_regeneration(self):
        """Test flares command with stale screenshot requiring regeneration."""
        mock_update, mock_context = self.create_mock_update_and_context()
        stale_screenshot = self.create_stale_screenshot()
        new_screenshot = os.path.join(Config.SCREENSHOT_DIR, 'new_screenshot.png')
        
        # Create new screenshot file
        with open(new_screenshot, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        # Mock screenshot generation
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                return_value=new_screenshot) as mock_get_screenshot:
                    
                    # Execute command
                    await self.enhanced_flares.flares_command(mock_update, mock_context)
                    
                    # Verify screenshot generation was called
                    mock_get_screenshot.assert_called_once()
                    
                    # Verify photo was sent
                    mock_context.bot.send_photo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_flares_command_no_existing_screenshot(self):
        """Test flares command when no screenshot exists."""
        mock_update, mock_context = self.create_mock_update_and_context()
        new_screenshot = os.path.join(Config.SCREENSHOT_DIR, 'generated_screenshot.png')
        
        # Create new screenshot file
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        with open(new_screenshot, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        # Mock screenshot generation
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                return_value=new_screenshot):
                    
                    # Execute command
                    await self.enhanced_flares.flares_command(mock_update, mock_context)
                    
                    # Verify photo was sent
                    mock_context.bot.send_photo.assert_called_once()
                    call_args = mock_context.bot.send_photo.call_args
                    caption = call_args[1]['caption']
                    assert "🌞 Прогноз сонячних спалахів" in caption
    
    @pytest.mark.asyncio
    async def test_flares_command_tool_unavailable(self):
        """Test flares command when wkhtmltoimage tool is unavailable."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock tool unavailability
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=False):
                    
                    # Execute command
                    await self.enhanced_flares.flares_command(mock_update, mock_context)
                    
                    # Verify error message was sent
                    mock_update.message.reply_text.assert_called_once()
                    call_args = mock_update.message.reply_text.call_args[0][0]
                    assert "❌" in call_args
                    assert "Інструмент для створення знімків недоступний" in call_args
    
    @pytest.mark.asyncio
    async def test_flares_command_screenshot_generation_failure(self):
        """Test flares command when screenshot generation fails."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock screenshot generation failure
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=True):
                    with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                    return_value=None):
                        
                        # Execute command
                        await self.enhanced_flares.flares_command(mock_update, mock_context)
                        
                        # Verify error message was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "Не вдалося створити або знайти знімок" in call_args
    
    @pytest.mark.asyncio
    async def test_flares_command_configuration_invalid(self):
        """Test flares command when configuration is invalid."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock invalid configuration
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": False, "issues": ["Config error"]})):
            
            # Execute command
            await self.enhanced_flares.flares_command(mock_update, mock_context)
            
            # Verify error message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "Конфігурація команди flares містить помилки" in call_args
    
    @pytest.mark.asyncio
    async def test_flares_command_dependencies_unhealthy(self):
        """Test flares command when dependencies are unhealthy."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock unhealthy dependencies
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": False, "dependencies": {"tool": False}})):
                
                # Execute command
                await self.enhanced_flares.flares_command(mock_update, mock_context)
                
                # Verify error message was sent
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "❌" in call_args
                assert "сервіси, необхідні для отримання знімків, недоступні" in call_args
    
    @pytest.mark.asyncio
    async def test_flares_command_send_photo_failure(self):
        """Test flares command when sending photo fails."""
        mock_update, mock_context = self.create_mock_update_and_context()
        fresh_screenshot = self.create_fresh_screenshot()
        
        # Mock send_photo failure
        mock_context.bot.send_photo.side_effect = Exception("Failed to send photo")
        
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command
                await self.enhanced_flares.flares_command(mock_update, mock_context)
                
                # Verify error message was sent
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "❌" in call_args
                assert "Не вдалося надіслати знімок" in call_args
    
    @pytest.mark.asyncio
    async def test_flares_command_status_message_handling(self):
        """Test flares command status message creation and cleanup."""
        mock_update, mock_context = self.create_mock_update_and_context()
        fresh_screenshot = self.create_fresh_screenshot()
        
        # Mock status message
        mock_status_msg = AsyncMock()
        mock_status_msg.edit_text = AsyncMock()
        mock_status_msg.delete = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg
        
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, 'get_screenshot_status_info',
                                return_value={
                                    'tool_available': True,
                                    'directory_exists': True,
                                    'has_screenshot': True,
                                    'is_fresh': True,
                                    'age_hours': 1.0
                                }):
                    
                    # Execute command
                    await self.enhanced_flares.flares_command(mock_update, mock_context)
                    
                    # Verify status message was created and deleted
                    mock_update.message.reply_text.assert_called()
                    mock_status_msg.delete.assert_called_once()
                    
                    # Verify photo was sent
                    mock_context.bot.send_photo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_flares_command_performance_metrics(self):
        """Test that performance metrics are logged correctly."""
        mock_update, mock_context = self.create_mock_update_and_context()
        fresh_screenshot = self.create_fresh_screenshot()
        
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch('modules.enhanced_flares_command.log_command_performance_metric') as mock_metric:
                    
                    # Execute command
                    await self.enhanced_flares.flares_command(mock_update, mock_context)
                    
                    # Verify performance metrics were logged
                    assert mock_metric.call_count >= 2  # At least file size and age metrics
    
    @pytest.mark.asyncio
    async def test_flares_command_concurrent_requests(self):
        """Test flares command handling concurrent requests."""
        fresh_screenshot = self.create_fresh_screenshot()
        
        # Create multiple concurrent requests
        tasks = []
        mock_updates = []
        mock_contexts = []
        
        for i in range(3):
            mock_update, mock_context = self.create_mock_update_and_context()
            mock_update.effective_user.id = self.user_id + i  # Different users
            mock_updates.append(mock_update)
            mock_contexts.append(mock_context)
            
            # Create task
            task = self.enhanced_flares.flares_command(mock_update, mock_context)
            tasks.append(task)
        
        # Mock all dependencies
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute all tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify all completed successfully
                for i, result in enumerate(results):
                    assert not isinstance(result, Exception), f"Task {i} failed: {result}"
                    mock_contexts[i].bot.send_photo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_flares_command_large_screenshot_handling(self):
        """Test flares command with large screenshot files."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Create large screenshot file (simulate 5MB)
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        large_screenshot = os.path.join(Config.SCREENSHOT_DIR, 'large_screenshot.png')
        
        with open(large_screenshot, 'wb') as f:
            # Write 5MB of data
            f.write(b'\x89PNG\r\n\x1a\n')  # PNG header
            f.write(b'0' * (5 * 1024 * 1024))  # 5MB of data
        
        # Set fresh timestamp
        one_hour_ago = datetime.now().timestamp() - 3600
        os.utime(large_screenshot, (one_hour_ago, one_hour_ago))
        
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command with timeout
                await asyncio.wait_for(
                    self.enhanced_flares.flares_command(mock_update, mock_context),
                    timeout=30.0  # Should complete within 30 seconds
                )
                
                # Verify photo was sent
                mock_context.bot.send_photo.assert_called_once()
                call_args = mock_context.bot.send_photo.call_args
                caption = call_args[1]['caption']
                assert "5.0 MB" in caption  # Should show file size
    
    @pytest.mark.asyncio
    async def test_flares_command_caption_content(self):
        """Test flares command caption content and formatting."""
        mock_update, mock_context = self.create_mock_update_and_context()
        fresh_screenshot = self.create_fresh_screenshot()
        
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command
                await self.enhanced_flares.flares_command(mock_update, mock_context)
                
                # Verify photo was sent with proper caption
                mock_context.bot.send_photo.assert_called_once()
                call_args = mock_context.bot.send_photo.call_args
                caption = call_args[1]['caption']
                
                # Check caption content
                assert "🌞 Прогноз сонячних спалахів і магнітних бурь" in caption
                assert "📅 Час знімку:" in caption
                assert "📊 Статус:" in caption
                assert "🔄 Наступне оновлення:" in caption
                assert "📁 Розмір файлу:" in caption
                assert "🔗 Джерело: api.meteoagent.com" in caption
                assert "актуальний" in caption or "застарілий" in caption


class TestEnhancedFlaresCommandErrorSimulation(AsyncBaseTestCase):
    """Test error simulation scenarios for enhanced flares command."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.enhanced_flares = EnhancedFlaresCommand()
        self.temp_dir = tempfile.mkdtemp()
        self.original_screenshot_dir = Config.SCREENSHOT_DIR
        Config.SCREENSHOT_DIR = os.path.join(self.temp_dir, 'screenshots')
        ScreenshotManager._instance = None
    
    def tearDown(self):
        """Clean up test environment."""
        super().tearDown()
        Config.SCREENSHOT_DIR = self.original_screenshot_dir
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        ScreenshotManager._instance = None
    
    def create_mock_update_and_context(self):
        """Create mock update and context objects."""
        # Create mock user
        mock_user = Mock()
        mock_user.id = 12345
        mock_user.username = "testuser"
        
        # Create mock chat
        mock_chat = Mock()
        mock_chat.id = -1001234567890
        
        # Create mock message
        mock_message = AsyncMock()
        mock_message.reply_text = AsyncMock()
        mock_message.delete = AsyncMock()
        
        # Create mock update
        mock_update = Mock()
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        # Create mock bot
        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock()
        
        # Create mock context
        mock_context = Mock()
        mock_context.bot = mock_bot
        
        return mock_update, mock_context
    
    @pytest.mark.asyncio
    async def test_network_timeout_during_screenshot_generation(self):
        """Test network timeout during screenshot generation."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock network timeout
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=True):
                    with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                    side_effect=asyncio.TimeoutError("Network timeout")):
                        
                        # Execute command
                        await self.enhanced_flares.flares_command(mock_update, mock_context)
                        
                        # Verify timeout error was handled gracefully
                        mock_update.message.reply_text.assert_called()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "мережевим підключенням" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_disk_space_exhaustion_during_screenshot(self):
        """Test disk space exhaustion during screenshot generation."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock disk space exhaustion
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=True):
                    with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                    side_effect=OSError("No space left on device")):
                        
                        # Execute command
                        await self.enhanced_flares.flares_command(mock_update, mock_context)
                        
                        # Verify error was handled gracefully
                        mock_update.message.reply_text.assert_called()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
    
    @pytest.mark.asyncio
    async def test_api_service_unavailable(self):
        """Test API service unavailability."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock API service unavailable
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=True):
                    with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                    side_effect=Exception("API service unavailable")):
                        
                        # Execute command
                        await self.enhanced_flares.flares_command(mock_update, mock_context)
                        
                        # Verify error was handled gracefully
                        mock_update.message.reply_text.assert_called()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
    
    @pytest.mark.asyncio
    async def test_permission_denied_screenshot_directory(self):
        """Test permission denied when accessing screenshot directory."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock permission denied
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability', 
                                return_value=True):
                    with patch.object(ScreenshotManager, 'get_current_screenshot', 
                                    side_effect=PermissionError("Permission denied")):
                        
                        # Execute command
                        await self.enhanced_flares.flares_command(mock_update, mock_context)
                        
                        # Verify error was handled gracefully
                        mock_update.message.reply_text.assert_called()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "файловою системою" in call_args.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])