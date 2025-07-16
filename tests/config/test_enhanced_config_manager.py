"""
Unit tests for the enhanced configuration manager.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from config.enhanced_config_manager import (
    EnhancedConfigManager, ConfigScope, ConfigValidationError,
    ConfigMergeStrategy, ConfigChangeEvent, ConfigValidator
)


class TestConfigScope:
    """Test cases for ConfigScope enum."""
    
    def test_config_scope_values(self):
        """Test ConfigScope enum values."""
        assert ConfigScope.GLOBAL.value == "global"
        assert ConfigScope.CHAT.value == "chat"
        assert ConfigScope.USER.value == "user"
        assert ConfigScope.MODULE.value == "module"


class TestConfigValidator:
    """Test cases for ConfigValidator."""
    
    def test_validate_chat_config_valid(self):
        """Test validation of valid chat configuration."""
        config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private",
                "chat_name": "Test Chat"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate_chat_config(config)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_chat_config_missing_metadata(self):
        """Test validation with missing chat metadata."""
        config = {
            "config_modules": {
                "gpt": {"enabled": True}
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate_chat_config(config)
        
        assert not result.is_valid
        assert "chat_metadata" in str(result.errors[0])
    
    def test_validate_chat_config_invalid_module(self):
        """Test validation with invalid module configuration."""
        config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            },
            "config_modules": {
                "gpt": {
                    "enabled": "not_boolean"  # Should be boolean
                }
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate_chat_config(config)
        
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_validate_global_config_valid(self):
        """Test validation of valid global configuration."""
        config = {
            "system_settings": {
                "debug_mode": False,
                "log_level": "INFO"
            },
            "default_modules": {
                "gpt": {
                    "enabled": True,
                    "default_model": "gpt-4"
                }
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate_global_config(config)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_module_config_valid(self):
        """Test validation of valid module configuration."""
        config = {
            "enabled": True,
            "settings": {
                "api_key": "test_key",
                "timeout": 30
            },
            "overrides": {
                "temperature": 0.8
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate_module_config("gpt", config)
        
        assert result.is_valid
        assert len(result.errors) == 0


class TestEnhancedConfigManager:
    """Test cases for EnhancedConfigManager."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary configuration directory."""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir(parents=True)
        
        # Create subdirectories
        (config_dir / "global").mkdir()
        (config_dir / "private").mkdir()
        (config_dir / "group").mkdir()
        (config_dir / "modules").mkdir()
        (config_dir / "backups").mkdir()
        
        yield config_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create an EnhancedConfigManager instance."""
        manager = EnhancedConfigManager(base_path=temp_config_dir.parent)
        return manager
    
    @pytest.mark.asyncio
    async def test_initialization(self, config_manager):
        """Test configuration manager initialization."""
        await config_manager.initialize()
        
        assert config_manager._initialized
        assert config_manager._validator is not None
        assert config_manager._cache is not None
    
    @pytest.mark.asyncio
    async def test_get_config_not_found(self, config_manager):
        """Test getting configuration that doesn't exist."""
        await config_manager.initialize()
        
        config = await config_manager.get_config(ConfigScope.CHAT, "nonexistent")
        assert config == {}
    
    @pytest.mark.asyncio
    async def test_set_and_get_config(self, config_manager, temp_config_dir):
        """Test setting and getting configuration."""
        await config_manager.initialize()
        
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private",
                "chat_name": "Test Chat"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {"temperature": 0.7}
                }
            }
        }
        
        # Set configuration
        success = await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        assert success
        
        # Get configuration
        retrieved_config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert retrieved_config["chat_metadata"]["chat_id"] == "123"
        assert retrieved_config["config_modules"]["gpt"]["enabled"] is True
    
    @pytest.mark.asyncio
    async def test_update_config(self, config_manager):
        """Test updating existing configuration."""
        await config_manager.initialize()
        
        # Set initial config
        initial_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            },
            "config_modules": {
                "gpt": {"enabled": True}
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", initial_config)
        
        # Update config
        updates = {
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {"temperature": 0.8}
                }
            }
        }
        
        success = await config_manager.update_config(
            ConfigScope.CHAT, "123", updates, ConfigMergeStrategy.DEEP_MERGE
        )
        assert success
        
        # Verify update
        updated_config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert updated_config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
    
    @pytest.mark.asyncio
    async def test_delete_config(self, config_manager):
        """Test deleting configuration."""
        await config_manager.initialize()
        
        # Set config
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        
        # Verify it exists
        config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert config != {}
        
        # Delete config
        success = await config_manager.delete_config(ConfigScope.CHAT, "123")
        assert success
        
        # Verify it's gone
        config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert config == {}
    
    @pytest.mark.asyncio
    async def test_list_configs(self, config_manager):
        """Test listing configurations."""
        await config_manager.initialize()
        
        # Set multiple configs
        for i in range(3):
            config = {
                "chat_metadata": {
                    "chat_id": str(i),
                    "chat_type": "private"
                }
            }
            await config_manager.set_config(ConfigScope.CHAT, str(i), config)
        
        # List configs
        config_list = await config_manager.list_configs(ConfigScope.CHAT)
        assert len(config_list) == 3
        assert all(str(i) in config_list for i in range(3))
    
    @pytest.mark.asyncio
    async def test_backup_and_restore(self, config_manager):
        """Test configuration backup and restore."""
        await config_manager.initialize()
        
        # Set config
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            },
            "config_modules": {
                "gpt": {"enabled": True}
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        
        # Create backup
        backup_id = await config_manager.create_backup(ConfigScope.CHAT, "123")
        assert backup_id is not None
        
        # Modify config
        modified_config = test_config.copy()
        modified_config["config_modules"]["gpt"]["enabled"] = False
        await config_manager.set_config(ConfigScope.CHAT, "123", modified_config)
        
        # Verify modification
        current_config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert current_config["config_modules"]["gpt"]["enabled"] is False
        
        # Restore from backup
        success = await config_manager.restore_backup(backup_id)
        assert success
        
        # Verify restoration
        restored_config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert restored_config["config_modules"]["gpt"]["enabled"] is True
    
    @pytest.mark.asyncio
    async def test_config_validation_on_set(self, config_manager):
        """Test that configuration is validated when set."""
        await config_manager.initialize()
        
        # Try to set invalid config
        invalid_config = {
            "config_modules": {
                "gpt": {
                    "enabled": "not_boolean"  # Should be boolean
                }
            }
        }
        
        success = await config_manager.set_config(ConfigScope.CHAT, "123", invalid_config)
        assert not success
    
    @pytest.mark.asyncio
    async def test_config_caching(self, config_manager):
        """Test configuration caching."""
        await config_manager.initialize()
        
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            }
        }
        
        # Set config
        await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        
        # Get config (should be cached)
        config1 = await config_manager.get_config(ConfigScope.CHAT, "123")
        config2 = await config_manager.get_config(ConfigScope.CHAT, "123")
        
        # Both should be the same (from cache)
        assert config1 == config2
    
    @pytest.mark.asyncio
    async def test_config_change_events(self, config_manager):
        """Test configuration change event emission."""
        await config_manager.initialize()
        
        events_received = []
        
        def event_handler(event: ConfigChangeEvent):
            events_received.append(event)
        
        # Subscribe to events
        config_manager.subscribe_to_changes(event_handler)
        
        # Set config (should trigger event)
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        
        # Verify event was received
        assert len(events_received) == 1
        event = events_received[0]
        assert event.scope == ConfigScope.CHAT
        assert event.config_id == "123"
        assert event.change_type == "set"
    
    @pytest.mark.asyncio
    async def test_merge_strategies(self, config_manager):
        """Test different configuration merge strategies."""
        await config_manager.initialize()
        
        # Set initial config
        initial_config = {
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", initial_config)
        
        # Test REPLACE strategy
        replace_updates = {
            "config_modules": {
                "gpt": {
                    "enabled": False
                }
            }
        }
        
        await config_manager.update_config(
            ConfigScope.CHAT, "123", replace_updates, ConfigMergeStrategy.REPLACE
        )
        
        config = await config_manager.get_config(ConfigScope.CHAT, "123")
        # With REPLACE, settings should be gone
        assert "settings" not in config["config_modules"]["gpt"]
        
        # Reset and test DEEP_MERGE strategy
        await config_manager.set_config(ConfigScope.CHAT, "123", initial_config)
        
        deep_merge_updates = {
            "config_modules": {
                "gpt": {
                    "settings": {
                        "temperature": 0.8  # Should merge with existing settings
                    }
                }
            }
        }
        
        await config_manager.update_config(
            ConfigScope.CHAT, "123", deep_merge_updates, ConfigMergeStrategy.DEEP_MERGE
        )
        
        config = await config_manager.get_config(ConfigScope.CHAT, "123")
        # With DEEP_MERGE, both settings should exist
        assert config["config_modules"]["gpt"]["settings"]["temperature"] == 0.8
        assert config["config_modules"]["gpt"]["settings"]["max_tokens"] == 1000
    
    @pytest.mark.asyncio
    async def test_config_inheritance(self, config_manager):
        """Test configuration inheritance between scopes."""
        await config_manager.initialize()
        
        # Set global config
        global_config = {
            "default_modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            }
        }
        await config_manager.set_config(ConfigScope.GLOBAL, "default", global_config)
        
        # Set chat config that overrides some settings
        chat_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.9  # Override global setting
                    }
                }
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", chat_config)
        
        # Get effective config (should inherit from global)
        effective_config = await config_manager.get_effective_config(ConfigScope.CHAT, "123")
        
        # Should have global max_tokens and chat temperature
        gpt_config = effective_config["config_modules"]["gpt"]
        assert gpt_config["settings"]["temperature"] == 0.9  # From chat override
        assert gpt_config["settings"]["max_tokens"] == 1000  # From global default
    
    @pytest.mark.asyncio
    async def test_config_hot_reload(self, config_manager):
        """Test configuration hot reloading."""
        await config_manager.initialize()
        
        # Enable hot reload
        config_manager.enable_hot_reload(interval=0.1)
        
        # Set initial config
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            }
        }
        await config_manager.set_config(ConfigScope.CHAT, "123", test_config)
        
        # Simulate external file change
        config_file = config_manager._get_config_file_path(ConfigScope.CHAT, "123")
        modified_config = test_config.copy()
        modified_config["chat_metadata"]["chat_name"] = "Modified Chat"
        
        with open(config_file, 'w') as f:
            json.dump(modified_config, f, indent=2)
        
        # Wait for hot reload
        await asyncio.sleep(0.2)
        
        # Get config (should be reloaded)
        reloaded_config = await config_manager.get_config(ConfigScope.CHAT, "123")
        assert reloaded_config["chat_metadata"]["chat_name"] == "Modified Chat"
        
        # Disable hot reload
        config_manager.disable_hot_reload()
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, config_manager):
        """Test concurrent configuration access."""
        await config_manager.initialize()
        
        async def set_config_task(config_id: str):
            config = {
                "chat_metadata": {
                    "chat_id": config_id,
                    "chat_type": "private"
                }
            }
            return await config_manager.set_config(ConfigScope.CHAT, config_id, config)
        
        async def get_config_task(config_id: str):
            return await config_manager.get_config(ConfigScope.CHAT, config_id)
        
        # Run concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(set_config_task(str(i)))
            tasks.append(get_config_task(str(i)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should not have any exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
    
    @pytest.mark.asyncio
    async def test_config_migration(self, config_manager):
        """Test configuration migration between versions."""
        await config_manager.initialize()
        
        # Set old format config
        old_config = {
            "chat_id": "123",  # Old format
            "gpt_enabled": True,
            "gpt_temperature": 0.7
        }
        
        # Simulate migration
        migrated = await config_manager.migrate_config(old_config, from_version="1.0", to_version="2.0")
        
        # Should be converted to new format
        assert "chat_metadata" in migrated
        assert migrated["chat_metadata"]["chat_id"] == "123"
        assert "config_modules" in migrated
        assert migrated["config_modules"]["gpt"]["enabled"] is True
        assert migrated["config_modules"]["gpt"]["overrides"]["temperature"] == 0.7


class TestConfigChangeEvent:
    """Test cases for ConfigChangeEvent."""
    
    def test_config_change_event_creation(self):
        """Test ConfigChangeEvent creation."""
        event = ConfigChangeEvent(
            scope=ConfigScope.CHAT,
            config_id="123",
            change_type="set",
            old_config={"old": "value"},
            new_config={"new": "value"},
            timestamp=datetime.now()
        )
        
        assert event.scope == ConfigScope.CHAT
        assert event.config_id == "123"
        assert event.change_type == "set"
        assert event.old_config == {"old": "value"}
        assert event.new_config == {"new": "value"}
        assert isinstance(event.timestamp, datetime)


class TestConfigMergeStrategy:
    """Test cases for ConfigMergeStrategy enum."""
    
    def test_merge_strategy_values(self):
        """Test ConfigMergeStrategy enum values."""
        assert ConfigMergeStrategy.REPLACE.value == "replace"
        assert ConfigMergeStrategy.SHALLOW_MERGE.value == "shallow_merge"
        assert ConfigMergeStrategy.DEEP_MERGE.value == "deep_merge"


class TestConfigIntegration:
    """Integration tests for configuration management."""
    
    @pytest.mark.asyncio
    async def test_full_config_lifecycle(self, temp_config_dir):
        """Test complete configuration lifecycle."""
        manager = EnhancedConfigManager(base_path=temp_config_dir.parent)
        await manager.initialize()
        
        # Create config
        config = {
            "chat_metadata": {
                "chat_id": "integration_test",
                "chat_type": "private",
                "chat_name": "Integration Test Chat"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.7,
                        "max_tokens": 1500
                    }
                },
                "weather": {
                    "enabled": False
                }
            }
        }
        
        # Set config
        success = await manager.set_config(ConfigScope.CHAT, "integration_test", config)
        assert success
        
        # Get and verify
        retrieved = await manager.get_config(ConfigScope.CHAT, "integration_test")
        assert retrieved["chat_metadata"]["chat_name"] == "Integration Test Chat"
        assert retrieved["config_modules"]["gpt"]["enabled"] is True
        
        # Update config
        updates = {
            "config_modules": {
                "gpt": {
                    "overrides": {
                        "temperature": 0.9
                    }
                },
                "weather": {
                    "enabled": True
                }
            }
        }
        
        success = await manager.update_config(
            ConfigScope.CHAT, "integration_test", updates, ConfigMergeStrategy.DEEP_MERGE
        )
        assert success
        
        # Verify updates
        updated = await manager.get_config(ConfigScope.CHAT, "integration_test")
        assert updated["config_modules"]["gpt"]["overrides"]["temperature"] == 0.9
        assert updated["config_modules"]["gpt"]["overrides"]["max_tokens"] == 1500  # Preserved
        assert updated["config_modules"]["weather"]["enabled"] is True
        
        # Create backup
        backup_id = await manager.create_backup(ConfigScope.CHAT, "integration_test")
        assert backup_id is not None
        
        # Delete config
        success = await manager.delete_config(ConfigScope.CHAT, "integration_test")
        assert success
        
        # Verify deletion
        deleted = await manager.get_config(ConfigScope.CHAT, "integration_test")
        assert deleted == {}
        
        # Restore from backup
        success = await manager.restore_backup(backup_id)
        assert success
        
        # Verify restoration
        restored = await manager.get_config(ConfigScope.CHAT, "integration_test")
        assert restored["config_modules"]["gpt"]["overrides"]["temperature"] == 0.9
        
        await manager.shutdown()