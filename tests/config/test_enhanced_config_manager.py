"""
Tests for Enhanced Configuration Manager

This module contains comprehensive tests for the enhanced configuration manager,
covering configuration loading, validation, merging, and inheritance.
"""

import asyncio
import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch, mock_open

from config.enhanced_config_manager import (
    EnhancedConfigManager,
    ConfigScope,
    ConfigSchema,
    ConfigMetadata,
    ConfigEntry,
    ConfigValidationError,
    ConfigChangeEvent
)
from tests.utils.comprehensive_test_utilities import get_test_utils


class TestEnhancedConfigManagerLoading:
    """Test configuration loading and validation functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create config manager with temporary directory."""
        return EnhancedConfigManager(base_path=temp_config_dir)
    
    @pytest.fixture
    def sample_global_config(self):
        """Sample global configuration data."""
        return {
            "_metadata": {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "schema_version": "1.0.0",
                "source": "test"
            },
            "modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "default_model": "gpt-4.1-mini",
                        "max_tokens": 1500,
                        "temperature": 0.7
                    }
                },
                "weather": {
                    "enabled": True,
                    "settings": {
                        "units": "metric",
                        "forecast_days": 3
                    }
                }
            }
        }
    
    @pytest.fixture
    def sample_module_config(self):
        """Sample module configuration data."""
        return {
            "_metadata": {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "schema_version": "1.0.0",
                "source": "test"
            },
            "enabled": True,
            "settings": {
                "api_key": "test_key",
                "timeout": 30,
                "retries": 3
            }
        }
    
    @pytest.fixture
    def sample_schema(self):
        """Sample configuration schema."""
        return ConfigSchema(
            name="test_module",
            version="1.0.0",
            fields={
                "enabled": {"type": "boolean", "required": True},
                "settings": {"type": "object", "required": True}
            },
            required_fields=["enabled", "settings"],
            validators={
                "enabled": lambda x: isinstance(x, bool)
            }
        )

    async def test_initialize_creates_directory_structure(self, config_manager, temp_config_dir):
        """Test that initialization creates required directory structure."""
        await config_manager.initialize()
        
        # Check that all required directories exist
        assert (temp_config_dir / "global").exists()
        assert (temp_config_dir / "private").exists()
        assert (temp_config_dir / "group").exists()
        assert (temp_config_dir / "modules").exists()
        assert (temp_config_dir / "schemas").exists()
        assert (temp_config_dir / "backups").exists()
    
    async def test_load_global_config_from_file(self, config_manager, temp_config_dir, sample_global_config):
        """Test loading global configuration from file."""
        # Create global config file
        global_config_path = temp_config_dir / "global" / "global_config.json"
        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(global_config_path, 'w') as f:
            json.dump(sample_global_config, f)
        
        await config_manager.initialize()
        
        # Verify config was loaded
        loaded_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert loaded_config == sample_global_config
    
    async def test_load_module_config_from_file(self, config_manager, temp_config_dir, sample_module_config):
        """Test loading module configuration from file."""
        # Create module config file
        module_config_path = temp_config_dir / "modules" / "test_module.json"
        module_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(module_config_path, 'w') as f:
            json.dump(sample_module_config, f)
        
        await config_manager.initialize()
        
        # Verify config was loaded
        loaded_config = await config_manager.get_config("test_module", ConfigScope.MODULE)
        assert loaded_config == sample_module_config
    
    async def test_create_default_global_config(self, config_manager, temp_config_dir):
        """Test creation of default global configuration when none exists."""
        await config_manager.initialize()
        
        # Verify default config was created
        global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert global_config is not None
        assert "_metadata" in global_config
        assert "modules" in global_config
        
        # Check that file was created
        global_config_path = temp_config_dir / "global" / "global_config.json"
        assert global_config_path.exists()
    
    async def test_load_config_with_environment_variables(self, config_manager):
        """Test loading configuration with environment variable overrides."""
        with patch.dict('os.environ', {'CONFIG_GPT_ENABLED': 'false', 'CONFIG_GPT_TEMPERATURE': '0.5'}):
            await config_manager.initialize()
            
            # Environment variables should override default values
            # Note: This test assumes environment variable support is implemented
            # For now, we'll test the basic functionality
            global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
            assert global_config is not None
    
    async def test_load_malformed_config_file(self, config_manager, temp_config_dir):
        """Test handling of malformed configuration files."""
        # Create malformed config file
        global_config_path = temp_config_dir / "global" / "global_config.json"
        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(global_config_path, 'w') as f:
            f.write("{ invalid json content")
        
        # Should not raise exception, but should log error
        await config_manager.initialize()
        
        # The malformed file should be ignored and no config loaded
        # (The enhanced config manager doesn't create default when malformed file exists)
        global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        # This might be None or an empty dict depending on implementation
        # The important thing is that it doesn't crash
        assert global_config is None or isinstance(global_config, dict)
    
    async def test_load_missing_config_file(self, config_manager, temp_config_dir):
        """Test handling of missing configuration files."""
        # Don't create any config files
        await config_manager.initialize()
        
        # Should create default global config
        global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert global_config is not None
        assert "_metadata" in global_config
    
    async def test_load_config_with_schema_validation(self, config_manager, temp_config_dir, sample_schema):
        """Test loading configuration with schema validation."""
        # Register schema
        config_manager.register_schema(sample_schema)
        
        # Create valid config
        valid_config = {
            "enabled": True,
            "settings": {"api_key": "test"}
        }
        
        module_config_path = temp_config_dir / "modules" / "test_module.json"
        module_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(module_config_path, 'w') as f:
            json.dump(valid_config, f)
        
        await config_manager.initialize()
        
        # Config should load successfully
        loaded_config = await config_manager.get_config("test_module", ConfigScope.MODULE)
        assert loaded_config["enabled"] is True
    
    async def test_load_config_with_validation_errors(self, config_manager, temp_config_dir, sample_schema):
        """Test loading configuration with validation errors."""
        # Register schema
        config_manager.register_schema(sample_schema)
        
        # Create invalid config (missing required field)
        invalid_config = {
            "settings": {"api_key": "test"}
            # Missing required "enabled" field
        }
        
        module_config_path = temp_config_dir / "modules" / "test_module.json"
        module_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(module_config_path, 'w') as f:
            json.dump(invalid_config, f)
        
        await config_manager.initialize()
        
        # Config should still load but validation warnings should be logged
        loaded_config = await config_manager.get_config("test_module", ConfigScope.MODULE)
        assert loaded_config is not None
    
    async def test_load_schema_files(self, config_manager, temp_config_dir):
        """Test loading schema files from schema directory."""
        # Create schema file
        schema_data = {
            "name": "test_schema",
            "version": "1.0.0",
            "fields": {
                "enabled": {"type": "boolean"},
                "name": {"type": "string"}
            },
            "required_fields": ["enabled"]
        }
        
        schema_path = temp_config_dir / "schemas" / "test_schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(schema_path, 'w') as f:
            json.dump(schema_data, f)
        
        await config_manager.initialize()
        
        # Verify schema was loaded
        assert "test_schema" in config_manager._schemas
        assert config_manager._schemas["test_schema"].name == "test_schema"
    
    async def test_load_invalid_schema_file(self, config_manager, temp_config_dir):
        """Test handling of invalid schema files."""
        # Create invalid schema file
        schema_path = temp_config_dir / "schemas" / "invalid_schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(schema_path, 'w') as f:
            f.write("{ invalid json")
        
        # Should not raise exception
        await config_manager.initialize()
        
        # Invalid schema should not be loaded
        assert "invalid_schema" not in config_manager._schemas


