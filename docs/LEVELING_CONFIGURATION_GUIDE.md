# Leveling System Configuration Guide

This guide explains how to configure and manage the user leveling system in the PsychoChauffeur bot.

## Overview

The leveling system now includes a comprehensive configuration management system that allows for:

- **Runtime Configuration Updates**: Change settings without restarting the bot
- **Feature Toggles**: Enable/disable specific features on the fly
- **Validation**: Automatic validation of configuration values
- **Default Values**: Fallback to sensible defaults for missing configuration
- **Hot Reloading**: Configuration changes are applied immediately

## Configuration Structure

The leveling system configuration is organized into several sections:

### System Control
- `enabled`: Enable/disable the entire leveling system

### XP Rates
- `xp_rates.message`: XP awarded per message (default: 1)
- `xp_rates.link`: XP awarded for sharing links (default: 3)
- `xp_rates.thanks`: XP awarded for receiving thanks (default: 5)

### Level Formula
- `level_formula.formula`: Type of progression ("exponential", "linear", "logarithmic", "custom")
- `level_formula.base_xp`: Base XP for level calculations (default: 50)
- `level_formula.multiplier`: Multiplier for exponential formula (default: 2.0)
- `level_formula.linear_increment`: XP increment for linear formula (default: 100)
- `level_formula.logarithmic_base`: Base for logarithmic formula (default: 1.5)
- `level_formula.custom_thresholds`: Custom level thresholds array

### Rate Limiting
- `rate_limiting.enabled`: Enable rate limiting (default: false)
- `rate_limiting.max_xp_per_minute`: Max XP per user per minute (default: 10)
- `rate_limiting.window_size_seconds`: Rate limiting window (default: 60)
- `rate_limiting.burst_limit`: Burst limit for rapid gains (default: 5)

### Notifications
- `notifications.enabled`: Enable all notifications (default: true)
- `notifications.level_up_enabled`: Enable level up notifications (default: true)
- `notifications.achievements_enabled`: Enable achievement notifications (default: true)
- `notifications.celebration_emoji`: Include celebration emojis (default: true)
- `notifications.batch_achievements`: Batch multiple achievements (default: true)
- `notifications.max_achievements_per_message`: Max achievements per message (default: 5)

### Caching
- `cache.enabled`: Enable caching (default: true)
- `cache.user_stats_ttl`: User stats cache TTL in seconds (default: 300)
- `cache.achievements_ttl`: Achievements cache TTL in seconds (default: 3600)
- `cache.leaderboard_ttl`: Leaderboard cache TTL in seconds (default: 600)
- `cache.max_cache_size`: Maximum cache size (default: 1000)

### Performance
- `performance.monitoring_enabled`: Enable performance monitoring (default: true)
- `performance.max_processing_time_ms`: Max processing time in ms (default: 100)
- `performance.performance_degradation_threshold_ms`: Degradation threshold in ms (default: 500)
- `performance.health_check_interval_seconds`: Health check interval (default: 300)
- `performance.circuit_breaker_enabled`: Enable circuit breaker (default: true)
- `performance.circuit_breaker_failure_threshold`: Failure threshold (default: 5)
- `performance.circuit_breaker_recovery_timeout`: Recovery timeout in seconds (default: 60)

### Retroactive Processing
- `retroactive.perform_startup_checks`: Perform checks on startup (default: false)
- `retroactive.check_achievements_on_profile`: Check achievements on profile view (default: true)
- `retroactive.check_levels_on_profile`: Recalculate levels on profile view (default: true)
- `retroactive.batch_size`: Batch size for processing (default: 100)
- `retroactive.max_concurrent_checks`: Max concurrent checks (default: 5)

## Using the Configuration Command

The `/leveling_config` command provides a user-friendly interface for managing configuration:

### View Current Configuration
```
/leveling_config
```
Shows the complete current configuration with all settings and their values.

### Get Specific Setting
```
/leveling_config get xp_rates.message
/leveling_config get notifications.enabled
/leveling_config get level_formula.base_xp
```

