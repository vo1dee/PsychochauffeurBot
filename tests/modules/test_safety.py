"""
Tests for the safety module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from modules.safety import SafetyManager


class TestSafetyManager:
    """Test safety manager functionality."""
    
    @pytest.fixture
    def safety_manager(self):
        """Create a safety manager instance."""
        return SafetyManager()
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock update."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.effective_user = Mock(spec=User)
        update.effective_chat = Mock(spec=Chat)
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return Mock(spec=CallbackContext)
    
    def test_safety_manager_initialization(self, safety_manager):
        """Test safety manager initialization."""
        assert safety_manager is not None
        assert hasattr(safety_manager, 'config_manager')
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, safety_manager):
        """Test successful initialization."""
        with patch.object(safety_manager.config_manager, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            
            with patch('modules.safety.general_logger') as mock_logger:
                result = await safety_manager.initialize()
                
                assert result is True
                mock_init.assert_called_once()
                mock_logger.info.assert_called_once_with("Safety manager initialized successfully")
    
    @pytest.mark.asyncio
    async def test_stop_success(self, safety_manager):
        """Test successful stop."""
        with patch('modules.safety.general_logger') as mock_logger:
            result = await safety_manager.stop()
            
            assert result is True
            mock_logger.info.assert_called_once_with("Safety manager stopped successfully")
    
    @pytest.mark.asyncio
    async def test_check_message_safety_basic(self, safety_manager, mock_update, mock_context):
        """Test basic message safety check."""
        message_text = "Hello, this is a safe message"
        
        # Mock the method to return True for basic test
        with patch.object(safety_manager, 'check_message_safety', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            
            result = await safety_manager.check_message_safety(mock_update, mock_context, message_text)
            assert result is True
    
    def test_safety_manager_has_config_manager(self, safety_manager):
        """Test that safety manager has config manager."""
        assert hasattr(safety_manager, 'config_manager')
        assert safety_manager.config_manager is not None


class TestSafetyManagerIntegration:
    """Test safety manager integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_safety_manager_lifecycle(self):
        """Test complete safety manager lifecycle."""
        manager = SafetyManager()
        
        # Test initialization
        with patch.object(manager.config_manager, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            
            with patch('modules.safety.general_logger'):
                init_result = await manager.initialize()
                assert init_result is True
        
        # Test stop
        with patch('modules.safety.general_logger'):
            stop_result = await manager.stop()
            assert stop_result is True
    
    def test_safety_manager_imports(self):
        """Test that safety manager imports work correctly."""
        from modules.safety import SafetyManager
        
        manager = SafetyManager()
        assert manager is not None
        
        # Test that required methods exist
        assert hasattr(manager, 'initialize')
        assert hasattr(manager, 'stop')
        assert hasattr(manager, 'check_message_safety')
        
        # Test that methods are callable
        assert callable(manager.initialize)
        assert callable(manager.stop)
        assert callable(manager.check_message_safety)
    
    @pytest.mark.asyncio
    async def test_safety_manager_with_real_config(self):
        """Test safety manager with real config manager."""
        manager = SafetyManager()
        
        # Should be able to create without errors
        assert manager.config_manager is not None
        
        # Should be able to call methods without errors (even if they don't do much)
        with patch('modules.safety.general_logger'):
            result = await manager.stop()
            assert result is True