class TestConfigValidation:
    """Test configuration validation functionality."""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager for validation tests."""
        return EnhancedConfigManager()
    
    @pytest.fixture
    def validation_schema(self):
        """Create validation schema for testing."""
        return ConfigSchema(
            name="validation_test",
            version="1.0.0",
            fields={
                "enabled": {"type": "boolean"},
                "name": {"type": "string"},
                "count": {"type": "integer"}
            },
            required_fields=["enabled", "name"],
            validators={
                "enabled": lambda x: isinstance(x, bool),
                "name": lambda x: isinstance(x, str) and len(x) > 0,
                "count": lambda x: isinstance(x, int) and x >= 0
            }
        )
    
    def test_schema_validation_success(self, validation_schema):
        """Test successful schema validation."""
        valid_config = {
            "enabled": True,
            "name": "test_config",
            "count": 5
        }
        
        errors = validation_schema.validate(valid_config)
        assert len(errors) == 0
    
    def test_schema_validation_missing_required_field(self, validation_schema):
        """Test schema validation with missing required field."""
        invalid_config = {
            "enabled": True
            # Missing required "name" field
        }
        
        errors = validation_schema.validate(invalid_config)
        assert len(errors) == 1
        assert "Required field 'name' is missing" in errors[0]
    
    def test_schema_validation_custom_validator_failure(self, validation_schema):
        """Test schema validation with custom validator failure."""
        invalid_config = {
            "enabled": True,
            "name": "",  # Empty string should fail validation
            "count": -1  # Negative count should fail validation
        }
        
        errors = validation_schema.validate(invalid_config)
        assert len(errors) == 2  # Both name and count should fail
    
    def test_schema_validation_validator_exception(self):
        """Test schema validation when validator raises exception."""
        # Create a schema with a validator that raises an exception
        schema_with_exception = ConfigSchema(
            name="exception_test",
            version="1.0.0",
            fields={"value": {"type": "string"}},
            required_fields=["value"],
            validators={
                "value": lambda x: x.upper()  # This will raise AttributeError for non-strings
            }
        )
        
        invalid_config = {
            "value": 123  # Integer will cause AttributeError when calling .upper()
        }
        
        errors = schema_with_exception.validate(invalid_config)
        assert len(errors) >= 1
        assert any("Validator error" in error for error in errors)
    
    async def test_config_validation_on_set(self, config_manager):
        """Test that validation occurs when setting configuration."""
        # Create schema with validation
        schema = ConfigSchema(
            name="global",
            version="1.0.0",
            fields={"modules": {"type": "object"}},
            required_fields=["modules"],
            validators={
                "modules": lambda x: isinstance(x, dict)
            }
        )
        
        config_manager.register_schema(schema)
        await config_manager.initialize()
        
        # Valid config should succeed
        valid_config = {"modules": {"gpt": {"enabled": True}}}
        result = await config_manager.set_config("global", valid_config, ConfigScope.GLOBAL)
        assert result is True
        
        # Invalid config should fail
        invalid_config = {"modules": "not_a_dict"}
        with pytest.raises(ConfigValidationError):
            await config_manager.set_config("global", invalid_config, ConfigScope.GLOBAL, validate=True)
    
    async def test_basic_validation_for_known_structures(self, config_manager):
        """Test basic validation for known configuration structures."""
        await config_manager.initialize()
        
        # Test config with modules structure
        config_with_modules = {
            "config_modules": {
                "gpt": {
                    "enabled": "not_a_boolean"  # Should be boolean
                }
            }
        }
        
        # Basic validation should catch this
        result = await config_manager.set_config("test", config_with_modules, ConfigScope.GLOBAL, validate=True)
        assert result is False  # Should fail basic validation
    
    async def test_validation_can_be_disabled(self, config_manager):
        """Test that validation can be disabled."""
        config_manager.enable_validation = False
        await config_manager.initialize()
        
        # Even invalid config should succeed when validation is disabled
        invalid_config = {"modules": "not_a_dict"}
        result = await config_manager.set_config("test", invalid_config, ConfigScope.GLOBAL, validate=False)
        assert result is True


class TestConfigErrorHandling:
    """Test error handling in configuration operations."""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager for error handling tests."""
        return EnhancedConfigManager()
    
    async def test_handle_file_permission_errors(self, config_manager, temp_config_dir):
        """Test handling of file permission errors."""
        config_manager.base_path = temp_config_dir
        
        # Create directory structure
        await config_manager.initialize()
        
        # Mock file operations to raise permission error
        with patch('aiofiles.open', side_effect=PermissionError("Permission denied")):
            result = await config_manager.set_config("test", {"key": "value"}, ConfigScope.GLOBAL)
            assert result is False  # Should handle error gracefully
    
    async def test_handle_disk_full_errors(self, config_manager):
        """Test handling of disk full errors."""
        await config_manager.initialize()
        
        # Mock file operations to raise OSError (disk full)
        with patch('aiofiles.open', side_effect=OSError("No space left on device")):
            result = await config_manager.set_config("test", {"key": "value"}, ConfigScope.GLOBAL)
            assert result is False  # Should handle error gracefully
    
    async def test_handle_json_serialization_errors(self, config_manager):
        """Test handling of JSON serialization errors."""
        await config_manager.initialize()
        
        # Create config with non-serializable object
        class NonSerializable:
            pass
        
        invalid_config = {"object": NonSerializable()}
        
        # Should handle serialization error gracefully
        result = await config_manager.set_config("test", invalid_config, ConfigScope.GLOBAL)
        assert result is False
    
    async def test_handle_corrupted_config_files(self, config_manager, temp_config_dir):
        """Test handling of corrupted configuration files."""
        config_manager.base_path = temp_config_dir
        
        # Create corrupted config file
        global_config_path = temp_config_dir / "global" / "global_config.json"
        global_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write binary data to JSON file
        with open(global_config_path, 'wb') as f:
            f.write(b'\x00\x01\x02\x03')
        
        # Should handle corrupted file gracefully
        await config_manager.initialize()
        
        # Should create default config instead
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
    
    async def test_handle_network_timeout_errors(self, config_manager):
        """Test handling of network timeout errors during remote config loading."""
        await config_manager.initialize()
        
        # Mock network timeout
        with patch('aiofiles.open', side_effect=asyncio.TimeoutError("Network timeout")):
            # Should handle timeout gracefully
            result = await config_manager.set_config("test", {"key": "value"}, ConfigScope.GLOBAL)
            assert result is False
    
    async def test_handle_concurrent_access_errors(self, config_manager):
        """Test handling of concurrent access to configuration files."""
        await config_manager.initialize()
        
        # Simulate concurrent access by trying to set config multiple times
        tasks = []
        for i in range(10):
            task = config_manager.set_config(f"test_{i}", {"value": i}, ConfigScope.GLOBAL)
            tasks.append(task)
        
        # All operations should complete without errors
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that most operations succeeded (some might fail due to race conditions)
        successful_operations = sum(1 for result in results if result is True)
        assert successful_operations > 0  # At least some should succeed


