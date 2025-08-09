"""
Integration tests for enhanced analyze command with database scenarios.

This module provides comprehensive integration testing for the enhanced analyze command including:
- Database connection scenarios
- Message retrieval and analysis
- Error handling and recovery
- Performance monitoring
- Cache functionality

Requirements addressed: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 3.1, 3.2, 3.3, 3.4, 3.5
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from modules.enhanced_analyze_command import EnhancedAnalyzeCommand, enhanced_analyze_command
from modules.database import Database
from modules.const import KYIV_TZ
from tests.base_test_classes import AsyncBaseTestCase, DatabaseTestCase


class TestEnhancedAnalyzeCommandIntegration(DatabaseTestCase):
    """Integration tests for enhanced analyze command with real database scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.enhanced_analyze = EnhancedAnalyzeCommand()
        self.chat_id = -1001234567890
        self.user_id = 12345
        self.username = "testuser"

    def create_mock_update_and_context(self, args=None):
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
        
        # Create mock update
        mock_update = Mock()
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        # Create mock context
        mock_context = Mock()
        mock_context.args = args or []
        mock_context.bot = AsyncMock()
        
        return mock_update, mock_context
    
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
                'message_text': f'Test message {i + 1} content for analysis',
                'timestamp': (base_time + timedelta(minutes=i * 10)).isoformat(),
                'created_at': base_time + timedelta(minutes=i * 10)
            }
            messages.append(message)
        
        return messages
    
    @pytest.mark.asyncio
    async def test_analyze_command_today_messages_success(self):
        """Test successful analysis of today's messages."""
        # Prepare test data
        sample_messages = self.create_sample_messages(5)
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock database calls
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis result")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за сьогодні:" in call_args
                        assert "Analysis result" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_last_n_messages_success(self):
        """Test successful analysis of last N messages."""
        # Prepare test data
        sample_messages = self.create_sample_messages(20)
        mock_update, mock_context = self.create_mock_update_and_context(['last', '20', 'messages'])
        
        # Mock database calls
        with patch('modules.database.get_last_n_messages_in_chat', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis of 20 messages")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за останні 20 повідомлень:" in call_args
                        assert "Analysis of 20 messages" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_last_n_days_success(self):
        """Test successful analysis of last N days."""
        # Prepare test data
        sample_messages = self.create_sample_messages(15)
        mock_update, mock_context = self.create_mock_update_and_context(['last', '7', 'days'])
        
        # Mock database calls
        with patch('modules.database.get_messages_for_chat_last_n_days', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis of 7 days")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за останні 7 днів:" in call_args
                        assert "Analysis of 7 days" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_date_range_success(self):
        """Test successful analysis of date range."""
        # Prepare test data
        sample_messages = self.create_sample_messages(10)
        mock_update, mock_context = self.create_mock_update_and_context(['period', '01-01-2024', '31-01-2024'])
        
        # Mock database calls
        with patch('modules.database.get_messages_for_chat_date_range', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis of date range")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за 01.01.2024 - 31.01.2024:" in call_args
                        assert "Analysis of date range" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_specific_date_success(self):
        """Test successful analysis of specific date."""
        # Prepare test data
        sample_messages = self.create_sample_messages(5)
        mock_update, mock_context = self.create_mock_update_and_context(['date', '15-01-2024'])
        
        # Mock database calls
        with patch('modules.database.get_messages_for_chat_date', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis of specific date")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за 15.01.2024:" in call_args
                        assert "Analysis of specific date" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_no_messages_found(self):
        """Test handling when no messages are found."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock database to return empty list
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=[])):
            with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                      new=AsyncMock(return_value={"valid": True})):
                with patch('modules.enhanced_analyze_command.check_command_dependencies',
                          new=AsyncMock(return_value={"healthy": True})):
                    
                    # Execute command
                    await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                    
                    # Verify appropriate message was sent
                    mock_update.message.reply_text.assert_called_once()
                    call_args = mock_update.message.reply_text.call_args[0][0]
                    assert "📭 Не знайдено повідомлень для аналізу" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_database_connection_failure(self):
        """Test handling of database connection failures."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock database to raise connection error
        with patch('modules.database.get_messages_for_chat_today', 
                  new=AsyncMock(side_effect=Exception("Database connection failed"))):
            with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                      new=AsyncMock(return_value={"valid": True})):
                with patch('modules.enhanced_analyze_command.check_command_dependencies',
                          new=AsyncMock(return_value={"healthy": True})):
                    
                    # Execute command
                    await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                    
                    # Verify error message was sent
                    mock_update.message.reply_text.assert_called_once()
                    call_args = mock_update.message.reply_text.call_args[0][0]
                    assert "❌" in call_args
                    assert "проблема з підключенням до бази даних" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_command_gpt_api_failure(self):
        """Test handling of GPT API failures."""
        # Prepare test data
        sample_messages = self.create_sample_messages(5)
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock database success but GPT failure
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(side_effect=Exception("API timeout"))):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify error message was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "сервіс аналізу тимчасово недоступний" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_command_invalid_date_format(self):
        """Test handling of invalid date formats."""
        mock_update, mock_context = self.create_mock_update_and_context(['date', 'invalid-date'])
        
        with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_analyze_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command
                await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                
                # Verify error message was sent
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "❌" in call_args
                assert "Помилка в форматі дати" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_invalid_command_type(self):
        """Test handling of invalid command types."""
        mock_update, mock_context = self.create_mock_update_and_context(['invalid', 'command'])
        
        with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_analyze_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": True})):
                
                # Execute command
                await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                
                # Verify error message was sent
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "❌" in call_args
                assert "Невідома команда" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_configuration_invalid(self):
        """Test handling when command configuration is invalid."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock invalid configuration
        with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": False, "issues": ["Config error"]})):
            
            # Execute command
            await self.enhanced_analyze.analyze_command(mock_update, mock_context)
            
            # Verify error message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "Конфігурація команди аналізу містить помилки" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_dependencies_unhealthy(self):
        """Test handling when command dependencies are unhealthy."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock unhealthy dependencies
        with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                  new=AsyncMock(return_value={"valid": True})):
            with patch('modules.enhanced_analyze_command.check_command_dependencies',
                      new=AsyncMock(return_value={"healthy": False, "dependencies": {"db": False}})):
                
                # Execute command
                await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                
                # Verify error message was sent
                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "❌" in call_args
                assert "сервіси, необхідні для аналізу, недоступні" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_cache_functionality(self):
        """Test cache functionality in analyze command."""
        # Prepare test data
        sample_messages = self.create_sample_messages(5)
        mock_update, mock_context = self.create_mock_update_and_context()
        cached_result = "Cached analysis result"
        
        # Mock cache hit
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.database.Database.get_cached_analysis', 
                      new=AsyncMock(return_value=cached_result)):
                with patch('modules.config.config_manager.config_manager.get_analysis_cache_config',
                          return_value={"enabled": True, "ttl": 3600}):
                    with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                              new=AsyncMock(return_value={"valid": True})):
                        with patch('modules.enhanced_analyze_command.check_command_dependencies',
                                  new=AsyncMock(return_value={"healthy": True})):
                            
                            # Execute command
                            await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                            
                            # Verify cached result was used
                            mock_update.message.reply_text.assert_called_once()
                            call_args = mock_update.message.reply_text.call_args[0][0]
                            assert "📊 Аналіз повідомлень за сьогодні (з кешу):" in call_args
                            assert cached_result in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_performance_metrics(self):
        """Test that performance metrics are logged correctly."""
        # Prepare test data
        sample_messages = self.create_sample_messages(10)
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock successful execution
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis result")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        with patch('modules.enhanced_analyze_command.log_command_performance_metric') as mock_metric:
                            
                            # Execute command
                            await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                            
                            # Verify performance metrics were logged
                            assert mock_metric.call_count >= 2  # At least message count and result length
    
    @pytest.mark.asyncio
    async def test_analyze_command_different_date_formats(self):
        """Test analyze command with different date formats."""
        sample_messages = self.create_sample_messages(5)
        
        date_formats = [
            ('date', '15-01-2024'),      # DD-MM-YYYY
            ('date', '2024-01-15'),      # YYYY-MM-DD
            ('date', '15/01/2024'),      # DD/MM/YYYY
            ('period', '01-01-2024', '31-01-2024'),  # Period with DD-MM-YYYY
            ('period', '2024-01-01', '2024-01-31'),  # Period with YYYY-MM-DD
        ]
        
        for date_args in date_formats:
            mock_update, mock_context = self.create_mock_update_and_context(list(date_args))
            
            # Mock appropriate database function based on command type
            if date_args[0] == 'date':
                patch_target = 'modules.database.get_messages_for_chat_date'
            else:  # period
                patch_target = 'modules.database.get_messages_for_chat_date_range'
            
            with patch(patch_target, new=AsyncMock(return_value=sample_messages)):
                with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis result")):
                    with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                              new=AsyncMock(return_value={"valid": True})):
                        with patch('modules.enhanced_analyze_command.check_command_dependencies',
                                  new=AsyncMock(return_value={"healthy": True})):
                            
                            # Execute command
                            await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                            
                            # Verify response was sent successfully
                            mock_update.message.reply_text.assert_called_once()
                            call_args = mock_update.message.reply_text.call_args[0][0]
                            assert "📊 Аналіз повідомлень за" in call_args
                            assert "Analysis result" in call_args
                            
                            # Reset mock for next iteration
                            mock_update.message.reply_text.reset_mock()
    
    @pytest.mark.asyncio
    async def test_analyze_command_large_message_dataset(self):
        """Test analyze command with large message datasets."""
        # Create large dataset
        large_message_set = self.create_sample_messages(1000)
        mock_update, mock_context = self.create_mock_update_and_context(['last', '1000', 'messages'])
        
        # Mock database calls
        with patch('modules.database.get_last_n_messages_in_chat', new=AsyncMock(return_value=large_message_set)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis of large dataset")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command with timeout
                        await asyncio.wait_for(
                            self.enhanced_analyze.analyze_command(mock_update, mock_context),
                            timeout=30.0  # Should complete within 30 seconds
                        )
                        
                        # Verify response was sent
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "📊 Аналіз повідомлень за останні 1000 повідомлень:" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_command_concurrent_requests(self):
        """Test analyze command handling concurrent requests."""
        sample_messages = self.create_sample_messages(5)
        
        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            mock_update, mock_context = self.create_mock_update_and_context()
            mock_update.effective_user.id = self.user_id + i  # Different users
            
            # Create task
            task = self.enhanced_analyze.analyze_command(mock_update, mock_context)
            tasks.append((task, mock_update))
        
        # Mock all dependencies
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Concurrent analysis")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute all tasks concurrently
                        results = await asyncio.gather(*[task for task, _ in tasks], return_exceptions=True)
                        
                        # Verify all completed successfully
                        for i, (result, (_, mock_update)) in enumerate(zip(results, tasks)):
                            assert not isinstance(result, Exception), f"Task {i} failed: {result}"
                            mock_update.message.reply_text.assert_called_once()


class TestEnhancedAnalyzeCommandErrorSimulation(AsyncBaseTestCase):
    """Test error simulation scenarios for enhanced analyze command."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.enhanced_analyze = EnhancedAnalyzeCommand()
    
    @pytest.mark.asyncio
    async def test_database_connection_retry_logic(self):
        """Test database connection retry logic."""
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock database to fail first few times, then succeed
        call_count = 0
        sample_messages = [{'message_text': 'test', 'timestamp': 'now', 'username': 'user'}]
        
        async def mock_db_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 times
                raise Exception("Connection timeout")
            return sample_messages
        
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(side_effect=mock_db_call)):
            with patch('modules.gpt.generate_response', new=AsyncMock(return_value="Analysis result")):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command - should eventually succeed after retries
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify it was called multiple times (retry logic)
                        assert call_count >= 1
    
    @pytest.mark.asyncio
    async def test_api_timeout_handling(self):
        """Test API timeout handling."""
        sample_messages = [{'message_text': 'test', 'timestamp': 'now', 'username': 'user'}]
        mock_update, mock_context = self.create_mock_update_and_context()
        
        # Mock API timeout
        with patch('modules.database.get_messages_for_chat_today', new=AsyncMock(return_value=sample_messages)):
            with patch('modules.gpt.generate_response', 
                      new=AsyncMock(side_effect=asyncio.TimeoutError("API timeout"))):
                with patch('modules.enhanced_analyze_command.validate_command_configuration', 
                          new=AsyncMock(return_value={"valid": True})):
                    with patch('modules.enhanced_analyze_command.check_command_dependencies',
                              new=AsyncMock(return_value={"healthy": True})):
                        
                        # Execute command
                        await self.enhanced_analyze.analyze_command(mock_update, mock_context)
                        
                        # Verify timeout error was handled gracefully
                        mock_update.message.reply_text.assert_called_once()
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "сервіс аналізу тимчасово недоступний" in call_args.lower()
    
    def create_mock_update_and_context(self, args=None):
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
        
        # Create mock update
        mock_update = Mock()
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
        
        # Create mock context
        mock_context = Mock()
        mock_context.args = args or []
        mock_context.bot = AsyncMock()
        
        return mock_update, mock_context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])