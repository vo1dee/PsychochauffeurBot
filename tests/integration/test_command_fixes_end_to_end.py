"""
End-to-end tests for complete command execution workflows.

This module provides comprehensive end-to-end testing for the command fixes including:
- Complete analyze command workflows
- Complete flares command workflows
- Error recovery scenarios
- Performance validation
- Integration between all components

Requirements addressed: All requirements validation
"""

import pytest
import asyncio
import sys
import os
import tempfile
import shutil
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.enhanced_analyze_command import enhanced_analyze_command
from modules.enhanced_flares_command import enhanced_flares_command
from modules.utils import DateParser, ScreenshotManager
from modules.const import Config, KYIV_TZ
from tests.base_test_classes import AsyncBaseTestCase


class TestCommandFixesEndToEnd(AsyncBaseTestCase):
    """End-to-end tests for complete command execution workflows."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
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
    
    def create_mock_telegram_objects(self, command_args=None):
        """Create comprehensive mock Telegram objects."""
        # Create mock user
        mock_user = Mock()
        mock_user.id = self.user_id
        mock_user.username = self.username
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.language_code = "uk"
        
        # Create mock chat
        mock_chat = Mock()
        mock_chat.id = self.chat_id
        mock_chat.type = "supergroup"
        mock_chat.title = "Test Group"
        
        # Create mock message
        mock_message = AsyncMock()
        mock_message.message_id = 12345
        mock_message.date = datetime.now(KYIV_TZ)
        mock_message.chat = mock_chat
        mock_message.from_user = mock_user
        mock_message.text = f"/analyze {' '.join(command_args or [])}"
        mock_message.reply_text = AsyncMock()
        mock_message.delete = AsyncMock()
        
        # Create mock update
        mock_update = Mock()
        mock_update.update_id = 1
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        # Create mock bot
        mock_bot = AsyncMock()
        mock_bot.id = 987654321
        mock_bot.username = "test_bot"
        mock_bot.first_name = "Test Bot"
        mock_bot.send_message = AsyncMock()
        mock_bot.send_photo = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=mock_bot)
        
        # Create mock context
        mock_context = Mock()
        mock_context.bot = mock_bot
        mock_context.args = command_args or []
        mock_context.user_data = {}
        mock_context.chat_data = {}
        mock_context.bot_data = {}
        
        return mock_update, mock_context, mock_bot
    
    def create_sample_messages(self, count=10, days_back=0):
        """Create sample messages for testing."""
        messages = []
        base_time = datetime.now(KYIV_TZ) - timedelta(days=days_back)
        
        for i in range(count):
            message = {
                'message_id': i + 1,
                'chat_id': self.chat_id,
                'user_id': self.user_id + (i % 3),  # Vary users
                'username': f'user{i % 3}',
                'message_text': f'Test message {i + 1} with some content for analysis. This is message number {i + 1}.',
                'timestamp': (base_time + timedelta(minutes=i * 10)).isoformat(),
                'created_at': base_time + timedelta(minutes=i * 10)
            }
            messages.append(message)
        
        return messages
    
    def create_screenshot_file(self, filename='test_screenshot.png', fresh=True):
        """Create a test screenshot file."""
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        screenshot_path = os.path.join(Config.SCREENSHOT_DIR, filename)
        
        # Create a minimal valid PNG file
        png_data = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR'  # IHDR chunk
            b'\x00\x00\x00\x64'  # Width: 100
            b'\x00\x00\x00\x64'  # Height: 100
            b'\x08\x02\x00\x00\x00'  # Bit depth, color type, compression, filter, interlace
            b'\x4c\x8f\x02\x8e'  # CRC
            b'\x00\x00\x00\x00IEND\xaeB`\x82'  # IEND chunk
        )
        
        with open(screenshot_path, 'wb') as f:
            f.write(png_data)
        
        # Set timestamp based on freshness
        if fresh:
            # 1 hour ago (fresh)
            timestamp = datetime.now().timestamp() - 3600
        else:
            # 8 hours ago (stale)
            timestamp = datetime.now().timestamp() - (8 * 3600)
        
        os.utime(screenshot_path, (timestamp, timestamp))
        
        return screenshot_path
    
    @pytest.mark.asyncio
    async def test_analyze_command_complete_workflow_today(self):
        """Test complete analyze command workflow for today's messages."""
        # Prepare test data
        sample_messages = self.create_sample_messages(15)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock all dependencies for successful execution
        with patch('modules.database.get_messages_for_chat_today', 
                  new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(return_value="Comprehensive analysis of today's messages showing active discussion patterns.")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                  return_value={"enabled": False}):
                            
                            # Execute complete workflow
                            await enhanced_analyze_command(mock_update, mock_context)
                            
                            # Verify complete workflow execution
                            mock_update.message.reply_text.assert_called_once()
                            response_text = mock_update.message.reply_text.call_args[0][0]
                            
                            # Verify response content
                            assert "📊 Аналіз повідомлень за сьогодні:" in response_text
                            assert "Comprehensive analysis" in response_text
                            assert len(response_text) > 100  # Substantial response
    
    @pytest.mark.asyncio
    async def test_analyze_command_complete_workflow_date_range(self):
        """Test complete analyze command workflow for date range."""
        # Prepare test data
        sample_messages = self.create_sample_messages(25)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects(
            ['period', '01-01-2024', '31-01-2024']
        )
        
        # Mock all dependencies for successful execution
        with patch('modules.database.get_messages_for_chat_date_range', 
                  new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(return_value="Detailed analysis of January 2024 messages showing monthly trends and patterns.")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                  return_value={"enabled": False}):
                            
                            # Execute complete workflow
                            await enhanced_analyze_command(mock_update, mock_context)
                            
                            # Verify complete workflow execution
                            mock_update.message.reply_text.assert_called_once()
                            response_text = mock_update.message.reply_text.call_args[0][0]
                            
                            # Verify response content
                            assert "📊 Аналіз повідомлень за 01.01.2024 - 31.01.2024:" in response_text
                            assert "Detailed analysis" in response_text
    
    @pytest.mark.asyncio
    async def test_analyze_command_complete_workflow_with_caching(self):
        """Test complete analyze command workflow with caching enabled."""
        # Prepare test data
        sample_messages = self.create_sample_messages(10)
        cached_result = "Cached analysis result from previous execution"
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock cache hit scenario
        with patch('modules.database.get_messages_for_chat_today', 
                  new=AsyncMock(return_value=sample_messages)):
            with patch('modules.database.Database.get_cached_analysis', 
                      new=AsyncMock(return_value=cached_result)):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                  return_value={"enabled": True, "ttl": 3600}):
                            
                            # Execute complete workflow
                            await enhanced_analyze_command(mock_update, mock_context)
                            
                            # Verify cached result was used
                            mock_update.message.reply_text.assert_called_once()
                            response_text = mock_update.message.reply_text.call_args[0][0]
                            
                            assert "📊 Аналіз повідомлень за сьогодні (з кешу):" in response_text
                            assert cached_result in response_text
    
    @pytest.mark.asyncio
    async def test_flares_command_complete_workflow_fresh_screenshot(self):
        """Test complete flares command workflow with fresh screenshot."""
        # Prepare test data
        fresh_screenshot = self.create_screenshot_file('fresh_flares.png', fresh=True)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock all dependencies for successful execution
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
                    with patch.object(ScreenshotManager, 'get_current_screenshot',
                                    return_value=fresh_screenshot):
                        
                        # Execute complete workflow
                        await enhanced_flares_command(mock_update, mock_context)
                        
                        # Verify complete workflow execution
                        mock_context.bot.send_photo.assert_called_once()
                        call_args = mock_context.bot.send_photo.call_args
                        
                        # Verify photo sending parameters
                        assert call_args[1]['chat_id'] == self.chat_id
                        assert 'photo' in call_args[1]
                        assert 'caption' in call_args[1]
                        
                        # Verify caption content
                        caption = call_args[1]['caption']
                        assert "🌞 Прогноз сонячних спалахів і магнітних бурь" in caption
                        assert "📅 Час знімку:" in caption
                        assert "📊 Статус: актуальний" in caption
                        assert "🔗 Джерело: api.meteoagent.com" in caption
    
    @pytest.mark.asyncio
    async def test_flares_command_complete_workflow_stale_regeneration(self):
        """Test complete flares command workflow with stale screenshot regeneration."""
        # Prepare test data
        stale_screenshot = self.create_screenshot_file('stale_flares.png', fresh=False)
        new_screenshot = self.create_screenshot_file('new_flares.png', fresh=True)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock status message
        mock_status_msg = AsyncMock()
        mock_status_msg.edit_text = AsyncMock()
        mock_status_msg.delete = AsyncMock()
        mock_update.message.reply_text.return_value = mock_status_msg
        
        # Mock all dependencies for successful execution
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, 'get_screenshot_status_info',
                                return_value={
                                    'tool_available': True,
                                    'directory_exists': True,
                                    'has_screenshot': True,
                                    'is_fresh': False,
                                    'age_hours': 8.0
                                }):
                    with patch.object(ScreenshotManager, 'get_current_screenshot',
                                    return_value=new_screenshot):
                        
                        # Execute complete workflow
                        await enhanced_flares_command(mock_update, mock_context)
                        
                        # Verify status message handling
                        mock_update.message.reply_text.assert_called()
                        mock_status_msg.edit_text.assert_called()
                        mock_status_msg.delete.assert_called_once()
                        
                        # Verify photo was sent
                        mock_context.bot.send_photo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_command_error_recovery_workflow(self):
        """Test analyze command error recovery workflow."""
        # Prepare test data
        sample_messages = self.create_sample_messages(5)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock database failure followed by recovery
        call_count = 0
        
        async def mock_db_with_recovery(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 times
                raise Exception("Database connection timeout")
            return sample_messages  # Succeed on 3rd try
        
        with patch('modules.database.get_messages_for_chat_today', 
                  new=AsyncMock(side_effect=mock_db_with_recovery)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(return_value="Analysis after recovery")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                  return_value={"enabled": False}):
                            
                            # Execute workflow with error recovery
                            await enhanced_analyze_command(mock_update, mock_context)
                            
                            # Verify error was handled gracefully
                            mock_update.message.reply_text.assert_called_once()
                            response_text = mock_update.message.reply_text.call_args[0][0]
                            
                            # Should show error message, not success
                            assert "❌" in response_text
                            assert "проблема з підключенням до бази даних" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_flares_command_error_recovery_workflow(self):
        """Test flares command error recovery workflow."""
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
        
        # Mock tool unavailability
        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_flares_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                with patch.object(ScreenshotManager, '_check_wkhtmltoimage_availability',
                                return_value=False):
                    
                    # Execute workflow with error
                    await enhanced_flares_command(mock_update, mock_context)
                    
                    # Verify error was handled gracefully
                    mock_update.message.reply_text.assert_called_once()
                    response_text = mock_update.message.reply_text.call_args[0][0]
                    
                    assert "❌" in response_text
                    assert "Інструмент для створення знімків недоступний" in response_text
    
    @pytest.mark.asyncio
    async def test_date_parser_integration_with_analyze_command(self):
        """Test DateParser integration with analyze command for various date formats."""
        sample_messages = self.create_sample_messages(5)
        
        # Test different date formats
        date_format_tests = [
            (['date', '15-01-2024'], 'get_messages_for_chat_date'),
            (['date', '2024-01-15'], 'get_messages_for_chat_date'),
            (['date', '15/01/2024'], 'get_messages_for_chat_date'),
            (['period', '01-01-2024', '31-01-2024'], 'get_messages_for_chat_date_range'),
            (['period', '2024-01-01', '2024-01-31'], 'get_messages_for_chat_date_range'),
        ]
        
        for args, db_function in date_format_tests:
            mock_update, mock_context, mock_bot = self.create_mock_telegram_objects(args)
            
            with patch(f'modules.database.{db_function}', 
                      new=AsyncMock(return_value=sample_messages)):
                with patch('modules.gpt.generate_response', 
                          new=AsyncMock(return_value=f"Analysis for {args}")):
                    with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                              new=AsyncMock(return_value={"valid": True})):
                        with patch('modules.enhanced_analyze_command.check_command_dependencies',
                                  new=AsyncMock(return_value={"healthy": True})):
                            with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                      return_value={"enabled": False}):
                                
                                # Execute workflow
                                await enhanced_analyze_command(mock_update, mock_context)
                                
                                # Verify successful execution
                                mock_update.message.reply_text.assert_called_once()
                                response_text = mock_update.message.reply_text.call_args[0][0]
                                assert "📊 Аналіз повідомлень за" in response_text
                                assert f"Analysis for {args}" in response_text
                                
                                # Reset mock for next iteration
                                mock_update.message.reply_text.reset_mock()
    
    @pytest.mark.asyncio
    async def test_concurrent_command_execution(self):
        """Test concurrent execution of both commands."""
        # Prepare test data
        sample_messages = self.create_sample_messages(10)
        screenshot_path = self.create_screenshot_file('concurrent_test.png', fresh=True)
        
        # Create multiple command executions
        analyze_tasks = []
        flares_tasks = []
        
        for i in range(3):
            # Analyze command tasks
            mock_update_analyze, mock_context_analyze, _ = self.create_mock_telegram_objects()
            mock_update_analyze.effective_user.id = self.user_id + i
            analyze_tasks.append((
                enhanced_analyze_command(mock_update_analyze, mock_context_analyze),
                mock_update_analyze
            ))
            
            # Flares command tasks
            mock_update_flares, mock_context_flares, _ = self.create_mock_telegram_objects()
            mock_update_flares.effective_user.id = self.user_id + i + 10
            flares_tasks.append((
                enhanced_flares_command(mock_update_flares, mock_context_flares),
                mock_update_flares,
                mock_context_flares
            ))
        
        # Mock all dependencies
        with patch('modules.database.get_messages_for_chat_today', 
                  new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(return_value="Concurrent analysis")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.enhanced_flares_command.validate_command_configuration', 
                                  new=AsyncMock(return_value={"valid": True})):
                            with patch('modules.enhanced_flares_command.check_command_dependencies',
                                      new=AsyncMock(return_value={"healthy": True})):
                                with patch.object(ScreenshotManager, 'get_current_screenshot',
                                                return_value=screenshot_path):
                                    with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                              return_value={"enabled": False}):
                                        
                                        # Execute all tasks concurrently
                                        all_tasks = [task for task, _ in analyze_tasks] + [task for task, _, _ in flares_tasks]
                                        results = await asyncio.gather(*all_tasks, return_exceptions=True)
                                        
                                        # Verify all completed successfully
                                        for i, result in enumerate(results):
                                            assert not isinstance(result, Exception), f"Task {i} failed: {result}"
                                        
                                        # Verify analyze commands sent responses
                                        for _, mock_update in analyze_tasks:
                                            mock_update.message.reply_text.assert_called_once()
                                        
                                        # Verify flares commands sent photos
                                        for _, _, mock_context in flares_tasks:
                                            mock_context.bot.send_photo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_performance_validation_large_dataset(self):
        """Test performance validation with large datasets."""
        import time
        
        # Create large dataset
        large_message_set = self.create_sample_messages(1000)
        mock_update, mock_context, mock_bot = self.create_mock_telegram_objects(
            ['last', '1000', 'messages']
        )
        
        # Mock all dependencies
        with patch('modules.database.get_last_n_messages_in_chat', 
                  new=AsyncMock(return_value=large_message_set)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(return_value="Analysis of large dataset")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                  return_value={"enabled": False}):
                            
                            # Measure execution time
                            start_time = time.time()
                            await enhanced_analyze_command(mock_update, mock_context)
                            execution_time = time.time() - start_time
                            
                            # Verify performance (should complete within reasonable time)
                            assert execution_time < 30.0, f"Command took too long: {execution_time:.2f} seconds"
                            
                            # Verify successful execution
                            mock_update.message.reply_text.assert_called_once()
                            response_text = mock_update.message.reply_text.call_args[0][0]
                            assert "📊 Аналіз повідомлень за останні 1000 повідомлень:" in response_text
    
    @pytest.mark.asyncio
    async def test_memory_usage_validation(self):
        """Test memory usage doesn't grow excessively during command execution."""
        import gc
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Execute multiple commands
        for i in range(10):
            sample_messages = self.create_sample_messages(50)
            mock_update, mock_context, mock_bot = self.create_mock_telegram_objects()
            mock_update.effective_user.id = self.user_id + i
            
            with patch('modules.database.get_messages_for_chat_today', 
                      new=AsyncMock(return_value=sample_messages)):
                with patch('modules.gpt.generate_response', 
                          new=AsyncMock(return_value=f"Analysis {i}")):
                    with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                              new=AsyncMock(return_value={"valid": True})):
                        with patch('modules.enhanced_analyze_command.check_command_dependencies',
                                  new=AsyncMock(return_value={"healthy": True})):
                            with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                      return_value={"enabled": False}):
                                
                                await enhanced_analyze_command(mock_update, mock_context)
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage shouldn't grow significantly
        object_growth = final_objects - initial_objects
        assert object_growth < 200, f"Memory usage grew by {object_growth} objects"
    
    @pytest.mark.asyncio
    async def test_integration_with_real_date_parsing_edge_cases(self):
        """Test integration with real date parsing edge cases."""
        sample_messages = self.create_sample_messages(5)
        
        # Test edge case dates
        edge_case_dates = [
            (['date', '29-02-2024'], True),   # Leap year
            (['date', '29-02-2023'], False),  # Non-leap year
            (['date', '31-04-2024'], False),  # Invalid day for April
            (['period', '31-01-2024', '01-02-2024'], True),  # Cross-month period
            (['period', '2024-01-31', '01-02-2024'], True),  # Mixed formats
        ]
        
        for args, should_succeed in edge_case_dates:
            mock_update, mock_context, mock_bot = self.create_mock_telegram_objects(args)
            
            # Determine which database function to mock
            if args[0] == 'date':
                db_patch = patch('modules.database.get_messages_for_chat_date', 
                               new=AsyncMock(return_value=sample_messages))
            else:  # period
                db_patch = patch('modules.database.get_messages_for_chat_date_range', 
                               new=AsyncMock(return_value=sample_messages))
            
            with db_patch:
                with patch('modules.gpt.generate_response', 
                          new=AsyncMock(return_value="Edge case analysis")):
                    with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                              new=AsyncMock(return_value={"valid": True})):
                        with patch('modules.enhanced_analyze_command.check_command_dependencies',
                                  new=AsyncMock(return_value={"healthy": True})):
                            with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                                      return_value={"enabled": False}):
                                
                                # Execute command
                                await enhanced_analyze_command(mock_update, mock_context)
                                
                                # Verify response
                                mock_update.message.reply_text.assert_called_once()
                                response_text = mock_update.message.reply_text.call_args[0][0]
                                
                                if should_succeed:
                                    assert "📊 Аналіз повідомлень за" in response_text
                                    assert "Edge case analysis" in response_text
                                else:
                                    assert "❌" in response_text
                                    assert "Помилка в форматі дати" in response_text or "Помилка в датах" in response_text
                                
                                # Reset mock for next iteration
                                mock_update.message.reply_text.reset_mock()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])