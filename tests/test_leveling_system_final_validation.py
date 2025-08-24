"""
Final Validation Tests for User Leveling System

This test suite validates that the leveling system is properly integrated
and can be instantiated with the correct dependencies.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from modules.user_leveling_service import UserLevelingService
from modules.leveling_models import UserStats, Achievement
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager


class TestLevelingSystemValidation:
    """Test leveling system integration and basic functionality."""
    
    def test_user_leveling_service_can_be_instantiated(self):
        """Test that UserLevelingService can be instantiated with mocked dependencies."""
        # Mock dependencies
        config_manager = Mock()
        database = Mock()
        
        # Create service
        service = UserLevelingService(config_manager=config_manager, database=database)
        
        # Verify service was created
        assert service is not None
        assert service.config_manager == config_manager
        assert service.database == database
        assert not service._initialized
    
    def test_xp_calculator_basic_functionality(self):
        """Test XP calculator basic functionality."""
        calculator = XPCalculator()
        
        # Test XP rates (stored as constants)
        assert calculator.MESSAGE_XP == 1
        assert calculator.LINK_XP == 3
        assert calculator.THANKS_XP == 5
        
        # Test link detection
        links = calculator.detect_links("Check this out: https://example.com and http://test.com")
        assert len(links) == 2
        assert "https://example.com" in links
        assert "http://test.com" in links
    
    def test_level_manager_basic_functionality(self):
        """Test level manager basic functionality."""
        manager = LevelManager(base_xp=50, multiplier=2.0)
        
        # Test level calculations
        assert manager.calculate_level(0) == 1
        assert manager.calculate_level(49) == 1
        assert manager.calculate_level(50) == 2
        assert manager.calculate_level(100) == 3
        assert manager.calculate_level(200) == 4
        
        # Test thresholds (exponential formula: base_xp * (2^(level-2)))
        assert manager.get_level_threshold(1) == 0
        assert manager.get_level_threshold(2) == 50   # 50 * (2^0) = 50
        assert manager.get_level_threshold(3) == 100  # 50 * (2^1) = 100
        assert manager.get_level_threshold(4) == 200  # 50 * (2^2) = 200
    
    def test_user_stats_model_functionality(self):
        """Test UserStats model basic functionality."""
        stats = UserStats(user_id=123, chat_id=456)
        
        # Test initial values
        assert stats.user_id == 123
        assert stats.chat_id == 456
        assert stats.xp == 0
        assert stats.level == 1
        assert stats.messages_count == 0
        assert stats.links_shared == 0
        assert stats.thanks_received == 0
        
        # Test XP addition
        stats.add_xp(10)
        assert stats.xp == 10
        
        # Test counter increments
        stats.increment_messages()
        assert stats.messages_count == 1
        
        stats.increment_links()
        assert stats.links_shared == 1
        
        stats.increment_thanks()
        assert stats.thanks_received == 1
    
    def test_achievement_model_functionality(self):
        """Test Achievement model basic functionality."""
        achievement = Achievement(
            id="test_achievement",
            title="Test Achievement",
            description="A test achievement",
            emoji="🏆",
            sticker="🏆",
            condition_type="messages_count",
            condition_value=100,
            category="activity"
        )
        
        # Test basic properties
        assert achievement.id == "test_achievement"
        assert achievement.title == "Test Achievement"
        assert achievement.condition_type == "messages_count"
        assert achievement.condition_value == 100
        
        # Test condition checking
        user_stats = UserStats(user_id=123, chat_id=456, messages_count=50)
        assert not achievement.check_condition(user_stats)
        
        user_stats.messages_count = 100
        assert achievement.check_condition(user_stats)
        
        user_stats.messages_count = 150
        assert achievement.check_condition(user_stats)
    
    @pytest.mark.asyncio
    async def test_service_initialization_with_mocks(self):
        """Test that service can be initialized with proper mocks."""
        # Mock dependencies
        config_manager = Mock()
        config_manager.get_config = AsyncMock(return_value={
            'enabled': True,
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5},
                'level_formula': {'base_xp': 50, 'multiplier': 2.0},
                'notifications': {'enabled': True}
            }
        })
        
        database = Mock()
        
        # Create service
        service = UserLevelingService(config_manager=config_manager, database=database)
        
        # Mock repositories to prevent actual database calls
        with patch('modules.repositories.UserStatsRepository') as mock_user_repo, \
             patch('modules.repositories.AchievementRepository') as mock_achievement_repo, \
             patch('modules.leveling_notification_service.LevelingNotificationService') as mock_notification:
            
            mock_user_repo.return_value = Mock()
            mock_achievement_repo.return_value = Mock()
            mock_notification.return_value = Mock()
            
            # Initialize service
            await service.initialize()
            
            # Verify service is initialized
            assert service._initialized
            assert service.xp_calculator is not None
            assert service.level_manager is not None
    
    def test_service_registry_integration_exists(self):
        """Test that service registry integration exists."""
        from modules.service_factories import ServiceFactory
        
        # Verify the factory method exists
        assert hasattr(ServiceFactory, 'create_user_leveling_service')
        
        # Test factory method can be called (with mocks)
        mock_registry = Mock()
        mock_registry.get_service.side_effect = lambda name: {
            'config_manager': Mock(),
            'database': Mock()
        }.get(name)
        
        service = ServiceFactory.create_user_leveling_service(mock_registry)
        assert service is not None
        assert isinstance(service, UserLevelingService)
    
    def test_message_handler_integration_exists(self):
        """Test that message handler integration exists."""
        from modules.message_handler import _process_leveling_system
        
        # Verify the integration function exists
        assert callable(_process_leveling_system)
    
    @pytest.mark.asyncio
    async def test_message_handler_integration_with_mocks(self):
        """Test message handler integration with mocked components."""
        from modules.message_handler import _process_leveling_system
        from telegram import Update, Message, User, Chat
        
        # Create mock update
        user = Mock(spec=User)
        user.id = 123
        user.is_bot = False
        
        chat = Mock(spec=Chat)
        chat.id = 456
        chat.type = "group"
        
        message = Mock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.text = "Hello world!"
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_chat = chat
        
        # Create mock context with service registry
        leveling_service = Mock()
        leveling_service.is_enabled.return_value = True
        leveling_service.process_message = AsyncMock()
        
        service_registry = Mock()
        service_registry.get_service.return_value = leveling_service
        
        context = Mock()
        context.bot_data = {'service_registry': service_registry}
        
        # Call integration function
        await _process_leveling_system(update, context)
        
        # Verify leveling service was called
        leveling_service.process_message.assert_called_once_with(update, context)
    
    @pytest.mark.asyncio
    async def test_no_duplicate_leveling_processing(self):
        """Test that leveling processing only happens once per message."""
        from modules.message_handler import _process_leveling_system
        from modules.handlers.message_handlers import handle_message
        
        # Mock leveling service
        leveling_service = Mock()
        leveling_service.is_enabled.return_value = True
        leveling_service.process_message = AsyncMock()
        
        service_registry = Mock()
        service_registry.get_service.return_value = leveling_service
        
        # Mock update and context
        update = Mock()
        update.message = Mock()
        update.message.text = "Test message"
        update.message.from_user = Mock()
        update.message.from_user.id = 123
        update.message.from_user.is_bot = False
        update.effective_chat = Mock()
        update.effective_chat.id = 456
        update.effective_chat.type = "group"
        
        context = Mock()
        context.bot_data = {'service_registry': service_registry}
        context.application = Mock()
        context.application.bot_data = {'service_registry': service_registry}
        
        # Test 1: Main handler should call leveling
        await _process_leveling_system(update, context)
        assert leveling_service.process_message.call_count == 1
        
        # Reset mock
        leveling_service.process_message.reset_mock()
        
        # Test 2: New handler should NOT call leveling
        with patch('modules.handlers.message_handlers.update_message_history'), \
             patch('modules.handlers.message_handlers.should_restrict_user', return_value=False), \
             patch('modules.handlers.message_handlers.process_message_content', return_value=("Test message", [])), \
             patch('modules.handlers.message_handlers.needs_gpt_response', return_value=(False, None)), \
             patch('modules.handlers.message_handlers.handle_random_gpt_response'):
            
            await handle_message(update, context)
        
        # Should not have called leveling service
        assert leveling_service.process_message.call_count == 0
    
    def test_all_required_modules_can_be_imported(self):
        """Test that all required modules can be imported without errors."""
        # Test core service
        from modules.user_leveling_service import UserLevelingService
        assert UserLevelingService is not None
        
        # Test models
        from modules.leveling_models import UserStats, Achievement, UserProfile
        assert UserStats is not None
        assert Achievement is not None
        assert UserProfile is not None
        
        # Test core components
        from modules.xp_calculator import XPCalculator
        from modules.level_manager import LevelManager
        assert XPCalculator is not None
        assert LevelManager is not None
        
        # Test repositories
        from modules.repositories import UserStatsRepository, AchievementRepository
        assert UserStatsRepository is not None
        assert AchievementRepository is not None
        
        # Test service factory
        from modules.service_factories import ServiceFactory
        assert ServiceFactory is not None
        
        # Test message handler integration
        from modules.message_handler import _process_leveling_system
        assert _process_leveling_system is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])