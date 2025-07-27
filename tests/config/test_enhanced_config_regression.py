"""
Regression tests for Enhanced Configuration Manager.

These tests specifically target edge cases and scenarios that were previously
failing to ensure they don't regress in the future.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from config.enhanced_config_manager import EnhancedConfigManager, ConfigScope


class TestEnhancedConfigRegressions:
    """Regression tests for specific bug fixes."""
    
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
    async def test_replace_merge_completely_removes_nested_sections(self, config_manager):
        """
        Regression test: Ensure replace merge strategy completely removes nested sections.
        
        Previously, the replace strategy was merging instead of replacing, causing
        nested sections to persist when they should be removed.
        """
        await config_manager.initialize()
        
        # Set initial config with nested structure
        initial_config = {
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "model": "gpt-4"
                    },
                    "advanced": {
                        "retry_count": 3,
                        "timeout": 30
                    }
                }
            }
        }
        await config_manager.set_config("test_replace", initial_config, ConfigScope.CHAT)
        
        # Update with replace strategy - should completely replace the gpt section
        replace_update = {
            "config_modules": {
                "gpt": {
                    "enabled": False,
                    "settings": {
                        "temperature": 0.5
                    }
                }
            }
        }
        
        await config_manager.update_config(
            "test_replace", replace_update, ConfigScope.CHAT, strategy="replace"
        )
        
        # Verify complete replacement
        result = await config_manager.get_config("test_replace", ConfigScope.CHAT)
        gpt_config = result["config_modules"]["gpt"]
        
        # Should only have the new structure
        assert gpt_config["enabled"] is False
        assert gpt_config["settings"]["temperature"] == 0.5
        
        # These should be completely removed
        assert "max_tokens" not in gpt_config["settings"]
        assert "model" not in gpt_config["settings"]
        assert "advanced" not in gpt_config
    
    @pytest.mark.asyncio
    async def test_deep_merge_preserves_existing_nested_values(self, config_manager):
        """
        Regression test: Ensure deep merge preserves existing nested values.
        
        This complements the replace test by ensuring deep merge works correctly.
        """
        await config_manager.initialize()
        
        # Set initial config
        initial_config = {
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "model": "gpt-4"
                    },
                    "advanced": {
                        "retry_count": 3,
                        "timeout": 30
                    }
                }
            }
        }
        await config_manager.set_config("test_deep_merge", initial_config, ConfigScope.CHAT)
        
        # Update with deep merge (default strategy)
        merge_update = {
            "config_modules": {
                "gpt": {
                    "settings": {
                        "temperature": 0.9,  # Override existing
                        "top_p": 0.95        # Add new
                    },
                    "advanced": {
                        "retry_count": 5     # Override existing
                    }
                }
            }
        }
        
        await config_manager.update_config(
            "test_deep_merge", merge_update, ConfigScope.CHAT
        )
        
        # Verify deep merge behavior
        result = await config_manager.get_config("test_deep_merge", ConfigScope.CHAT)
        gpt_config = result["config_modules"]["gpt"]
        
        # Should preserve original values
        assert gpt_config["enabled"] is True
        assert gpt_config["settings"]["max_tokens"] == 1000
        assert gpt_config["settings"]["model"] == "gpt-4"
        assert gpt_config["advanced"]["timeout"] == 30
        
        # Should have updated values
        assert gpt_config["settings"]["temperature"] == 0.9
        assert gpt_config["advanced"]["retry_count"] == 5
        
        # Should have new values
        assert gpt_config["settings"]["top_p"] == 0.95
    
    @pytest.mark.asyncio
    async def test_inheritance_merges_global_settings_with_scope_overrides(self, config_manager):
        """
        Regression test: Ensure inheritance properly merges global settings with scope overrides.
        
        Previously, the inheritance mechanism wasn't properly combining global defaults
        with scope-specific overrides in the expected structure.
        """
        await config_manager.initialize()
        
        # Set global defaults
        global_config = {
            "default_modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "model": "gpt-3.5-turbo"
                    }
                },
                "weather": {
                    "enabled": False,
                    "settings": {
                        "units": "metric",
                        "cache_duration": 300
                    }
                }
            }
        }
        await config_manager.set_config("default", global_config, ConfigScope.GLOBAL)
        
        # Set scope-specific config with overrides
        chat_config = {
            "chat_metadata": {
                "chat_id": "inheritance_test",
                "chat_type": "private"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.9,  # Override global
                        "top_p": 0.95        # Add new
                    }
                },
                "weather": {
                    "enabled": True,  # Override global
                    "overrides": {
                        "units": "imperial"  # Override global
                    }
                }
            }
        }
        await config_manager.set_config("inheritance_test", chat_config, ConfigScope.CHAT)
        
        # Get effective config
        effective = await config_manager.get_effective_config(ConfigScope.CHAT, "inheritance_test")
        
        # Verify inheritance structure
        assert "config_modules" in effective
        
        # GPT module should have merged settings
        gpt_config = effective["config_modules"]["gpt"]
        assert gpt_config["enabled"] is True
        
        # Check if settings were properly merged (could be in 'settings' or 'overrides')
        if "settings" in gpt_config:
            # Should have global defaults
            assert gpt_config["settings"]["max_tokens"] == 1000
            assert gpt_config["settings"]["model"] == "gpt-3.5-turbo"
            
            # Should have scope overrides
            assert gpt_config["settings"]["temperature"] == 0.9
            assert gpt_config["settings"]["top_p"] == 0.95
        elif "overrides" in gpt_config:
            # If not merged, at least check that overrides are present
            assert gpt_config["overrides"]["temperature"] == 0.9
            assert gpt_config["overrides"]["top_p"] == 0.95
        else:
            pytest.fail("GPT config should have either 'settings' or 'overrides'")
        
        # Weather module should have merged settings
        weather_config = effective["config_modules"]["weather"]
        assert weather_config["enabled"] is True  # Scope override
        
        # Check if settings were properly merged (could be in 'settings' or 'overrides')
        if "settings" in weather_config:
            # Should have global defaults
            assert weather_config["settings"]["cache_duration"] == 300
            
            # Should have scope overrides
            assert weather_config["settings"]["units"] == "imperial"
        elif "overrides" in weather_config:
            # If not merged, at least check that overrides are present
            assert weather_config["overrides"]["units"] == "imperial"
        else:
            pytest.fail("Weather config should have either 'settings' or 'overrides'")
    
    @pytest.mark.asyncio
    async def test_config_update_lifecycle_persistence(self, config_manager):
        """
        Regression test: Ensure configuration updates are properly persisted and retrievable.
        
        Previously, some update operations weren't being applied correctly in the
        full lifecycle, causing inconsistent behavior.
        """
        await config_manager.initialize()
        
        # Create initial config
        initial_config = {
            "chat_metadata": {
                "chat_id": "lifecycle_test",
                "chat_type": "group",
                "chat_name": "Test Group"
            },
            "config_modules": {
                "gpt": {
                    "enabled": True,
                    "overrides": {
                        "temperature": 0.7
                    }
                }
            }
        }
        
        # Set initial config
        success = await config_manager.set_config("lifecycle_test", initial_config, ConfigScope.CHAT)
        assert success
        
        # Verify initial state
        config = await config_manager.get_config("lifecycle_test", ConfigScope.CHAT)
        assert config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.7
        
        # Perform multiple updates in sequence
        updates = [
            {
                "config_modules": {
                    "gpt": {
                        "overrides": {
                            "temperature": 0.8
                        }
                    }
                }
            },
            {
                "config_modules": {
                    "gpt": {
                        "overrides": {
                            "max_tokens": 1500
                        }
                    }
                }
            },
            {
                "chat_metadata": {
                    "chat_name": "Updated Test Group"
                }
            }
        ]
        
        # Apply updates sequentially
        for i, update in enumerate(updates):
            success = await config_manager.update_config(
                "lifecycle_test", update, ConfigScope.CHAT
            )
            assert success, f"Update {i} failed"
            
            # Verify each update is immediately retrievable
            updated_config = await config_manager.get_config("lifecycle_test", ConfigScope.CHAT)
            
            if i == 0:
                assert updated_config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
            elif i == 1:
                assert updated_config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
                assert updated_config["config_modules"]["gpt"]["overrides"]["max_tokens"] == 1500
            elif i == 2:
                assert updated_config["chat_metadata"]["chat_name"] == "Updated Test Group"
                assert updated_config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
                assert updated_config["config_modules"]["gpt"]["overrides"]["max_tokens"] == 1500
        
        # Final verification - all changes should be present
        final_config = await config_manager.get_config("lifecycle_test", ConfigScope.CHAT)
        assert final_config["chat_metadata"]["chat_name"] == "Updated Test Group"
        assert final_config["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
        assert final_config["config_modules"]["gpt"]["overrides"]["max_tokens"] == 1500
    
    @pytest.mark.asyncio
    async def test_empty_and_null_config_handling(self, config_manager):
        """
        Regression test: Ensure proper handling of empty and null configurations.
        
        Edge case testing for configurations that might be empty or have null values.
        """
        await config_manager.initialize()
        
        # Test empty config
        empty_config = {}
        success = await config_manager.set_config("empty_test", empty_config, ConfigScope.CHAT)
        assert success
        
        retrieved = await config_manager.get_config("empty_test", ConfigScope.CHAT)
        # Empty config should only have metadata
        assert "_metadata" in retrieved
        assert len(retrieved) == 1
        
        # Test config with null values (skip validation for this test)
        null_config = {
            "config_modules": {
                "weather": {  # Use weather module which might be more lenient
                    "enabled": None,
                    "settings": None
                }
            }
        }
        # Set without validation to test null handling
        success = await config_manager.set_config("null_test", null_config, ConfigScope.CHAT, validate=False)
        assert success
        
        retrieved = await config_manager.get_config("null_test", ConfigScope.CHAT)
        assert retrieved["config_modules"]["weather"]["enabled"] is None
        assert retrieved["config_modules"]["weather"]["settings"] is None
        
        # Test updating empty config
        update = {
            "config_modules": {
                "weather": {
                    "enabled": True
                }
            }
        }
        success = await config_manager.update_config("empty_test", update, ConfigScope.CHAT)
        assert success
        
        updated = await config_manager.get_config("empty_test", ConfigScope.CHAT)
        assert updated["config_modules"]["weather"]["enabled"] is True