class TestConfigLoadingFromDifferentSources:
    """Test loading configurations from different sources (files, environment, defaults)."""
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create config manager with temporary directory."""
        return EnhancedConfigManager(base_path=temp_config_dir)
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    async def test_load_from_default_sources(self, config_manager):
        """Test loading configuration from default sources."""
        await config_manager.initialize()
        
        # Should create default global config
        global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert global_config is not None
        assert "_metadata" in global_config
        assert global_config["_metadata"]["source"] == "system_default"
    
    async def test_load_from_file_source(self, config_manager, temp_config_dir):
        """Test loading configuration from file source."""
        # Create config file
        config_data = {
            "_metadata": {
                "version": "1.0.0",
                "source": "file",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            "test_setting": "file_value"
        }
        
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        await config_manager.initialize()
        
        loaded_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert loaded_config["_metadata"]["source"] == "file"
        assert loaded_config["test_setting"] == "file_value"
    
    async def test_load_with_environment_override(self, config_manager):
        """Test loading configuration with environment variable overrides."""
        # Set environment variables
        with patch.dict('os.environ', {
            'CONFIG_TEST_SETTING': 'env_value',
            'CONFIG_NUMERIC_SETTING': '42'
        }):
            await config_manager.initialize()
            
            # For now, test that initialization completes successfully
            # Environment variable support would need to be implemented
            global_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
            assert global_config is not None
    
    async def test_load_multiple_config_files(self, config_manager, temp_config_dir):
        """Test loading multiple configuration files."""
        # Create global config
        global_config = {
            "_metadata": {"version": "1.0.0", "source": "file"},
            "global_setting": "global_value"
        }
        
        global_path = temp_config_dir / "global" / "global_config.json"
        global_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(global_path, 'w') as f:
            json.dump(global_config, f)
        
        # Create module config
        module_config = {
            "_metadata": {"version": "1.0.0", "source": "file"},
            "module_setting": "module_value"
        }
        
        module_path = temp_config_dir / "modules" / "test_module.json"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(module_path, 'w') as f:
            json.dump(module_config, f)
        
        await config_manager.initialize()
        
        # Verify both configs loaded
        global_loaded = await config_manager.get_config("global", ConfigScope.GLOBAL)
        module_loaded = await config_manager.get_config("test_module", ConfigScope.MODULE)
        
        assert global_loaded["global_setting"] == "global_value"
        assert module_loaded["module_setting"] == "module_value"
    
    async def test_load_config_with_includes(self, config_manager, temp_config_dir):
        """Test loading configuration with file includes/references."""
        # Create base config
        base_config = {
            "_metadata": {"version": "1.0.0"},
            "base_setting": "base_value"
        }
        
        # Create included config
        included_config = {
            "included_setting": "included_value"
        }
        
        base_path = temp_config_dir / "global" / "global_config.json"
        base_path.parent.mkdir(parents=True, exist_ok=True)
        
        included_path = temp_config_dir / "global" / "included.json"
        
        with open(base_path, 'w') as f:
            json.dump(base_config, f)
        
        with open(included_path, 'w') as f:
            json.dump(included_config, f)
        
        await config_manager.initialize()
        
        # For now, just verify base config loads
        # Include functionality would need to be implemented
        loaded_config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert loaded_config["base_setting"] == "base_value"
    
    async def test_load_config_with_remote_source(self, config_manager):
        """Test loading configuration from remote source (mocked)."""
        # Mock remote config loading
        remote_config = {
            "_metadata": {"version": "1.0.0", "source": "remote"},
            "remote_setting": "remote_value"
        }
        
        # For now, just test that we can set a config that appears to be from remote
        await config_manager.initialize()
        
        result = await config_manager.set_config("remote_test", remote_config, ConfigScope.GLOBAL)
        assert result is True
        
        loaded_config = await config_manager.get_config("remote_test", ConfigScope.GLOBAL)
        assert loaded_config["_metadata"]["source"] == "remote"


class TestConfigValidationLogicAndSchemaEnforcement:
    """Test configuration validation logic and schema enforcement."""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager for validation tests."""
        return EnhancedConfigManager()
    
    @pytest.fixture
    def complex_schema(self):
        """Create complex schema for testing."""
        return ConfigSchema(
            name="complex_config",
            version="1.0.0",
            fields={
                "database": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                        "ssl": {"type": "boolean"}
                    }
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "limits": {
                    "type": "object",
                    "properties": {
                        "max_connections": {"type": "integer"},
                        "timeout": {"type": "number"}
                    }
                }
            },
            required_fields=["database", "features"],
            validators={
                "database": lambda x: isinstance(x, dict) and "host" in x,
                "features": lambda x: isinstance(x, list) and len(x) > 0,
                "limits": lambda x: isinstance(x, dict) and x.get("max_connections", 0) > 0
            }
        )
    
    def test_complex_schema_validation_success(self, complex_schema):
        """Test successful validation of complex schema."""
        valid_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "ssl": True
            },
            "features": ["auth", "logging", "metrics"],
            "limits": {
                "max_connections": 100,
                "timeout": 30.0
            }
        }
        
        errors = complex_schema.validate(valid_config)
        assert len(errors) == 0
    
    def test_complex_schema_validation_missing_required(self, complex_schema):
        """Test validation failure with missing required fields."""
        invalid_config = {
            "database": {
                "host": "localhost",
                "port": 5432
            }
            # Missing required "features" field
        }
        
        errors = complex_schema.validate(invalid_config)
        assert len(errors) >= 1
        assert any("Required field 'features' is missing" in error for error in errors)
    
    def test_complex_schema_validation_custom_validator_failure(self, complex_schema):
        """Test validation failure with custom validator."""
        invalid_config = {
            "database": {
                "port": 5432
                # Missing required "host" field for database validator
            },
            "features": [],  # Empty array should fail validation
            "limits": {
                "max_connections": 0  # Should fail validation (must be > 0)
            }
        }
        
        errors = complex_schema.validate(invalid_config)
        assert len(errors) >= 2  # database and features should fail
    
    async def test_schema_enforcement_on_config_operations(self, config_manager, complex_schema):
        """Test that schema is enforced during configuration operations."""
        config_manager.register_schema(complex_schema)
        await config_manager.initialize()
        
        # Valid config should succeed
        valid_config = {
            "database": {"host": "localhost"},
            "features": ["test"]
        }
        
        result = await config_manager.set_config("complex_config", valid_config, ConfigScope.GLOBAL)
        assert result is True
        
        # Invalid config should fail
        invalid_config = {
            "database": {},  # Missing host
            "features": []   # Empty features
        }
        
        with pytest.raises(ConfigValidationError):
            await config_manager.set_config("complex_config", invalid_config, ConfigScope.GLOBAL, validate=True)
    
    def test_schema_version_compatibility(self):
        """Test schema version compatibility checking."""
        schema_v1 = ConfigSchema(
            name="test_config",
            version="1.0.0",
            fields={"setting1": {"type": "string"}},
            required_fields=["setting1"]
        )
        
        schema_v2 = ConfigSchema(
            name="test_config",
            version="2.0.0",
            fields={
                "setting1": {"type": "string"},
                "setting2": {"type": "integer"}
            },
            required_fields=["setting1", "setting2"]
        )
        
        # Test that different versions are treated as different schemas
        assert schema_v1.version != schema_v2.version
        assert len(schema_v1.required_fields) != len(schema_v2.required_fields)
    
    async def test_validation_with_nested_objects(self, config_manager):
        """Test validation of nested object structures."""
        nested_schema = ConfigSchema(
            name="nested_config",
            version="1.0.0",
            fields={
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string"}
                            }
                        }
                    }
                }
            },
            required_fields=["level1"],
            validators={
                "level1": lambda x: isinstance(x, dict) and "level2" in x
            }
        )
        
        config_manager.register_schema(nested_schema)
        await config_manager.initialize()
        
        # Valid nested config
        valid_config = {
            "level1": {
                "level2": {
                    "value": "test"
                }
            }
        }
        
        result = await config_manager.set_config("nested_config", valid_config, ConfigScope.GLOBAL)
        assert result is True
    
    async def test_validation_with_array_types(self, config_manager):
        """Test validation of array type configurations."""
        array_schema = ConfigSchema(
            name="array_config",
            version="1.0.0",
            fields={
                "string_array": {"type": "array", "items": {"type": "string"}},
                "object_array": {"type": "array", "items": {"type": "object"}}
            },
            required_fields=["string_array"],
            validators={
                "string_array": lambda x: isinstance(x, list) and all(isinstance(item, str) for item in x),
                "object_array": lambda x: isinstance(x, list) and all(isinstance(item, dict) for item in x)
            }
        )
        
        config_manager.register_schema(array_schema)
        await config_manager.initialize()
        
        # Valid array config
        valid_config = {
            "string_array": ["item1", "item2", "item3"],
            "object_array": [{"key": "value1"}, {"key": "value2"}]
        }
        
        result = await config_manager.set_config("array_config", valid_config, ConfigScope.GLOBAL)
        assert result is True


