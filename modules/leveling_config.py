"""
Leveling System Configuration Management

This module provides comprehensive configuration management for the user leveling system,
including feature toggles, XP rates, level formulas, and runtime configuration updates.
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class LevelFormula(Enum):
    """Available level progression formulas."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"
    CUSTOM = "custom"


@dataclass
class XPRatesConfig:
    """Configuration for XP rates."""
    message: int = 1
    link: int = 3
    thanks: int = 5
    
    def validate(self) -> List[str]:
        """Validate XP rates configuration."""
        errors = []
        if self.message < 0:
            errors.append("Message XP rate cannot be negative")
        if self.link < 0:
            errors.append("Link XP rate cannot be negative")
        if self.thanks < 0:
            errors.append("Thanks XP rate cannot be negative")
        return errors


@dataclass
class LevelFormulaConfig:
    """Configuration for level progression formula."""
    formula: LevelFormula = LevelFormula.EXPONENTIAL
    base_xp: int = 50
    multiplier: float = 2.0
    linear_increment: int = 100  # For linear formula
    logarithmic_base: float = 1.5  # For logarithmic formula
    custom_thresholds: List[int] = field(default_factory=list)  # For custom formula
    
    def validate(self) -> List[str]:
        """Validate level formula configuration."""
        errors = []
        if self.base_xp <= 0:
            errors.append("Base XP must be positive")
        if self.multiplier <= 1.0 and self.formula == LevelFormula.EXPONENTIAL:
            errors.append("Exponential multiplier must be greater than 1.0")
        if self.linear_increment <= 0 and self.formula == LevelFormula.LINEAR:
            errors.append("Linear increment must be positive")
        if self.logarithmic_base <= 1.0 and self.formula == LevelFormula.LOGARITHMIC:
            errors.append("Logarithmic base must be greater than 1.0")
        if self.formula == LevelFormula.CUSTOM and not self.custom_thresholds:
            errors.append("Custom formula requires threshold values")
        return errors


@dataclass
class RateLimitingConfig:
    """Configuration for rate limiting."""
    enabled: bool = False
    max_xp_per_minute: int = 10
    window_size_seconds: int = 60
    burst_limit: int = 5
    
    def validate(self) -> List[str]:
        """Validate rate limiting configuration."""
        errors = []
        if self.max_xp_per_minute <= 0:
            errors.append("Max XP per minute must be positive")
        if self.window_size_seconds <= 0:
            errors.append("Window size must be positive")
        if self.burst_limit <= 0:
            errors.append("Burst limit must be positive")
        return errors


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    level_up_enabled: bool = True
    achievements_enabled: bool = True
    celebration_emoji: bool = True
    batch_achievements: bool = True
    max_achievements_per_message: int = 5
    
    def validate(self) -> List[str]:
        """Validate notification configuration."""
        errors = []
        if self.max_achievements_per_message <= 0:
            errors.append("Max achievements per message must be positive")
        return errors


