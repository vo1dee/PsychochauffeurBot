"""
Unit tests for the enhanced configuration manager.
"""

import pytest
import json
import tempfile
import shutil
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from config.enhanced_config_manager import (
    EnhancedConfigManager, ConfigScope, ConfigValidationError,
    ConfigSchema, ConfigMetadata, ConfigEntry
)


class TestConfigScope:
    """Test cases for ConfigScope enum."""
    
    def test_config_scope_values(self):
        """Test ConfigScope enum values."""
        assert ConfigScope.GLOBAL.value == "global"
        assert ConfigScope.CHAT.value == "chat"
        assert ConfigScope.USER.value == "user"
        assert ConfigScope.MODULE.value == "module"



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
        # Test that initialization completes without error
        await config_manager.initialize()
        
        # Test that we can call basic methods without error
        config = await config_manager.get_config("test", ConfigScope.GLOBAL)
        # Config can be None for non-existent keys, which is expected
        assert True  # If we get here, initialization worked
    
    @pytest.mark.asyncio
    async def test_get_config_not_found(self, config_manager):
        """Test getting configuration that doesn't exist."""
        await config_manager.initialize()
        
        config = await config_manager.get_config("nonexistent", ConfigScope.CHAT)
        assert config is None
    
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
        success = await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        assert success
        
        # Get configuration
        retrieved_config = await config_manager.get_config("123", ConfigScope.CHAT)
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
        await config_manager.set_config("123", initial_config, ConfigScope.CHAT)
        
        # Update config
        updates = {
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {"temperature": 0.8}
                }
            }
        }
        
        success = await config_manager.set_config("123", updates, ConfigScope.CHAT)
        assert success
        
        # Verify update
        updated_config = await config_manager.get_config("123", ConfigScope.CHAT)
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
        await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        
        # Verify it exists
        config = await config_manager.get_config("123", ConfigScope.CHAT)
        assert config != {}
        
        # Delete config
        success = await config_manager.delete_config("123", ConfigScope.CHAT)
        assert success
        
        # Verify it's gone
        config = await config_manager.get_config("123", ConfigScope.CHAT)
        assert config is None
    
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
            await config_manager.set_config(str(i), config, ConfigScope.CHAT)
        
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
        await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        
        # Create backup
        backup_id = await config_manager.create_backup(ConfigScope.CHAT, "123")
        assert backup_id is not None
        
        # Modify config
        modified_config = test_config.copy()
        modified_config["config_modules"]["gpt"]["enabled"] = False
        await config_manager.set_config("123", modified_config, ConfigScope.CHAT)
        
        # Verify modification
        current_config = await config_manager.get_config("123", ConfigScope.CHAT)
        assert current_config["config_modules"]["gpt"]["enabled"] is False
        
        # Restore from backup
        success = await config_manager.restore_backup(backup_id)
        assert success
        
        # Verify restoration
        restored_config = await config_manager.get_config("123", ConfigScope.CHAT)
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
        
        success = await config_manager.set_config("123", invalid_config, ConfigScope.CHAT)
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
        await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        
        # Get config (should be cached)
        config1 = await config_manager.get_config("123", ConfigScope.CHAT)
        config2 = await config_manager.get_config("123", ConfigScope.CHAT)
        
        # Both should be the same (from cache)
        assert config1 == config2
    
    @pytest.mark.asyncio
    async def test_config_change_events(self, config_manager):
        """Test configuration change event emission."""
        await config_manager.initialize()
        
        events_received = []
        
        def event_handler(event):
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
        await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        
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
        await config_manager.set_config("123", initial_config, ConfigScope.CHAT)
        
        # Test REPLACE strategy
        replace_updates = {
            "config_modules": {
                "gpt": {
                    "enabled": False
                }
            }
        }
        
        await config_manager.update_config(
            "123", replace_updates, ConfigScope.CHAT, strategy="replace"
        )
        
        config = await config_manager.get_config("123", ConfigScope.CHAT)
        # With REPLACE, settings should be gone
        assert "settings" not in config["config_modules"]["gpt"]
        
        # Reset and test DEEP_MERGE strategy
        await config_manager.set_config("123", initial_config, ConfigScope.CHAT)
        
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
            "123", deep_merge_updates, ConfigScope.CHAT
        )
        
        config = await config_manager.get_config("123", ConfigScope.CHAT)
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
        await config_manager.set_config("default", global_config, ConfigScope.GLOBAL)
        
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
        await config_manager.set_config("123", chat_config, ConfigScope.CHAT)
        
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
        config_manager.enable_hot_reload = True
        
        # Set initial config
        test_config = {
            "chat_metadata": {
                "chat_id": "123",
                "chat_type": "private"
            }
        }
        await config_manager.set_config("123", test_config, ConfigScope.CHAT)
        
        # Simulate external file change
        config_file = config_manager._get_config_file_path(ConfigScope.CHAT, "123")
        modified_config = test_config.copy()
        modified_config["chat_metadata"]["chat_name"] = "Modified Chat"
        
        with open(config_file, 'w') as f:
            json.dump(modified_config, f, indent=2)
        
        # Wait for hot reload
        await asyncio.sleep(0.2)
        
        # Get config (should be reloaded)
        reloaded_config = await config_manager.get_config("123", ConfigScope.CHAT)
        assert reloaded_config["chat_metadata"]["chat_name"] == "Modified Chat"
        
        # Disable hot reload
        config_manager.enable_hot_reload = False
    
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
            return await config_manager.set_config(config_id, config, ConfigScope.CHAT)
        
        async def get_config_task(config_id: str):
            return await config_manager.get_config(config_id, ConfigScope.CHAT)
        
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
        success = await manager.set_config("integration_test", config, ConfigScope.CHAT)
        assert success
        
        # Get and verify
        retrieved = await manager.get_config("integration_test", ConfigScope.CHAT)
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
            "integration_test", updates, ConfigScope.CHAT
        )
        assert success
        
        # Verify updates
        updated = await manager.get_config("integration_test", ConfigScope.CHAT)
        assert updated["config_modules"]["gpt"]["overrides"]["temperature"] == 0.9
        assert updated["config_modules"]["gpt"]["overrides"]["max_tokens"] == 1500  # Preserved
        assert updated["config_modules"]["weather"]["enabled"] is True
        
        # Create backup
        backup_id = await manager.create_backup(ConfigScope.CHAT, "integration_test")
        assert backup_id is not None
        
        # Delete config
        success = await manager.delete_config("integration_test", ConfigScope.CHAT)
        assert success
        
        # Verify deletion
        deleted = await manager.get_config("integration_test", ConfigScope.CHAT)
        assert deleted is None
        
        # Restore from backup
        success = await manager.restore_backup(backup_id)
        assert success
        
        # Verify restoration
        restored = await manager.get_config("integration_test", ConfigScope.CHAT)
        assert restored["config_modules"]["gpt"]["overrides"]["temperature"] == 0.9
        
        await manager.shutdown()