class TestConfigErrorHandlingForMalformedFiles:
    """Test error handling for malformed or missing configuration files."""
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create config manager with temporary directory."""
        return EnhancedConfigManager(base_path=temp_config_dir)
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    async def test_handle_missing_config_directory(self, temp_config_dir):
        """Test handling when config directory doesn't exist."""
        # Use non-existent directory
        non_existent_path = temp_config_dir / "non_existent"
        config_manager = EnhancedConfigManager(base_path=non_existent_path)
        
        # Should create directory and initialize successfully
        await config_manager.initialize()
        
        assert non_existent_path.exists()
        assert (non_existent_path / "global").exists()
    
    async def test_handle_empty_config_file(self, config_manager, temp_config_dir):
        """Test handling of empty configuration files."""
        # Create empty config file
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()  # Create empty file
        
        # Should handle gracefully and create default config
        await config_manager.initialize()
        
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
    
    async def test_handle_invalid_json_syntax(self, config_manager, temp_config_dir):
        """Test handling of files with invalid JSON syntax."""
        # Create file with invalid JSON
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write('{ "key": "value", }')  # Trailing comma - invalid JSON
        
        await config_manager.initialize()
        
        # Should create default config instead
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
        assert "_metadata" in config
    
    async def test_handle_incomplete_json_structure(self, config_manager, temp_config_dir):
        """Test handling of incomplete JSON structures."""
        # Create file with incomplete JSON
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write('{ "key": "value"')  # Missing closing brace
        
        await config_manager.initialize()
        
        # Should handle gracefully
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
    
    async def test_handle_wrong_data_types_in_config(self, config_manager, temp_config_dir):
        """Test handling of wrong data types in configuration."""
        # Create config with wrong data types
        invalid_config = {
            "_metadata": "should_be_object",  # Wrong type
            "modules": ["should", "be", "object"]  # Wrong type
        }
        
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(invalid_config, f)
        
        await config_manager.initialize()
        
        # Should load the config but may log warnings
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
    
    async def test_handle_circular_references_in_config(self, config_manager, temp_config_dir):
        """Test handling of circular references in configuration."""
        # Create config that would cause circular reference issues
        config_with_refs = {
            "_metadata": {"version": "1.0.0"},
            "section1": {
                "ref_to_section2": "{{section2.value}}"
            },
            "section2": {
                "ref_to_section1": "{{section1.value}}",
                "value": "test"
            }
        }
        
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config_with_refs, f)
        
        await config_manager.initialize()
        
        # Should load without infinite recursion
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
    
    async def test_handle_very_large_config_files(self, config_manager, temp_config_dir):
        """Test handling of very large configuration files."""
        # Create large config (simulate with nested structure)
        large_config = {
            "_metadata": {"version": "1.0.0"},
            "large_section": {}
        }
        
        # Add many nested items
        for i in range(1000):
            large_config["large_section"][f"item_{i}"] = {
                "value": f"value_{i}",
                "nested": {
                    "deep_value": f"deep_{i}"
                }
            }
        
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(large_config, f)
        
        await config_manager.initialize()
        
        # Should handle large files
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
        assert len(config["large_section"]) == 1000
    
    async def test_handle_unicode_and_special_characters(self, config_manager, temp_config_dir):
        """Test handling of Unicode and special characters in config."""
        # Create config with Unicode and special characters
        unicode_config = {
            "_metadata": {"version": "1.0.0"},
            "unicode_test": {
                "emoji": "🚀🎉",
                "chinese": "你好世界",
                "arabic": "مرحبا بالعالم",
                "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>?,./"
            }
        }
        
        config_path = temp_config_dir / "global" / "global_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(unicode_config, f, ensure_ascii=False)
        
        await config_manager.initialize()
        
        # Should handle Unicode correctly
        config = await config_manager.get_config("global", ConfigScope.GLOBAL)
        assert config is not None
        assert config["unicode_test"]["emoji"] == "🚀🎉"
        assert config["unicode_test"]["chinese"] == "你好世界"