@dataclass
class CacheConfig:
    """Configuration for caching system."""
    enabled: bool = True
    user_stats_ttl: int = 300  # 5 minutes
    achievements_ttl: int = 3600  # 1 hour
    leaderboard_ttl: int = 600  # 10 minutes
    max_cache_size: int = 1000
    
    def validate(self) -> List[str]:
        """Validate cache configuration."""
        errors = []
        if self.user_stats_ttl <= 0:
            errors.append("User stats TTL must be positive")
        if self.achievements_ttl <= 0:
            errors.append("Achievements TTL must be positive")
        if self.leaderboard_ttl <= 0:
            errors.append("Leaderboard TTL must be positive")
        if self.max_cache_size <= 0:
            errors.append("Max cache size must be positive")
        return errors


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring and optimization."""
    monitoring_enabled: bool = True
    max_processing_time_ms: int = 100
    performance_degradation_threshold_ms: int = 500
    health_check_interval_seconds: int = 300
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    
    def validate(self) -> List[str]:
        """Validate performance configuration."""
        errors = []
        if self.max_processing_time_ms <= 0:
            errors.append("Max processing time must be positive")
        if self.performance_degradation_threshold_ms <= 0:
            errors.append("Performance degradation threshold must be positive")
        if self.health_check_interval_seconds <= 0:
            errors.append("Health check interval must be positive")
        if self.circuit_breaker_failure_threshold <= 0:
            errors.append("Circuit breaker failure threshold must be positive")
        if self.circuit_breaker_recovery_timeout <= 0:
            errors.append("Circuit breaker recovery timeout must be positive")
        return errors


@dataclass
class RetroactiveConfig:
    """Configuration for retroactive checks."""
    perform_startup_checks: bool = False
    check_achievements_on_profile: bool = True
    check_levels_on_profile: bool = True
    batch_size: int = 100
    max_concurrent_checks: int = 5
    
    def validate(self) -> List[str]:
        """Validate retroactive configuration."""
        errors = []
        if self.batch_size <= 0:
            errors.append("Batch size must be positive")
        if self.max_concurrent_checks <= 0:
            errors.append("Max concurrent checks must be positive")
        return errors


@dataclass
class LevelingSystemConfig:
    """Complete leveling system configuration."""
    enabled: bool = True
    xp_rates: XPRatesConfig = field(default_factory=XPRatesConfig)
    level_formula: LevelFormulaConfig = field(default_factory=LevelFormulaConfig)
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    retroactive: RetroactiveConfig = field(default_factory=RetroactiveConfig)
    
    def validate(self) -> List[str]:
        """Validate the entire configuration."""
        errors = []
        
        # Validate all sub-configurations
        errors.extend(self.xp_rates.validate())
        errors.extend(self.level_formula.validate())
        errors.extend(self.rate_limiting.validate())
        errors.extend(self.notifications.validate())
        errors.extend(self.cache.validate())
        errors.extend(self.performance.validate())
        errors.extend(self.retroactive.validate())
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LevelingSystemConfig':
        """Create configuration from dictionary."""
        # Handle nested configurations
        config_data = data.copy()
        
        if 'xp_rates' in config_data and isinstance(config_data['xp_rates'], dict):
            config_data['xp_rates'] = XPRatesConfig(**config_data['xp_rates'])
        
        if 'level_formula' in config_data and isinstance(config_data['level_formula'], dict):
            formula_data = config_data['level_formula'].copy()
            if 'formula' in formula_data and isinstance(formula_data['formula'], str):
                formula_data['formula'] = LevelFormula(formula_data['formula'])
            config_data['level_formula'] = LevelFormulaConfig(**formula_data)
        
        if 'rate_limiting' in config_data and isinstance(config_data['rate_limiting'], dict):
            config_data['rate_limiting'] = RateLimitingConfig(**config_data['rate_limiting'])
        
        if 'notifications' in config_data and isinstance(config_data['notifications'], dict):
            config_data['notifications'] = NotificationConfig(**config_data['notifications'])
        
        if 'cache' in config_data and isinstance(config_data['cache'], dict):
            config_data['cache'] = CacheConfig(**config_data['cache'])
        
        if 'performance' in config_data and isinstance(config_data['performance'], dict):
            config_data['performance'] = PerformanceConfig(**config_data['performance'])
        
        if 'retroactive' in config_data and isinstance(config_data['retroactive'], dict):
            config_data['retroactive'] = RetroactiveConfig(**config_data['retroactive'])
        
        return cls(**config_data)


class LevelingConfigManager:
    """
    Configuration manager for the leveling system with runtime updates and validation.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the leveling configuration manager.
        
        Args:
            config_manager: Global configuration manager instance
        """
        self.config_manager = config_manager
        self._current_config: Optional[LevelingSystemConfig] = None
        self._change_callbacks: List[Callable[[LevelingSystemConfig, LevelingSystemConfig], Awaitable[None]]] = []
        self._config_lock = asyncio.Lock()
        self._last_update = datetime.now()
        
        logger.info("LevelingConfigManager initialized")
    
    async def initialize(self) -> None:
        """Initialize the configuration manager."""
        logger.info("Initializing LevelingConfigManager...")
        
        try:
            # Load initial configuration
            await self.load_configuration()
            
            # Register for configuration change notifications if available
            if self.config_manager and hasattr(self.config_manager, 'register_change_callback'):
                self.config_manager.register_change_callback('leveling_system', self._on_config_change)
            
            logger.info("LevelingConfigManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize LevelingConfigManager: {e}", exc_info=True)
            # Create default configuration as fallback
            self._current_config = LevelingSystemConfig()
            logger.info("Using default configuration as fallback")
    
    async def load_configuration(self) -> LevelingSystemConfig:
        """Load configuration from the global config manager."""
        async with self._config_lock:
            try:
                if self.config_manager:
                    # Load from global configuration
                    config_data = await self.config_manager.get_config(module_name='leveling_system')
                    
                    if config_data and 'overrides' in config_data:
                        # Extract the actual configuration from overrides
                        raw_config = config_data['overrides']
                        
                        # Validate and create configuration object
                        self._current_config = LevelingSystemConfig.from_dict(raw_config)
                        
                        # Validate configuration
                        validation_errors = self._current_config.validate()
                        if validation_errors:
                            logger.warning(f"Configuration validation errors: {validation_errors}")
                            # Use defaults for invalid values
                            self._current_config = self._merge_with_defaults(self._current_config)
                    else:
                        # No configuration found, create default
                        self._current_config = LevelingSystemConfig()
                        await self._save_default_configuration()
                else:
                    # No config manager, use defaults
                    self._current_config = LevelingSystemConfig()
                
                self._last_update = datetime.now()
                logger.info("Configuration loaded successfully")
                
            except Exception as e:
                logger.error(f"Error loading configuration: {e}", exc_info=True)
                # Fallback to default configuration
                self._current_config = LevelingSystemConfig()
            
            return self._current_config
    
    async def _save_default_configuration(self) -> None:
        """Save default configuration to the global config manager."""
        if not self.config_manager or not self._current_config:
            return
        
        try:
            # Prepare configuration data for saving
            config_data = {
                'enabled': True,
                'overrides': self._current_config.to_dict()
            }
            
            # Save to global configuration
            await self.config_manager.set_config(
                chat_id=None,
                chat_type=None,
                module_name='leveling_system',
                config=config_data
            )
            
            logger.info("Default configuration saved to global config")
            
        except Exception as e:
            logger.error(f"Failed to save default configuration: {e}", exc_info=True)
    
    def _merge_with_defaults(self, config: LevelingSystemConfig) -> LevelingSystemConfig:
        """Merge configuration with defaults for invalid values."""
        default_config = LevelingSystemConfig()
        
        # This is a simplified merge - in practice, you'd want more sophisticated merging
        # For now, we'll just return the default if there are validation errors
        return default_config
    
    async def get_configuration(self) -> LevelingSystemConfig:
        """Get the current configuration."""
        if self._current_config is None:
            await self.load_configuration()
        
        return self._current_config
    
    async def update_configuration(self, new_config: LevelingSystemConfig) -> bool:
        """
        Update the configuration with validation.
        
        Args:
            new_config: New configuration to apply
            
        Returns:
            True if update was successful, False otherwise
        """
        async with self._config_lock:
            try:
                # Validate new configuration
                validation_errors = new_config.validate()
                if validation_errors:
                    logger.error(f"Configuration validation failed: {validation_errors}")
                    return False
                
                # Store old configuration for callbacks
                old_config = self._current_config
                
                # Update current configuration
                self._current_config = new_config
                self._last_update = datetime.now()
                
                # Save to global configuration if available
                if self.config_manager:
                    config_data = {
                        'enabled': new_config.enabled,
                        'overrides': new_config.to_dict()
                    }
                    
                    await self.config_manager.set_config(
                        chat_id=None,
                        chat_type=None,
                        module_name='leveling_system',
                        config=config_data
                    )
                
                # Notify change callbacks
                await self._notify_config_change(old_config, new_config)
                
                logger.info("Configuration updated successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}", exc_info=True)
                return False
    
    async def update_partial_configuration(self, updates: Dict[str, Any]) -> bool:
        """
        Update specific configuration values without replacing the entire config.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            True if update was successful, False otherwise
        """
        current_config = await self.get_configuration()
        
        # Create a new configuration with updates
        config_dict = current_config.to_dict()
        
        # Apply updates (supports nested updates)
        self._apply_nested_updates(config_dict, updates)
        
        # Create new configuration object
        try:
            new_config = LevelingSystemConfig.from_dict(config_dict)
            return await self.update_configuration(new_config)
        except Exception as e:
            logger.error(f"Failed to apply partial configuration update: {e}", exc_info=True)
            return False
    
    def _apply_nested_updates(self, target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Apply nested updates to a dictionary."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._apply_nested_updates(target[key], value)
            else:
                target[key] = value
    
    async def toggle_feature(self, feature_path: str, enabled: bool) -> bool:
        """
        Toggle a specific feature on or off.
        
        Args:
            feature_path: Dot-separated path to the feature (e.g., 'notifications.level_up_enabled')
            enabled: Whether to enable or disable the feature
            
        Returns:
            True if toggle was successful, False otherwise
        """
        try:
            # Convert feature path to nested dictionary update
            path_parts = feature_path.split('.')
            updates = {}
            current = updates
            
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    current[part] = enabled
                else:
                    current[part] = {}
                    current = current[part]
            
            return await self.update_partial_configuration(updates)
            
        except Exception as e:
            logger.error(f"Failed to toggle feature {feature_path}: {e}", exc_info=True)
            return False
    
    async def get_feature_status(self, feature_path: str) -> Optional[bool]:
        """
        Get the status of a specific feature.
        
        Args:
            feature_path: Dot-separated path to the feature
            
        Returns:
            Feature status or None if not found
        """
        try:
            config = await self.get_configuration()
            config_dict = config.to_dict()
            
            # Navigate to the feature
            current = config_dict
            for part in feature_path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            
            return current if isinstance(current, bool) else None
            
        except Exception as e:
            logger.error(f"Failed to get feature status for {feature_path}: {e}", exc_info=True)
            return None
    
    def register_change_callback(self, callback: Callable[[LevelingSystemConfig, LevelingSystemConfig], Awaitable[None]]) -> None:
        """
        Register a callback to be notified of configuration changes.
        
        Args:
            callback: Async function that takes (old_config, new_config) parameters
        """
        self._change_callbacks.append(callback)
        logger.info(f"Registered configuration change callback: {callback.__name__}")
    
    async def _notify_config_change(self, old_config: Optional[LevelingSystemConfig], new_config: LevelingSystemConfig) -> None:
        """Notify all registered callbacks of configuration changes."""
        if not old_config:
            return
        
        for callback in self._change_callbacks:
            try:
                await callback(old_config, new_config)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}", exc_info=True)
    
    async def _on_config_change(self, module_name: str, new_config: Dict[str, Any]) -> None:
        """Handle configuration changes from the global config manager."""
        if module_name == 'leveling_system':
            logger.info("Received configuration change notification")
            await self.load_configuration()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        if not self._current_config:
            return {}
        
        return {
            'enabled': self._current_config.enabled,
            'last_update': self._last_update.isoformat(),
            'xp_rates': {
                'message': self._current_config.xp_rates.message,
                'link': self._current_config.xp_rates.link,
                'thanks': self._current_config.xp_rates.thanks
            },
            'level_formula': {
                'type': self._current_config.level_formula.formula.value,
                'base_xp': self._current_config.level_formula.base_xp,
                'multiplier': self._current_config.level_formula.multiplier
            },
            'features': {
                'rate_limiting': self._current_config.rate_limiting.enabled,
                'notifications': self._current_config.notifications.enabled,
                'caching': self._current_config.cache.enabled,
                'performance_monitoring': self._current_config.performance.monitoring_enabled
            }
        }


# Global instance for easy access
leveling_config_manager: Optional[LevelingConfigManager] = None


def get_leveling_config_manager() -> Optional[LevelingConfigManager]:
    """Get the global leveling configuration manager instance."""
    return leveling_config_manager


def initialize_leveling_config_manager(config_manager=None) -> LevelingConfigManager:
    """Initialize the global leveling configuration manager."""
    global leveling_config_manager
    leveling_config_manager = LevelingConfigManager(config_manager)
    return leveling_config_manager