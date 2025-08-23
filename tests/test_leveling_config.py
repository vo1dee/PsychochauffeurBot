"""
Tests for the leveling system configuration management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from modules.leveling_config import (
    LevelingSystemConfig,
    LevelingConfigManager,
    XPRatesConfig,
    LevelFormulaConfig,
    RateLimitingConfig,
    NotificationConfig,
    CacheConfig,
    PerformanceConfig,
    RetroactiveConfig,
    LevelFormula
)


class TestLevelingSystemConfig:
    """Test the LevelingSystemConfig dataclass."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = LevelingSystemConfig()
        
        assert config.enabled is True
        assert config.xp_rates.message == 1
        assert config.xp_rates.link == 3
        assert config.xp_rates.thanks == 5
        assert config.level_formula.formula == LevelFormula.EXPONENTIAL
        assert config.level_formula.base_xp == 50
        assert config.level_formula.multiplier == 2.0
        assert config.notifications.enabled is True
        assert config.cache.enabled is True
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid configuration
        config = LevelingSystemConfig()
        errors = config.validate()
        assert len(errors) == 0
        
        # Invalid configuration - negative XP rates
        config.xp_rates.message = -1
        errors = config.validate()
        assert len(errors) > 0
        assert any("negative" in error.lower() for error in errors)
    
    def test_configuration_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = LevelingSystemConfig()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'enabled' in config_dict
        assert 'xp_rates' in config_dict
        assert 'level_formula' in config_dict
        assert config_dict['enabled'] is True
    
    def test_configuration_from_dict(self):
        """Test configuration deserialization from dictionary."""
        config_data = {
            'enabled': False,
            'xp_rates': {
                'message': 2,
                'link': 6,
                'thanks': 10
            },
            'level_formula': {
                'formula': 'linear',
                'base_xp': 100,
                'multiplier': 1.5
            }
        }
        
        config = LevelingSystemConfig.from_dict(config_data)
        
        assert config.enabled is False
        assert config.xp_rates.message == 2
        assert config.xp_rates.link == 6
        assert config.xp_rates.thanks == 10
        assert config.level_formula.formula == LevelFormula.LINEAR
        assert config.level_formula.base_xp == 100
        assert config.level_formula.multiplier == 1.5


class TestXPRatesConfig:
    """Test XP rates configuration."""
    
    def test_valid_xp_rates(self):
        """Test valid XP rates configuration."""
        config = XPRatesConfig(message=2, link=5, thanks=8)
        errors = config.validate()
        assert len(errors) == 0
    
    def test_invalid_xp_rates(self):
        """Test invalid XP rates configuration."""
        config = XPRatesConfig(message=-1, link=-2, thanks=-3)
        errors = config.validate()
        assert len(errors) == 3
        assert all("negative" in error.lower() for error in errors)


class TestLevelFormulaConfig:
    """Test level formula configuration."""
    
    def test_exponential_formula_validation(self):
        """Test exponential formula validation."""
        config = LevelFormulaConfig(
            formula=LevelFormula.EXPONENTIAL,
            base_xp=50,
            multiplier=2.0
        )
        errors = config.validate()
        assert len(errors) == 0
        
        # Invalid multiplier for exponential
        config.multiplier = 0.5
        errors = config.validate()
        assert len(errors) > 0
    
    def test_linear_formula_validation(self):
        """Test linear formula validation."""
        config = LevelFormulaConfig(
            formula=LevelFormula.LINEAR,
            base_xp=50,
            linear_increment=100
        )
        errors = config.validate()
        assert len(errors) == 0
        
        # Invalid increment for linear
        config.linear_increment = -10
        errors = config.validate()
        assert len(errors) > 0
    
    def test_custom_formula_validation(self):
        """Test custom formula validation."""
        config = LevelFormulaConfig(
            formula=LevelFormula.CUSTOM,
            custom_thresholds=[50, 150, 300, 500]
        )
        errors = config.validate()
        assert len(errors) == 0
        
        # Missing thresholds for custom
        config.custom_thresholds = []
        errors = config.validate()
        assert len(errors) > 0