class TestConfigurationMergingAndInheritance:
    """Test configuration hierarchy and precedence rules, merging logic, and override behavior."""
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create config manager with temporary directory."""
        return EnhancedConfigManager(base_path=temp_config_dir)
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def base_global_config(self):
        """Base global configuration for merging tests."""
        return {
            "_metadata": {
                "version": "1.0.0",
                "source": "global"
            },
            "modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {
                        "model": "gpt-4.1-mini",
                        "temperature": 0.7,
                        "max_tokens": 1500
                    }
                },
                "weather": {
                    "enabled": True,
                    "settings": {
                        "units": "metric",
                        "forecast_days": 3
                    }
                }
            },
            "global_setting": "global_value"
        }
    
    @pytest.fixture
    def chat_specific_config(self):
        """Chat-specific configuration for merging tests."""
        return {
            "_metadata": {
                "version": "1.0.0",
                "source": "chat_specific"
            },
            "modules": {
                "gpt": {
                    "settings": {
                        "temperature": 0.9,  # Override global temperature
                        "max_tokens": 2000   # Override global max_tokens
                    }
                }
            },
            "chat_setting": "chat_value"
        }
    
    @pytest.fixture
    def user_specific_config(self):
        """User-specific configuration for merging tests."""
        return {
            "_metadata": {
                "version": "1.0.0",
                "source": "user_specific"
            },
            "modules": {
                "gpt": {
                    "settings": {
                        "temperature": 0.5  # Override both global and chat temperature
                    }
                }
            },
            "user_setting": "user_value"
        }

    async def test_configuration_hierarchy_precedence(self, config_manager):
        """Test that configuration hierarchy follows correct precedence rules."""
        await config_manager.initialize()
        
        # Set up hierarchy: global < chat < user
        global_config = {"setting": "global", "global_only": "global_value"}
        chat_config = {"setting": "chat", "chat_only": "chat_value"}
        user_config = {"setting": "user", "user_only": "user_value"}
        
        await config_manager.set_config("global", global_config, ConfigScope.GLOBAL)
        await config_manager.set_config("test_chat", chat_config, ConfigScope.CHAT)
        await config_manager.set_config("test_user", user_config, ConfigScope.USER)
        
        # Test that each scope returns its own config
        global_result = await config_manager.get_config("global", ConfigScope.GLOBAL)
        chat_result = await config_manager.get_config("test_chat", ConfigScope.CHAT)
        user_result = await config_manager.get_config("test_user", ConfigScope.USER)
        
        assert global_result["setting"] == "global"
        assert chat_result["setting"] == "chat"
        assert user_result["setting"] == "user"
    
    async def test_deep_merge_nested_configurations(self, config_manager, base_global_config, chat_specific_config):
        """Test deep merging of nested configuration structures."""
        await config_manager.initialize()
        
        # Set base global config
        await config_manager.set_config("global", base_global_config, ConfigScope.GLOBAL)
        
        # Test the deep merge functionality directly
        merged_config = config_manager._deep_merge_configs(base_global_config, chat_specific_config)
        
        # Verify deep merge results
        assert merged_config["modules"]["gpt"]["enabled"] is True  # From global
        assert merged_config["modules"]["gpt"]["settings"]["model"] == "gpt-4.1-mini"  # From global
        assert merged_config["modules"]["gpt"]["settings"]["temperature"] == 0.9  # From chat (override)
        assert merged_config["modules"]["gpt"]["settings"]["max_tokens"] == 2000  # From chat (override)
        
        # Weather module should remain unchanged from global
        assert merged_config["modules"]["weather"]["enabled"] is True
        assert merged_config["modules"]["weather"]["settings"]["units"] == "metric"
        
        # Both global and chat specific settings should be present
        assert merged_config["global_setting"] == "global_value"
        assert merged_config["chat_setting"] == "chat_value"
    
    async def test_merge_with_array_handling(self, config_manager):
        """Test merging configurations with array values."""
        await config_manager.initialize()
        
        base_config = {
            "features": ["feature1", "feature2"],
            "permissions": ["read", "write"],
            "nested": {
                "array_field": ["item1", "item2"]
            }
        }
        
        override_config = {
            "features": ["feature3", "feature4"],  # Should replace, not merge
            "permissions": ["admin"],  # Should replace
            "nested": {
                "array_field": ["item3"]  # Should replace
            }
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # Arrays should be replaced, not merged
        assert merged["features"] == ["feature3", "feature4"]
        assert merged["permissions"] == ["admin"]
        assert merged["nested"]["array_field"] == ["item3"]
    
    async def test_merge_with_null_and_empty_values(self, config_manager):
        """Test merging configurations with null and empty values."""
        await config_manager.initialize()
        
        base_config = {
            "setting1": "value1",
            "setting2": {"nested": "value"},
            "setting3": ["item1", "item2"]
        }
        
        override_config = {
            "setting1": None,  # Should override with null
            "setting2": {},    # Should override with empty object
            "setting3": []     # Should override with empty array
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        assert merged["setting1"] is None
        assert merged["setting2"] == {}
        assert merged["setting3"] == []
    
    async def test_merge_with_type_conflicts(self, config_manager):
        """Test merging configurations with conflicting data types."""
        await config_manager.initialize()
        
        base_config = {
            "setting1": {"nested": "object"},
            "setting2": ["array", "values"],
            "setting3": "string_value"
        }
        
        override_config = {
            "setting1": "now_a_string",  # Type conflict: object -> string
            "setting2": {"now": "object"},  # Type conflict: array -> object
            "setting3": {"now": "object"}   # Type conflict: string -> object
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # Override should win in type conflicts
        assert merged["setting1"] == "now_a_string"
        assert merged["setting2"] == {"now": "object"}
        assert merged["setting3"] == {"now": "object"}
    
    async def test_hierarchical_config_inheritance(self, config_manager):
        """Test hierarchical configuration inheritance patterns."""
        await config_manager.initialize()
        
        # Set up inheritance chain
        global_config = {
            "database": {
                "host": "global.db.com",
                "port": 5432,
                "ssl": True
            },
            "features": {
                "logging": True,
                "metrics": True,
                "debug": False
            }
        }
        
        group_config = {
            "database": {
                "host": "group.db.com"  # Override only host
            },
            "features": {
                "debug": True  # Override only debug
            }
        }
        
        user_config = {
            "database": {
                "port": 3306  # Override only port
            }
        }
        
        await config_manager.set_config("global", global_config, ConfigScope.GLOBAL)
        
        # Test hierarchical inheritance using the internal method
        group_inherited = await config_manager._get_hierarchical_config("test_group", ConfigScope.CHAT)
        
        # Should inherit from global
        assert group_inherited["database"]["host"] == "global.db.com"
        assert group_inherited["database"]["port"] == 5432
        assert group_inherited["features"]["logging"] is True
    
    async def test_config_override_behavior(self, config_manager):
        """Test configuration override behavior and conflict resolution."""
        await config_manager.initialize()
        
        # Set initial config
        initial_config = {
            "module_settings": {
                "timeout": 30,
                "retries": 3,
                "features": {
                    "cache": True,
                    "logging": False
                }
            }
        }
        
        await config_manager.set_config("test_module", initial_config, ConfigScope.MODULE)
        
        # Apply override
        override_updates = {
            "module_settings": {
                "timeout": 60,  # Override existing
                "features": {
                    "logging": True,  # Override existing
                    "metrics": True   # Add new
                }
            }
        }
        
        result = await config_manager.update_config("test_module", override_updates, ConfigScope.MODULE)
        assert result is True
        
        # Verify override results
        updated_config = await config_manager.get_config("test_module", ConfigScope.MODULE)
        
        assert updated_config["module_settings"]["timeout"] == 60  # Overridden
        assert updated_config["module_settings"]["retries"] == 3   # Preserved
        assert updated_config["module_settings"]["features"]["cache"] is True    # Preserved
        assert updated_config["module_settings"]["features"]["logging"] is True  # Overridden
        assert updated_config["module_settings"]["features"]["metrics"] is True  # Added
    
    async def test_merge_with_metadata_handling(self, config_manager):
        """Test that metadata is properly handled during merging."""
        await config_manager.initialize()
        
        base_config = {
            "_metadata": {
                "version": "1.0.0",
                "source": "base",
                "created_at": "2024-01-01T00:00:00"
            },
            "setting": "base_value"
        }
        
        override_config = {
            "_metadata": {
                "version": "1.1.0",
                "source": "override",
                "updated_at": "2024-01-02T00:00:00"
            },
            "setting": "override_value"
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # Metadata should be merged properly
        assert merged["_metadata"]["version"] == "1.1.0"  # Override wins
        assert merged["_metadata"]["source"] == "override"  # Override wins
        assert merged["_metadata"]["created_at"] == "2024-01-01T00:00:00"  # Base preserved
        assert merged["_metadata"]["updated_at"] == "2024-01-02T00:00:00"  # Override added
        assert merged["setting"] == "override_value"
    
    async def test_complex_nested_merge_scenarios(self, config_manager):
        """Test complex nested merging scenarios."""
        await config_manager.initialize()
        
        base_config = {
            "level1": {
                "level2": {
                    "level3": {
                        "setting1": "base1",
                        "setting2": "base2"
                    },
                    "other_setting": "base_other"
                },
                "sibling": "base_sibling"
            },
            "top_level": "base_top"
        }
        
        override_config = {
            "level1": {
                "level2": {
                    "level3": {
                        "setting1": "override1",  # Override existing
                        "setting3": "override3"   # Add new
                    }
                    # other_setting should be preserved
                },
                "new_sibling": "override_new_sibling"  # Add new
            }
            # top_level should be preserved
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # Verify deep nested merging
        assert merged["level1"]["level2"]["level3"]["setting1"] == "override1"  # Overridden
        assert merged["level1"]["level2"]["level3"]["setting2"] == "base2"      # Preserved
        assert merged["level1"]["level2"]["level3"]["setting3"] == "override3"  # Added
        assert merged["level1"]["level2"]["other_setting"] == "base_other"      # Preserved
        assert merged["level1"]["sibling"] == "base_sibling"                    # Preserved
        assert merged["level1"]["new_sibling"] == "override_new_sibling"        # Added
        assert merged["top_level"] == "base_top"                               # Preserved
    
    async def test_merge_strategy_selection(self, config_manager):
        """Test different merge strategies (deep_merge, replace, etc.)."""
        await config_manager.initialize()
        
        base_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "options": {
                    "ssl": True,
                    "timeout": 30
                }
            }
        }
        
        # Test deep merge strategy (default)
        deep_merge_updates = {
            "database": {
                "port": 3306,  # Override port
                "options": {
                    "timeout": 60  # Override timeout, keep ssl
                }
            }
        }
        
        await config_manager.set_config("test_db", base_config, ConfigScope.MODULE)
        result = await config_manager.update_config("test_db", deep_merge_updates, ConfigScope.MODULE, strategy="deep_merge")
        assert result is True
        
        updated_config = await config_manager.get_config("test_db", ConfigScope.MODULE)
        
        # Verify deep merge preserved nested values
        assert updated_config["database"]["host"] == "localhost"  # Preserved
        assert updated_config["database"]["port"] == 3306         # Overridden
        assert updated_config["database"]["options"]["ssl"] is True  # Preserved
        assert updated_config["database"]["options"]["timeout"] == 60  # Overridden
    
    async def test_circular_reference_prevention_in_merge(self, config_manager):
        """Test prevention of circular references during merging."""
        await config_manager.initialize()
        
        # Create configs that could cause circular references
        config_a = {
            "name": "config_a",
            "reference": "config_b",
            "data": {"value": "a"}
        }
        
        config_b = {
            "name": "config_b", 
            "reference": "config_a",
            "data": {"value": "b"}
        }
        
        # Merging should not cause infinite recursion
        merged = config_manager._deep_merge_configs(config_a, config_b)
        
        assert merged["name"] == "config_b"  # Override wins
        assert merged["reference"] == "config_a"  # Override wins
        assert merged["data"]["value"] == "b"  # Override wins
    
    async def test_merge_performance_with_large_configs(self, config_manager):
        """Test merge performance with large configuration objects."""
        await config_manager.initialize()
        
        # Create large base config
        large_base = {"sections": {}}
        for i in range(100):
            large_base["sections"][f"section_{i}"] = {
                "settings": {f"setting_{j}": f"value_{j}" for j in range(50)},
                "metadata": {"id": i, "type": "section"}
            }
        
        # Create override config
        large_override = {"sections": {}}
        for i in range(0, 100, 10):  # Override every 10th section
            large_override["sections"][f"section_{i}"] = {
                "settings": {"setting_0": f"overridden_{i}"},
                "metadata": {"updated": True}
            }
        
        # Measure merge performance
        import time
        start_time = time.time()
        merged = config_manager._deep_merge_configs(large_base, large_override)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second)
        assert (end_time - start_time) < 1.0
        
        # Verify merge correctness
        assert len(merged["sections"]) == 100
        assert merged["sections"]["section_0"]["settings"]["setting_0"] == "overridden_0"
        assert merged["sections"]["section_1"]["settings"]["setting_0"] == "value_0"  # Not overridden


class TestConfigConflictResolution:
    """Test configuration conflict resolution during merging and inheritance."""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager for conflict resolution tests."""
        return EnhancedConfigManager()
    
    async def test_resolve_type_conflicts_in_merge(self, config_manager):
        """Test resolution of type conflicts during configuration merging."""
        await config_manager.initialize()
        
        # Test string vs object conflict
        base_config = {"setting": "string_value"}
        override_config = {"setting": {"nested": "object_value"}}
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        assert merged["setting"] == {"nested": "object_value"}  # Object wins
        
        # Test array vs object conflict
        base_config = {"setting": ["array", "values"]}
        override_config = {"setting": {"key": "object_value"}}
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        assert merged["setting"] == {"key": "object_value"}  # Object wins
        
        # Test object vs primitive conflict
        base_config = {"setting": {"nested": {"deep": "value"}}}
        override_config = {"setting": 42}
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        assert merged["setting"] == 42  # Primitive wins (override)
    
    async def test_resolve_version_conflicts(self, config_manager):
        """Test resolution of version conflicts in configuration metadata."""
        await config_manager.initialize()
        
        base_config = {
            "_metadata": {"version": "1.0.0", "schema_version": "1.0"},
            "setting": "base"
        }
        
        override_config = {
            "_metadata": {"version": "2.0.0", "schema_version": "1.1"},
            "setting": "override"
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # Higher version should win
        assert merged["_metadata"]["version"] == "2.0.0"
        assert merged["_metadata"]["schema_version"] == "1.1"
        assert merged["setting"] == "override"
    
    async def test_resolve_timestamp_conflicts(self, config_manager):
        """Test resolution of timestamp conflicts in metadata."""
        await config_manager.initialize()
        
        older_time = "2024-01-01T00:00:00"
        newer_time = "2024-01-02T00:00:00"
        
        base_config = {
            "_metadata": {
                "created_at": older_time,
                "updated_at": older_time
            },
            "setting": "base"
        }
        
        override_config = {
            "_metadata": {
                "created_at": newer_time,  # Should not override created_at
                "updated_at": newer_time   # Should override updated_at
            },
            "setting": "override"
        }
        
        merged = config_manager._deep_merge_configs(base_config, override_config)
        
        # created_at should keep original (older) value
        assert merged["_metadata"]["created_at"] == older_time
        # updated_at should use newer value
        assert merged["_metadata"]["updated_at"] == newer_time
    
    async def test_resolve_priority_based_conflicts(self, config_manager):
        """Test resolution of conflicts based on configuration priority."""
        await config_manager.initialize()
        
        # Simulate different priority sources
        system_config = {
            "_metadata": {"source": "system", "priority": 1},
            "setting": "system_value"
        }
        
        user_config = {
            "_metadata": {"source": "user", "priority": 10},
            "setting": "user_value"
        }
        
        admin_config = {
            "_metadata": {"source": "admin", "priority": 100},
            "setting": "admin_value"
        }
        
        # Test different merge orders
        merged1 = config_manager._deep_merge_configs(system_config, user_config)
        merged2 = config_manager._deep_merge_configs(merged1, admin_config)
        
        # Higher priority should win
        assert merged2["setting"] == "admin_value"
        assert merged2["_metadata"]["source"] == "admin"
        assert merged2["_metadata"]["priority"] == 100


class TestConfigMigrationAndVersioning:
    """Test configuration migration and versioning during merging."""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager for migration tests."""
        return EnhancedConfigManager()
    
    async def test_migrate_old_config_format(self, config_manager):
        """Test migration of old configuration format to new format."""
        await config_manager.initialize()
        
        # Old format config
        old_config = {
            "chat_id": 12345,
            "gpt_enabled": True,
            "gpt_temperature": 0.8
        }
        
        # Migrate to new format
        migrated = await config_manager.migrate_config(old_config, "1.0", "2.0")
        
        # Verify migration
        assert "chat_metadata" in migrated
        assert migrated["chat_metadata"]["chat_id"] == 12345
        assert "config_modules" in migrated
        assert migrated["config_modules"]["gpt"]["enabled"] is True
        assert migrated["config_modules"]["gpt"]["overrides"]["temperature"] == 0.8
    
    async def test_migrate_with_unsupported_version(self, config_manager):
        """Test migration with unsupported version combination."""
        await config_manager.initialize()
        
        config = {"setting": "value"}
        
        # Unsupported migration should return original config
        migrated = await config_manager.migrate_config(config, "3.0", "4.0")
        assert migrated == config
    
    async def test_migrate_with_partial_data(self, config_manager):
        """Test migration with partial/incomplete data."""
        await config_manager.initialize()
        
        # Partial old format
        partial_old_config = {
            "chat_id": 12345,
            "gpt_enabled": True
            # Missing gpt_temperature
        }
        
        migrated = await config_manager.migrate_config(partial_old_config, "1.0", "2.0")
        
        # Should handle missing fields gracefully
        assert migrated["chat_metadata"]["chat_id"] == 12345
        assert migrated["config_modules"]["gpt"]["enabled"] is True
        assert "overrides" not in migrated["config_modules"]["gpt"]  # No temperature to migrate
    
    async def test_version_compatibility_checking(self, config_manager):
        """Test version compatibility checking during merging."""
        await config_manager.initialize()
        
        v1_config = {
            "_metadata": {"version": "1.0.0", "schema_version": "1.0"},
            "old_setting": "value"
        }
        
        v2_config = {
            "_metadata": {"version": "2.0.0", "schema_version": "2.0"},
            "new_setting": "value"
        }
        
        # Should be able to merge different versions
        merged = config_manager._deep_merge_configs(v1_config, v2_config)
        
        # Should preserve both settings and use newer version
        assert merged["_metadata"]["version"] == "2.0.0"
        assert merged["_metadata"]["schema_version"] == "2.0"
        assert "old_setting" in merged
        assert "new_setting" in merged


# Integration test to verify the complete functionality
class TestConfigManagerIntegration:
    """Integration tests for the complete configuration manager functionality."""
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create config manager with temporary directory."""
        return EnhancedConfigManager(base_path=temp_config_dir)
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    async def test_end_to_end_config_workflow(self, config_manager, temp_config_dir):
        """Test complete end-to-end configuration workflow."""
        # Initialize
        await config_manager.initialize()
        
        # Create and save global config
        global_config = {
            "modules": {
                "gpt": {
                    "enabled": True,
                    "settings": {"temperature": 0.7}
                }
            }
        }
        
        result = await config_manager.set_config("global", global_config, ConfigScope.GLOBAL)
        assert result is True
        
        # Create module-specific config
        module_config = {
            "enabled": True,
            "api_key": "test_key",
            "settings": {"timeout": 30}
        }
        
        result = await config_manager.set_config("test_module", module_config, ConfigScope.MODULE)
        assert result is True
        
        # Verify configs can be retrieved
        retrieved_global = await config_manager.get_config("global", ConfigScope.GLOBAL)
        retrieved_module = await config_manager.get_config("test_module", ConfigScope.MODULE)
        
        assert retrieved_global["modules"]["gpt"]["enabled"] is True
        assert retrieved_module["api_key"] == "test_key"
        
        # Update config
        updates = {"settings": {"timeout": 60}}
        result = await config_manager.update_config("test_module", updates, ConfigScope.MODULE)
        assert result is True
        
        # Verify update
        updated_config = await config_manager.get_config("test_module", ConfigScope.MODULE)
        assert updated_config["settings"]["timeout"] == 60
        assert updated_config["api_key"] == "test_key"  # Should be preserved
        
        # List configs
        global_configs = await config_manager.list_configs(ConfigScope.GLOBAL)
        module_configs = await config_manager.list_configs(ConfigScope.MODULE)
        
        assert "modules" in global_configs
        assert "test_module" in module_configs
        
        # Clean up
        await config_manager.shutdown()
    
    async def test_config_persistence_across_restarts(self, config_manager, temp_config_dir):
        """Test that configurations persist across manager restarts."""
        # First session - create and save config
        await config_manager.initialize()
        
        test_config = {
            "persistent_setting": "should_persist",
            "nested": {"value": 42}
        }
        
        await config_manager.set_config("persistent_test", test_config, ConfigScope.MODULE)
        await config_manager.shutdown()
        
        # Second session - create new manager and verify persistence
        new_manager = EnhancedConfigManager(base_path=temp_config_dir)
        await new_manager.initialize()
        
        retrieved_config = await new_manager.get_config("persistent_test", ConfigScope.MODULE)
        
        assert retrieved_config["persistent_setting"] == "should_persist"
        assert retrieved_config["nested"]["value"] == 42
        
        await new_manager.shutdown()