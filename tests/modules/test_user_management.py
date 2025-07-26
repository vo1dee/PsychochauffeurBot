"""
Tests for the user management module.
"""

import pytest
import pytz
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, Chat, Message, User, ChatPermissions
from telegram.ext import CallbackContext
from telegram.error import TelegramError

from modules.user_management import restrict_user, LOCAL_TZ, RESTRICT_DURATION_RANGE


class TestUserManagement:
    """Test user management functionality."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock update."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 12345
        update.effective_chat.type = "group"
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return Mock(spec=CallbackContext)
    
    def test_local_timezone_constant(self):
        """Test that LOCAL_TZ is properly configured."""
        assert LOCAL_TZ.zone == 'Europe/Kyiv'
        assert isinstance(LOCAL_TZ, pytz.BaseTzInfo)
    
    def test_restrict_duration_range_constant(self):
        """Test that RESTRICT_DURATION_RANGE is properly configured."""
        assert RESTRICT_DURATION_RANGE == (1, 15)
        assert len(RESTRICT_DURATION_RANGE) == 2
        assert RESTRICT_DURATION_RANGE[0] < RESTRICT_DURATION_RANGE[1]
    
    @pytest.mark.asyncio
    async def test_restrict_user_no_message(self, mock_context):
        """Test restrict_user with no message in update."""
        update = Mock(spec=Update)
        update.message = None
        
        with patch('modules.user_management.error_logger') as mock_logger:
            await restrict_user(update, mock_context)
            mock_logger.error.assert_called_once_with("No message found in update")
    
    @pytest.mark.asyncio
    async def test_restrict_user_with_valid_update(self, mock_update, mock_context):
        """Test restrict_user with valid update."""
        with patch('modules.user_management.general_logger') as mock_logger:
            await restrict_user(mock_update, mock_context)
            assert mock_logger.info.call_count >= 1
            # Check that the function was called and logged appropriately
            call_args_list = [call[0][0] for call in mock_logger.info.call_args_list]
            log_messages = ' '.join(call_args_list)
            assert "[restrict_user]" in log_messages
            assert "chat_id=12345" in log_messages
            assert "chat_type=group" in log_messages
    
    @pytest.mark.asyncio
    async def test_restrict_user_with_no_chat(self, mock_context):
        """Test restrict_user with no effective chat."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.effective_chat = None
        
        with patch('modules.user_management.general_logger') as mock_logger:
            await restrict_user(update, mock_context)
            assert mock_logger.info.call_count >= 2
            # Check that the function was called and logged appropriately
            call_args_list = [call[0][0] for call in mock_logger.info.call_args_list]
            log_messages = ' '.join(call_args_list)
            assert "chat_id=None" in log_messages
            assert "chat_type=None" in log_messages


class TestUserManagementIntegration:
    """Test user management integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_restrict_user_with_config_manager(self):
        """Test restrict_user with config manager integration."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 12345
        update.effective_chat.type = "group"
        
        context = Mock(spec=CallbackContext)
        
        with patch('modules.user_management.config_manager') as mock_config:
            with patch('modules.user_management.general_logger'):
                await restrict_user(update, context)
                # Should not raise any errors
                assert True
    
    def test_module_imports(self):
        """Test that all required modules are imported correctly."""
        import modules.user_management as um
        
        # Test that constants are available
        assert hasattr(um, 'LOCAL_TZ')
        assert hasattr(um, 'RESTRICT_DURATION_RANGE')
        
        # Test that functions are available
        assert hasattr(um, 'restrict_user')
        assert callable(um.restrict_user)
    
    def test_timezone_functionality(self):
        """Test timezone functionality."""
        now = datetime.now()
        kyiv_time = LOCAL_TZ.localize(now)
        assert kyiv_time.tzinfo.zone == LOCAL_TZ.zone
        
        # Test that we can work with timedeltas
        future_time = kyiv_time + timedelta(minutes=5)
        assert future_time > kyiv_time
        
        # Test timezone zone property
        assert LOCAL_TZ.zone == 'Europe/Kyiv'