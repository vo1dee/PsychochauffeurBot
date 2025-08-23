"""
Integration tests for leveling system configuration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from modules.leveling_config import LevelingConfigManager, LevelingSystemConfig
from modules.xp_calculator import XPCalculator
from modules.level_manager import LevelManager


class TestLevelingConfigIntegration:
    """Integration tests for leveling configuration with core components."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock global config manager."""
        mock = AsyncMock()
        mock.get_config = AsyncMock()
        mock.set_config = AsyncMock()
        mock.register_change_callback = Mock()
        return mock
    
    @pytest.mark.asyncio
    async def test_config_manager_initialization(self, mock_config_manager):
        """Test that the leveling config manager initializes correctly."""
        # Mock the global config manager to return leveling system config
        mock_config_manager.get_config.return_value = {
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 2, 'link': 6, 'thanks': 10},
                'level_formula': {'base_xp': 100, 'multiplier': 1.5},
                'notifications': {'enabled': True, 'level_up_enabled': True}
            }
        }
        
        # Create leveling config manager
        config_manager = LevelingConfigManager(mock_config_manager)
        await config_manager.initialize()
        
        # Verify configuration was loaded
        config = await config_manager.get_configuration()
        assert config.enabled is True
        assert config.xp_rates.message == 2
        assert config.xp_rates.link == 6
        assert config.xp_rates.thanks == 10
        assert config.level_formula.base_xp == 100
        assert config.level_formula.multiplier == 1.5
        assert config.notifications.enabled is True
    
    @pytest.mark.asyncio
    async def test_xp_calculator_with_config(self, mock_config_manager):
        """Test XP calculator initialization with configuration."""
        # Create config manager with custom XP rates
        config_manager = LevelingConfigManager(mock_config_manager)
        mock_config_manager.get_config.return_value = {
            'overrides': {
                'xp_rates': {'message': 3, 'link': 9, 'thanks': 15}
            }
        }
        
        await config_manager.initialize()
        config = await config_manager.get_configuration()
        
        # Create XP calculator with configuration
        xp_calculator = XPCalculator(
            message_xp=config.xp_rates.message,
            link_xp=config.xp_rates.link,
            thanks_xp=config.xp_rates.thanks
        )
        
        # Verify XP rates are applied
        assert xp_calculator.MESSAGE_XP == 3
        assert xp_calculator.LINK_XP == 9
        assert xp_calculator.THANKS_XP == 15
    
    @pytest.mark.asyncio
    async def test_level_manager_with_config(self, mock_config_manager):
        """Test level manager initialization with configuration."""
        # Create config manager with custom level formula
        config_manager = LevelingConfigManager(mock_config_manager)
        mock_config_manager.get_config.return_value = {
            'overrides': {
                'level_formula': {'base_xp': 75, 'multiplier': 1.8}
            }
        }
        
        await config_manager.initialize()
        config = await config_manager.get_configuration()
        
        # Create level manager with configuration
        level_manager = LevelManager(
            base_xp=config.level_formula.base_xp,
            multiplier=config.level_formula.multiplier
        )
        
        # Verify level formula parameters are applied
        assert level_manager.base_xp == 75
        assert level_manager.multiplier == 1.8
        
        # Test level calculations with new parameters
        assert level_manager.get_level_threshold(1) == 0
        assert level_manager.get_level_threshold(2) == 75
        assert level_manager.get_level_threshold(3) == int(75 * 1.8)  # 75 * (1.8^1) = 135
    
    @pytest.mark.asyncio
    async def test_configuration_update_flow(self, mock_config_manager):
        """Test the complete configuration update flow."""
        # Initial configuration
        initial_config = {
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5},
                'level_formula': {'base_xp': 50, 'multiplier': 2.0}
            }
        }
        mock_config_manager.get_config.return_value = initial_config
        mock_config_manager.set_config.return_value = True
        
        # Create config manager
        config_manager = LevelingConfigManager(mock_config_manager)
        await config_manager.initialize()
        
        # Verify initial configuration
        config = await config_manager.get_configuration()
        assert config.xp_rates.message == 1
        assert config.level_formula.base_xp == 50
        
        # Update configuration
        updates = {
            'xp_rates': {'message': 2},
            'level_formula': {'base_xp': 100}
        }
        
        success = await config_manager.update_partial_configuration(updates)
        assert success is True
        
        # Verify updated configuration
        updated_config = await config_manager.get_configuration()
        assert updated_config.xp_rates.message == 2
        assert updated_config.level_formula.base_xp == 100
        # Other values should remain unchanged
        assert updated_config.xp_rates.link == 3
        assert updated_config.level_formula.multiplier == 2.0
    
    @pytest.mark.asyncio
    async def test_feature_toggle_integration(self, mock_config_manager):
        """Test feature toggling integration."""
        # Initial configuration
        initial_config = {
            'overrides': {
                'notifications': {'enabled': True, 'level_up_enabled': True},
                'rate_limiting': {'enabled': False}
            }
        }
        mock_config_manager.get_config.return_value = initial_config
        mock_config_manager.set_config.return_value = True
        
        # Create config manager
        config_manager = LevelingConfigManager(mock_config_manager)
        await config_manager.initialize()
        
        # Verify initial state
        assert await config_manager.get_feature_status('notifications.enabled') is True
        assert await config_manager.get_feature_status('rate_limiting.enabled') is False
        
        # Toggle features
        success = await config_manager.toggle_feature('notifications.enabled', False)
        assert success is True
        assert await config_manager.get_feature_status('notifications.enabled') is False
        
        success = await config_manager.toggle_feature('rate_limiting.enabled', True)
        assert success is True
        assert await config_manager.get_feature_status('rate_limiting.enabled') is True
    
    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, mock_config_manager):
        """Test configuration validation in the integration flow."""
        # Initial valid configuration
        initial_config = {
            'overrides': {
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5}
            }
        }
        mock_config_manager.get_config.return_value = initial_config
        
        # Create config manager
        config_manager = LevelingConfigManager(mock_config_manager)
        await config_manager.initialize()
        
        # Try to update with invalid configuration
        invalid_config = LevelingSystemConfig()
        invalid_config.xp_rates.message = -1  # Invalid negative value
        
        success = await config_manager.update_configuration(invalid_config)
        assert success is False
        
        # Original configuration should remain unchanged
        config = await config_manager.get_configuration()
        assert config.xp_rates.message == 1


if __name__ == '__main__':
    pytest.main([__file__])