### Set Specific Setting
```
/leveling_config set xp_rates.message 2
/leveling_config set level_formula.base_xp 75
/leveling_config set notifications.enabled true
```

### Toggle Features
```
/leveling_config toggle notifications.enabled
/leveling_config toggle rate_limiting.enabled
/leveling_config toggle cache.enabled
```

### Reload Configuration
```
/leveling_config reload
```
Reloads configuration from the configuration file.

### Reset to Defaults
```
/leveling_config reset
```
Resets all configuration to default values.

## Programmatic Configuration

For programmatic access, use the `LevelingConfigManager`:

```python
from modules.leveling_config import get_leveling_config_manager

# Get the config manager
config_manager = get_leveling_config_manager()

# Get current configuration
config = await config_manager.get_configuration()

# Update specific settings
updates = {
    'xp_rates': {'message': 2},
    'notifications': {'enabled': False}
}
success = await config_manager.update_partial_configuration(updates)

# Toggle a feature
success = await config_manager.toggle_feature('rate_limiting.enabled', True)

# Get feature status
enabled = await config_manager.get_feature_status('notifications.enabled')
```

## Configuration Validation

The system automatically validates all configuration changes:

- **Type Validation**: Ensures values are of the correct type (boolean, integer, float, string)
- **Range Validation**: Checks that numeric values are within acceptable ranges
- **Dependency Validation**: Ensures required fields are present for specific configurations
- **Logic Validation**: Validates that configuration combinations make sense

Invalid configurations are rejected and the system continues with the previous valid configuration.

## Configuration Persistence

Configuration changes are automatically saved to the global configuration file and persist across bot restarts. The configuration is stored in the `config/global/global_config.json` file under the `leveling_system` module.

## Default Configuration File

A default configuration is available at `config/defaults/leveling_system_default.json` and can be used as a reference or for resetting the configuration.

## Configuration Schema

The configuration schema is defined in `config/schemas/leveling_system.json` and provides:

- Field definitions and types
- Validation rules and constraints
- Default values
- Documentation for each setting

## Best Practices

1. **Test Changes**: Always test configuration changes in a development environment first
2. **Backup Configuration**: Keep backups of working configurations before making changes
3. **Monitor Performance**: Watch performance metrics after changing performance-related settings
4. **Gradual Changes**: Make incremental changes rather than large configuration overhauls
5. **Document Changes**: Keep track of configuration changes and their reasons

## Troubleshooting

### Configuration Not Loading
- Check that the configuration file exists and is valid JSON
- Verify that the bot has read/write permissions to the configuration directory
- Check the bot logs for configuration loading errors

### Changes Not Taking Effect
- Ensure the configuration was saved successfully (check return values)
- Try reloading the configuration with `/leveling_config reload`
- Check that the feature you're trying to configure is actually implemented

### Performance Issues
- Review performance-related settings like processing time limits
- Check if caching is enabled and properly configured
- Monitor the performance metrics to identify bottlenecks

### Validation Errors
- Check that numeric values are within acceptable ranges
- Ensure boolean values are true/false (not strings)
- Verify that required fields are present for complex configurations

## Examples

### Increase XP Rates for More Active Leveling
```
/leveling_config set xp_rates.message 2
/leveling_config set xp_rates.link 5
/leveling_config set xp_rates.thanks 8
```

### Enable Rate Limiting to Prevent XP Farming
```
/leveling_config toggle rate_limiting.enabled
/leveling_config set rate_limiting.max_xp_per_minute 15
```

### Disable Notifications Temporarily
```
/leveling_config toggle notifications.enabled
```

### Switch to Linear Level Progression
```
/leveling_config set level_formula.formula linear
/leveling_config set level_formula.linear_increment 150
```

### Optimize for High-Traffic Chats
```
/leveling_config set cache.user_stats_ttl 600
/leveling_config set performance.max_processing_time_ms 50
/leveling_config toggle performance.circuit_breaker_enabled
```

This configuration system provides flexible, runtime management of the leveling system while maintaining data integrity and system stability.