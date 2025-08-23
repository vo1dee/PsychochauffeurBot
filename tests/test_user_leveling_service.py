"""
Tests for UserLevelingService.

This module contains unit tests for the main UserLevelingService class,
testing initialization, message processing, and integration functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from modules.user_leveling_service import UserLevelingService
from modules.leveling_models import UserStats, UserProfile, LevelUpResult
from modules.types import UserId, ChatId


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    config_manager = Mock()
    config_manager.get.return_value = {
        'enabled': True,
        'level_base_xp': 50,
        'level_multiplier': 2.0,
        'notifications_enabled': True
    }
    return config_manager


@pytest.fixture
def leveling_service(mock_config_manager):
    """Create a UserLevelingService instance for testing."""
    return UserLevelingService(config_manager=mock_config_manager)


@pytest.fixture
def mock_message():
    """Create a mock Telegram message."""
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 12345
    message.from_user.is_bot = False
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    
    message.chat = Mock(spec=Chat)
    message.chat.id = 67890
    message.chat.type = 'group'
    
    message.text = "Hello world!"
    message.reply_to_message = None
    
    return message


@pytest.fixture
def mock_update(mock_message):
    """Create a mock Telegram update."""
    update = Mock(spec=Update)
    update.message = mock_message
    update.effective_chat = mock_message.chat
    return update


@pytest.fixture
def mock_context():
    """Create a mock bot context."""
    return Mock(spec=ContextTypes.DEFAULT_TYPE)


class TestUserLevelingService:
    """Test cases for UserLevelingService."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, leveling_service):
        """Test service initialization."""
        # Mock the dependencies
        with patch('modules.user_leveling_service.XPCalculator') as mock_xp_calc, \
             patch('modules.user_leveling_service.LevelManager') as mock_level_mgr, \
             patch('modules.user_leveling_service.UserStatsRepository') as mock_user_repo, \
             patch('modules.user_leveling_service.AchievementRepository') as mock_ach_repo, \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            # Mock the achievement engine initialization
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            # Initialize the service
            await leveling_service.initialize()
            
            # Verify initialization
            assert leveling_service._initialized is True
            assert leveling_service.xp_calculator is not None
            assert leveling_service.level_manager is not None
            assert leveling_service.user_stats_repo is not None
            assert leveling_service.achievement_repo is not None
            assert leveling_service.achievement_engine is not None
            
            # Verify achievement definitions were initialized
            mock_ach_engine_instance.initialize_achievement_definitions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, leveling_service):
        """Test service shutdown."""
        # Initialize first
        with patch('modules.user_leveling_service.XPCalculator'), \
             patch('modules.user_leveling_service.LevelManager'), \
             patch('modules.user_leveling_service.UserStatsRepository'), \
             patch('modules.user_leveling_service.AchievementRepository'), \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            await leveling_service.initialize()
            
            # Now test shutdown
            await leveling_service.shutdown()
            
            assert leveling_service._initialized is False
            assert leveling_service.xp_calculator is None
            assert leveling_service.level_manager is None
    
    @pytest.mark.asyncio
    async def test_process_message_not_initialized(self, leveling_service, mock_update, mock_context):
        """Test message processing when service is not initialized."""
        # Service should not process messages when not initialized
        await leveling_service.process_message(mock_update, mock_context)
        
        # No errors should occur, but no processing should happen
        assert leveling_service._stats['messages_processed'] == 0
    
    @pytest.mark.asyncio
    async def test_process_message_bot_message(self, leveling_service, mock_update, mock_context):
        """Test that bot messages are ignored."""
        # Initialize service
        with patch('modules.user_leveling_service.XPCalculator'), \
             patch('modules.user_leveling_service.LevelManager'), \
             patch('modules.user_leveling_service.UserStatsRepository'), \
             patch('modules.user_leveling_service.AchievementRepository'), \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            await leveling_service.initialize()
        
        # Set message as from bot
        mock_update.message.from_user.is_bot = True
        
        await leveling_service.process_message(mock_update, mock_context)
        
        # Should not process bot messages
        assert leveling_service._stats['messages_processed'] == 0
    
    @pytest.mark.asyncio
    async def test_process_message_private_chat(self, leveling_service, mock_update, mock_context):
        """Test that private chat messages are ignored."""
        # Initialize service
        with patch('modules.user_leveling_service.XPCalculator'), \
             patch('modules.user_leveling_service.LevelManager'), \
             patch('modules.user_leveling_service.UserStatsRepository'), \
             patch('modules.user_leveling_service.AchievementRepository'), \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            await leveling_service.initialize()
        
        # Set chat as private
        mock_update.effective_chat.type = 'private'
        
        await leveling_service.process_message(mock_update, mock_context)
        
        # Should not process private chat messages
        assert leveling_service._stats['messages_processed'] == 0
    
    @pytest.mark.asyncio
    async def test_process_valid_message(self, leveling_service, mock_update, mock_context):
        """Test processing a valid group message."""
        # Mock all dependencies
        with patch('modules.user_leveling_service.XPCalculator') as mock_xp_calc_class, \
             patch('modules.user_leveling_service.LevelManager') as mock_level_mgr_class, \
             patch('modules.user_leveling_service.UserStatsRepository') as mock_user_repo_class, \
             patch('modules.user_leveling_service.AchievementRepository') as mock_ach_repo_class, \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine_class:
            
            # Create mock instances
            mock_xp_calc = Mock()
            mock_xp_calc.calculate_total_message_xp.return_value = (1, {})  # 1 XP for sender, no thanks
            mock_xp_calc_class.return_value = mock_xp_calc
            
            mock_level_mgr = Mock()
            mock_level_mgr.calculate_level.return_value = 1
            mock_level_mgr_class.return_value = mock_level_mgr
            
            mock_user_repo = AsyncMock()
            mock_user_stats = UserStats(user_id=12345, chat_id=67890, xp=0, level=1)
            mock_user_repo.get_user_stats.return_value = mock_user_stats
            mock_user_repo_class.return_value = mock_user_repo
            
            mock_ach_repo = AsyncMock()
            mock_ach_repo_class.return_value = mock_ach_repo
            
            mock_ach_engine = AsyncMock()
            mock_ach_engine.check_achievements.return_value = []
            mock_ach_engine_class.return_value = mock_ach_engine
            
            # Initialize service
            await leveling_service.initialize()
            
            # Process message
            await leveling_service.process_message(mock_update, mock_context)
            
            # Verify processing occurred
            assert leveling_service._stats['messages_processed'] == 1
            mock_xp_calc.calculate_total_message_xp.assert_called_once()
            mock_user_repo.get_user_stats.assert_called_once_with(12345, 67890)
            mock_user_repo.update_user_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_profile_not_initialized(self, leveling_service):
        """Test getting user profile when service is not initialized."""
        profile = await leveling_service.get_user_profile(12345, 67890)
        assert profile is None
    
    @pytest.mark.asyncio
    async def test_get_user_profile_user_not_found(self, leveling_service):
        """Test getting profile for non-existent user."""
        with patch('modules.user_leveling_service.XPCalculator'), \
             patch('modules.user_leveling_service.LevelManager'), \
             patch('modules.user_leveling_service.UserStatsRepository') as mock_user_repo_class, \
             patch('modules.user_leveling_service.AchievementRepository'), \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            mock_user_repo = AsyncMock()
            mock_user_repo.get_user_stats.return_value = None
            mock_user_repo_class.return_value = mock_user_repo
            
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            await leveling_service.initialize()
            
            profile = await leveling_service.get_user_profile(12345, 67890)
            assert profile is None
    
    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, leveling_service):
        """Test successfully getting a user profile."""
        with patch('modules.user_leveling_service.XPCalculator'), \
             patch('modules.user_leveling_service.LevelManager') as mock_level_mgr_class, \
             patch('modules.user_leveling_service.UserStatsRepository') as mock_user_repo_class, \
             patch('modules.user_leveling_service.AchievementRepository') as mock_ach_repo_class, \
             patch('modules.user_leveling_service.AchievementEngine') as mock_ach_engine:
            
            # Mock user stats
            mock_user_stats = UserStats(
                user_id=12345, 
                chat_id=67890, 
                xp=75, 
                level=2,
                messages_count=50,
                links_shared=5,
                thanks_received=3
            )
            
            mock_user_repo = AsyncMock()
            mock_user_repo.get_user_stats.return_value = mock_user_stats
            mock_user_repo_class.return_value = mock_user_repo
            
            # Mock achievements
            mock_ach_repo = AsyncMock()
            mock_ach_repo.get_user_achievements.return_value = []
            mock_ach_repo_class.return_value = mock_ach_repo
            
            # Mock level manager
            mock_level_mgr = Mock()
            mock_level_mgr.get_level_threshold.side_effect = lambda level: level * 50
            mock_level_mgr.calculate_level.return_value = 2  # Return the same level to avoid changes
            mock_level_mgr_class.return_value = mock_level_mgr
            
            mock_ach_engine_instance = AsyncMock()
            mock_ach_engine.return_value = mock_ach_engine_instance
            
            await leveling_service.initialize()
            
            profile = await leveling_service.get_user_profile(12345, 67890)
            
            assert profile is not None
            assert profile.user_id == 12345
            assert profile.level == 2
            assert profile.xp == 75
            assert profile.stats['messages_count'] == 50
            assert profile.stats['links_shared'] == 5
            assert profile.stats['thanks_received'] == 3
    
    def test_service_stats(self, leveling_service):
        """Test getting service statistics."""
        stats = leveling_service.get_service_stats()
        
        assert 'initialized' in stats
        assert 'enabled' in stats
        assert 'stats' in stats
        assert 'config' in stats
        
        assert stats['initialized'] is False  # Not initialized yet
        assert stats['enabled'] is True  # Default enabled
    
    def test_is_enabled(self, leveling_service):
        """Test checking if service is enabled."""
        # Not initialized yet
        assert leveling_service.is_enabled() is False
        
        # Mock initialization
        leveling_service._initialized = True
        leveling_service._enabled = True
        assert leveling_service.is_enabled() is True
        
        # Disabled
        leveling_service._enabled = False
        assert leveling_service.is_enabled() is False