class TestLevelingConfigManager:
    """Test the LevelingConfigManager class."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock = AsyncMock()
        mock.get_config = AsyncMock()
        mock.set_config = AsyncMock()
        mock.register_change_callback = Mock()
        return mock
    
    @pytest.fixture
    def config_manager(self, mock_config_manager):
        """Create a LevelingConfigManager instance."""
        return LevelingConfigManager(mock_config_manager)
    
    @pytest.mark.asyncio
    async def test_initialization(self, config_manager, mock_config_manager):
        """Test configuration manager initialization."""
        # Mock config data
        mock_config_manager.get_config.return_value = {
            'overrides': {
                'enabled': True,
                'xp_rates': {'message': 1, 'link': 3, 'thanks': 5}
            }
        }
        
        await config_manager.initialize()
        
        assert config_manager._current_config is not None
        assert config_manager._current_config.enabled is True
        mock_config_manager.register_change_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_configuration(self, config_manager, mock_config_manager):
        """Test configuration loading."""
        # Mock config data
        config_data = {
            'overrides': {
                'enabled': False,
                'xp_rates': {'message': 2, 'link': 4, 'thanks': 6},
                'notifications': {'enabled': False}
            }
        }
        mock_config_manager.get_config.return_value = config_data
        
        config = await config_manager.load_configuration()
        
        assert config.enabled is False
        assert config.xp_rates.message == 2
        assert config.notifications.enabled is False
        mock_config_manager.get_config.assert_called_once_with(module_name='leveling_system')
    
    @pytest.mark.asyncio
    async def test_update_configuration(self, config_manager, mock_config_manager):
        """Test configuration updates."""
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        
        # Create new configuration
        new_config = LevelingSystemConfig()
        new_config.enabled = False
        new_config.xp_rates.message = 3
        
        # Mock successful save
        mock_config_manager.set_config.return_value = True
        
        success = await config_manager.update_configuration(new_config)
        
        assert success is True
        assert config_manager._current_config.enabled is False
        assert config_manager._current_config.xp_rates.message == 3
        mock_config_manager.set_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_partial_configuration_update(self, config_manager, mock_config_manager):
        """Test partial configuration updates."""
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        mock_config_manager.set_config.return_value = True
        
        updates = {
            'xp_rates': {'message': 5},
            'notifications': {'enabled': False}
        }
        
        success = await config_manager.update_partial_configuration(updates)
        
        assert success is True
        # The current config should be updated
        assert config_manager._current_config.xp_rates.message == 5
        assert config_manager._current_config.notifications.enabled is False
        # Other values should remain unchanged
        assert config_manager._current_config.xp_rates.link == 3  # default
        assert config_manager._current_config.enabled is True  # default
    
    @pytest.mark.asyncio
    async def test_toggle_feature(self, config_manager, mock_config_manager):
        """Test feature toggling."""
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        mock_config_manager.set_config.return_value = True
        
        # Toggle notifications off
        success = await config_manager.toggle_feature('notifications.enabled', False)
        
        assert success is True
        assert config_manager._current_config.notifications.enabled is False
        
        # Toggle notifications back on
        success = await config_manager.toggle_feature('notifications.enabled', True)
        
        assert success is True
        assert config_manager._current_config.notifications.enabled is True
    
    @pytest.mark.asyncio
    async def test_get_feature_status(self, config_manager):
        """Test getting feature status."""
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        
        # Test existing feature
        status = await config_manager.get_feature_status('notifications.enabled')
        assert status is True
        
        # Test non-existing feature
        status = await config_manager.get_feature_status('nonexistent.feature')
        assert status is None
    
    @pytest.mark.asyncio
    async def test_configuration_validation_failure(self, config_manager, mock_config_manager):
        """Test configuration validation failure."""
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        
        # Create invalid configuration
        invalid_config = LevelingSystemConfig()
        invalid_config.xp_rates.message = -1  # Invalid negative value
        
        success = await config_manager.update_configuration(invalid_config)
        
        assert success is False
        # Original config should remain unchanged
        assert config_manager._current_config.xp_rates.message == 1
    
    def test_config_summary(self, config_manager):
        """Test configuration summary generation."""
        config_manager._current_config = LevelingSystemConfig()
        
        summary = config_manager.get_config_summary()
        
        assert isinstance(summary, dict)
        assert 'enabled' in summary
        assert 'xp_rates' in summary
        assert 'level_formula' in summary
        assert 'features' in summary
        assert summary['enabled'] is True
        assert summary['xp_rates']['message'] == 1


class TestConfigurationIntegration:
    """Integration tests for configuration system."""
    
    @pytest.mark.asyncio
    async def test_configuration_change_callback(self):
        """Test configuration change callbacks."""
        config_manager = LevelingConfigManager()
        
        # Track callback calls
        callback_calls = []
        
        async def test_callback(old_config, new_config):
            callback_calls.append((old_config, new_config))
        
        config_manager.register_change_callback(test_callback)
        
        # Initialize with default config
        config_manager._current_config = LevelingSystemConfig()
        
        # Update configuration
        new_config = LevelingSystemConfig()
        new_config.enabled = False
        
        # Simulate successful update (without actual config manager)
        old_config = config_manager._current_config
        config_manager._current_config = new_config
        await config_manager._notify_config_change(old_config, new_config)
        
        # Check callback was called
        assert len(callback_calls) == 1
        assert callback_calls[0][0].enabled is True  # old config
        assert callback_calls[0][1].enabled is False  # new config


if __name__ == '__main__':
    pytest.main([__file__])