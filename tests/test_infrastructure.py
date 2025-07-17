"""
Test the test infrastructure setup.
"""

import pytest
import asyncio
from tests.base_test_classes import (
    BaseTestCase, AsyncBaseTestCase, ComprehensiveTestCase,
    TelegramTestMixin, ConfigTestMixin
)


class TestBaseInfrastructure(BaseTestCase):
    """Test the base test infrastructure."""
    
    def test_base_test_case_setup(self):
        """Test that base test case sets up correctly."""
        self.assertIsNotNone(self.mock_bot)
        self.assertEqual(self.test_user_id, 12345)
        self.assertEqual(self.test_username, "testuser")
    
    def test_mock_user_creation(self):
        """Test mock user creation."""
        user = self.create_mock_user()
        self.assertEqual(user.id, self.test_user_id)
        self.assertEqual(user.username, self.test_username)
        self.assertFalse(user.is_bot)
    
    def test_mock_message_creation(self):
        """Test mock message creation."""
        message = self.create_mock_message()
        self.assertEqual(message.text, self.test_message_text)
        self.assertIsNotNone(message.reply_text)
    
    def test_mock_update_creation(self):
        """Test mock update creation."""
        update = self.create_mock_update()
        self.assertEqual(update.update_id, 1)
        self.assertIsNotNone(update.message)


class TestAsyncInfrastructure(AsyncBaseTestCase):
    """Test the async test infrastructure."""
    
    @pytest.mark.asyncio
    async def test_async_test_case_setup(self):
        """Test that async test case sets up correctly."""
        self.assertIsNotNone(self.loop)
        
        # Test async functionality
        async def sample_async_function():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await sample_async_function()
        self.assertEqual(result, "async_result")
    
    @pytest.mark.asyncio
    async def test_run_async_test_helper(self):
        """Test the run_async_test helper."""
        async def test_coro():
            return "test_result"
        
        result = await self.run_async_test(test_coro())
        self.assertEqual(result, "test_result")


class TestTelegramMixin(BaseTestCase, TelegramTestMixin):
    """Test the Telegram test mixin."""
    
    def test_assert_message_sent(self):
        """Test the assert_message_sent utility."""
        # Mock a bot call
        self.mock_bot.send_message(chat_id=12345, text="Test message")
        
        # Test the assertion
        self.assert_message_sent(self.mock_bot, chat_id=12345, text="Test message")
    
    def test_assert_callback_answered(self):
        """Test the assert_callback_answered utility."""
        callback_query = self.create_mock_callback_query()
        callback_query.answer()
        
        self.assert_callback_answered(callback_query)


class TestConfigMixin(BaseTestCase, ConfigTestMixin):
    """Test the configuration test mixin."""
    
    def test_create_test_config(self):
        """Test test configuration creation."""
        config = self.create_test_config()
        
        self.assertIn("chat_metadata", config)
        self.assertIn("config_modules", config)
        self.assertEqual(config["chat_metadata"]["chat_id"], "test_chat")
    
    def test_create_test_config_with_overrides(self):
        """Test test configuration creation with overrides."""
        config = self.create_test_config(**{
            "chat_metadata.chat_id": "custom_chat",
            "config_modules.gpt.enabled": False
        })
        
        self.assertEqual(config["chat_metadata"]["chat_id"], "custom_chat")
        self.assertFalse(config["config_modules"]["gpt"]["enabled"])


class TestComprehensiveInfrastructure(ComprehensiveTestCase):
    """Test the comprehensive test case that combines all mixins."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_functionality(self):
        """Test that all functionality works together."""
        # Test base functionality
        self.assertIsNotNone(self.mock_bot)
        
        # Test async functionality
        async def async_operation():
            await asyncio.sleep(0.01)
            return "success"
        
        result = await async_operation()
        self.assertEqual(result, "success")
        
        # Test Telegram functionality
        message = self.create_mock_message("Hello world")
        self.assertEqual(message.text, "Hello world")
        
        # Test config functionality
        config = self.create_test_config()
        self.assertIn("chat_metadata", config)
        
        # Test mock functionality
        mock_service = self.patch_module('os.path.exists', return_value=True)
        import os
        self.assertTrue(os.path.exists("any_path"))
        mock_service.assert_called_with("any_path")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])