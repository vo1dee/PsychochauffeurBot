"""
Enhanced Configuration Manager

This module provides an improved configuration management system with
validation, hot-reloading, versioning, and better structure.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Set
import hashlib
import aiofiles
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    WATCHDOG_AVAILABLE = False

from modules.service_registry import ServiceInterface
from modules.event_system import event_bus, EventType

logger = logging.getLogger(__name__)


class ConfigChangeEvent:
    """Event object for configuration changes."""
    def __init__(self, scope: 'ConfigScope', config_id: str, change_type: str, old_value: Any = None, new_value: Any = None):
        self.scope = scope
        self.config_id = config_id
        self.change_type = change_type
        self.old_value = old_value
        self.new_value = new_value


class ConfigScope(Enum):
    """Configuration scopes."""
    GLOBAL = "global"
    CHAT = "chat"
    USER = "user"
    MODULE = "module"


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


@dataclass
class ConfigSchema:
    """Configuration schema definition."""
    name: str
    version: str
    fields: Dict[str, Any]
    required_fields: List[str] = field(default_factory=list)
    validators: Dict[str, Callable[..., Any]] = field(default_factory=dict)
    
    def validate(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration against schema."""
        errors = []
        
        # Check required fields
        for field_name in self.required_fields:
            if field_name not in config:
                errors.append(f"Required field '{field_name}' is missing")
        
        # Run custom validators
        for field_name, validator in self.validators.items():
            if field_name in config:
                try:
                    if not validator(config[field_name]):
                        errors.append(f"Validation failed for field '{field_name}'")
                except Exception as e:
                    errors.append(f"Validator error for field '{field_name}': {e}")
        
        return errors


@dataclass
class ConfigMetadata:
    """Configuration metadata."""
    version: str
    created_at: datetime
    updated_at: datetime
    checksum: str
    schema_version: str
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "checksum": self.checksum,
            "schema_version": self.schema_version,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigMetadata':
        """Create from dictionary."""
        return cls(
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            checksum=data["checksum"],
            schema_version=data["schema_version"],
            source=data["source"]
        )


@dataclass
class ConfigEntry:
    """Configuration entry with metadata."""
    key: str
    value: Any
    scope: ConfigScope
    metadata: ConfigMetadata
    schema: Optional[ConfigSchema] = None
    
    def validate(self) -> List[str]:
        """Validate this configuration entry."""
        if self.schema:
            return self.schema.validate({"value": self.value})
        return []


class ConfigChangeHandler(ABC):
    """Abstract handler for configuration changes."""
    
    @abstractmethod
    async def handle_change(self, key: str, old_value: Any, new_value: Any, scope: ConfigScope) -> None:
        """Handle configuration change."""
        pass


class ConfigWatcher:
    """File system watcher for configuration changes."""
    
    def __init__(self, config_manager: 'EnhancedConfigManager') -> None:
        self.config_manager = config_manager
        self.debounce_delay = 1.0  # seconds
        self.pending_changes: Dict[str, float] = {}
        
        if WATCHDOG_AVAILABLE:
            # Initialize as FileSystemEventHandler
            FileSystemEventHandler.__init__(self)
    
    def on_modified(self, event: Any) -> None:
        """Handle file modification events."""
        if not WATCHDOG_AVAILABLE:
            return
            
        if event.is_directory:
            return
        
        file_path = event.src_path
        if file_path.endswith('.json'):
            # Debounce rapid changes
            current_time = asyncio.get_event_loop().time()
            self.pending_changes[file_path] = current_time
            
            # Schedule reload after debounce delay
            asyncio.create_task(self._debounced_reload(file_path, current_time))
    
    async def _debounced_reload(self, file_path: str, change_time: float) -> None:
        """Reload configuration after debounce delay."""
        await asyncio.sleep(self.debounce_delay)
        
        # Check if this is still the latest change
        if self.pending_changes.get(file_path) == change_time:
            await self.config_manager._reload_config_file(file_path)
            del self.pending_changes[file_path]

# Make ConfigWatcher inherit from FileSystemEventHandler if available
if WATCHDOG_AVAILABLE:
    ConfigWatcher.__bases__ = (FileSystemEventHandler,)


class EnhancedConfigManager(ServiceInterface):
    """
    Enhanced configuration manager with validation, hot-reloading, and versioning.
    
    Features:
    - Schema validation
    - Hot-reloading of configuration files
    - Configuration versioning and migration
    - Event-driven change notifications
    - Hierarchical configuration inheritance
    - Configuration caching and optimization
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(__file__).parent.parent / "config"
        self.global_config_path = self.base_path / "global"
        self.chat_config_path = self.base_path / "private"
        self.group_config_path = self.base_path / "group"
        self.module_config_path = self.base_path / "modules"
        self.schema_path = self.base_path / "schemas"
        
        # Internal state
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._schemas: Dict[str, ConfigSchema] = {}
        self._change_handlers: List[ConfigChangeHandler] = []
        self._file_locks: Dict[str, asyncio.Lock] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._watcher: Optional[Observer] = None
        
        # Configuration
        self.cache_ttl_seconds = 300  # 5 minutes
        self.enable_hot_reload = True
        self.enable_validation = True
        self.backup_on_change = True
    
    async def initialize(self) -> None:
        """Initialize the enhanced configuration manager."""
        logger.info("Initializing Enhanced Configuration Manager...")
        
        # Create directory structure
        await self._ensure_directories()
        
        # Load schemas
        await self._load_schemas()
        
        # Load existing configurations
        await self._load_all_configs()
        
        # Setup file watching for hot-reload
        if self.enable_hot_reload:
            await self._setup_file_watcher()
        
        logger.info("Enhanced Configuration Manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the configuration manager."""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
        
        # Clear caches
        self._configs.clear()
        self._cache.clear()
        self._cache_ttl.clear()
        
        logger.info("Enhanced Configuration Manager shutdown")
    
    async def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.base_path,
            self.global_config_path,
            self.chat_config_path,
            self.group_config_path,
            self.module_config_path,
            self.schema_path,
            self.base_path / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def _load_schemas(self) -> None:
        """Load configuration schemas."""
        if not self.schema_path.exists():
            return
        
        for schema_file in self.schema_path.glob("*.json"):
            try:
                async with aiofiles.open(schema_file, 'r') as f:
                    schema_data = json.loads(await f.read())
                
                schema = ConfigSchema(
                    name=schema_data["name"],
                    version=schema_data["version"],
                    fields=schema_data["fields"],
                    required_fields=schema_data.get("required_fields", [])
                )
                
                self._schemas[schema.name] = schema
                logger.info(f"Loaded schema: {schema.name} v{schema.version}")
                
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")
    
    async def _load_all_configs(self) -> None:
        """Load all existing configuration files."""
        # Load global config
        await self._load_global_config()
        
        # Load module configs
        if self.module_config_path.exists():
            for config_file in self.module_config_path.glob("*.json"):
                await self._load_config_file(str(config_file))
    
    async def _load_global_config(self) -> None:
        """Load global configuration."""
        global_config_file = self.global_config_path / "global_config.json"
        if global_config_file.exists():
            if not await self._load_config_file(str(global_config_file)):
                await self._create_default_global_config()
        else:
            # Create default global config
            await self._create_default_global_config()
    
    async def _create_default_global_config(self) -> None:
        """Create default global configuration."""
        default_config = {
            "_metadata": {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "schema_version": "1.0.0",
                "source": "system_default"
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
                },
                "reminders": {
                    "enabled": True,
                    "settings": {
                        "max_per_user": 5,
                        "max_duration_days": 30
                    }
                }
            }
        }
        
        await self.set_config("global", default_config, ConfigScope.GLOBAL, validate=False, source="system_default")
    
    async def _load_config_file(self, file_path: str) -> bool:
        """Load a specific configuration file."""
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                if not content.strip():
                    logger.warning(f"Config file is empty: {file_path}")
                    return False
                config_data = json.loads(content)

            path_obj = Path(file_path)
            if "global" in str(path_obj):
                key = "global"
            elif "modules" in str(path_obj):
                key = f"module_{path_obj.stem}"
            else:
                key = path_obj.stem

            self._configs[key] = config_data

            if self.enable_validation and key in self._schemas:
                errors = self._schemas[key].validate(config_data)
                if errors:
                    logger.warning(f"Configuration validation errors for {key}: {errors}")

            logger.debug(f"Loaded configuration: {key}")
            return True
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading config file {file_path}: {e}")
            return False
    
    async def _setup_file_watcher(self) -> None:
        """Setup file system watcher for hot-reload."""
        try:
            from watchdog.observers import Observer
            
            self._watcher = Observer()
            handler = ConfigWatcher(self)
            
            # Watch all config directories
            for path in [self.global_config_path, self.module_config_path]:
                if path.exists():
                    self._watcher.schedule(handler, str(path), recursive=True)
            
            self._watcher.start()
            logger.info("Configuration file watcher started")
            
        except ImportError:
            logger.warning("Watchdog not available, hot-reload disabled")
        except Exception as e:
            logger.error(f"Failed to setup file watcher: {e}")
    
    async def _reload_config_file(self, file_path: str) -> None:
        """Reload a configuration file and notify handlers."""
        logger.info(f"Reloading configuration file: {file_path}")
        
        # Get old config for comparison
        path_obj = Path(file_path)
        key = path_obj.stem
        old_config = self._configs.get(key, {})
        
        # Reload the file
        await self._load_config_file(file_path)
        
        # Get new config
        new_config = self._configs.get(key, {})
        
        # Notify change handlers
        for handler in self._change_handlers:
            try:
                await handler.handle_change(key, old_config, new_config, ConfigScope.GLOBAL)
            except Exception as e:
                logger.error(f"Error in config change handler: {e}")
        
        # Publish event
        await event_bus.publish_event(
            EventType.CONFIG_CHANGED,
            "enhanced_config_manager",
            {
                "key": key,
                "file_path": file_path,
                "old_config": old_config,
                "new_config": new_config
            }
        )
        
        # Clear related cache entries
        self._clear_cache_for_key(key)
    
    def _clear_cache_for_key(self, key: str) -> None:
        """Clear cache entries related to a configuration key."""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(key)]
        for cache_key in keys_to_remove:
            del self._cache[cache_key]
            if cache_key in self._cache_ttl:
                del self._cache_ttl[cache_key]
    
    def _get_file_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create a lock for a file."""
        if file_path not in self._file_locks:
            self._file_locks[file_path] = asyncio.Lock()
        return self._file_locks[file_path]
    
    def _calculate_checksum(self, data: Any) -> str:
        """Calculate checksum for data."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache_ttl:
            return False
        
        import time
        return time.time() < self._cache_ttl[cache_key]
    
    def _set_cache(self, cache_key: str, value: Any) -> None:
        """Set cache entry with TTL."""
        import time
        self._cache[cache_key] = value
        self._cache_ttl[cache_key] = time.time() + self.cache_ttl_seconds
    
    async def get_config(
        self, 
        key: str, 
        scope: ConfigScope = ConfigScope.GLOBAL,
        default: Any = None
    ) -> Any:
        """Get configuration value."""
        cache_key = f"{scope.value}:{key}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Get configuration based on scope
        config_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
        
        if scope == ConfigScope.GLOBAL:
            # For global scope, the config_key is the same as the key
            config = self._configs.get(key, {})
            # Navigate to nested key if needed
            if "." in key:
                parts = key.split(".")
                value = config
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = default
                        break
            else:
                # For global scope, return the entire config for that key
                value = config if config else default
        elif scope == ConfigScope.MODULE:
            # For module scope, return the entire module config
            value = self._configs.get(f"module_{key}", default)
        else:
            # For chat/user scope, return the entire config for that key
            value = self._configs.get(config_key, default)
            logger.info(f"get_config for {config_key}: returning {value}")
        
        # Cache the result
        self._set_cache(cache_key, value)
        
        return value
    
    async def _get_hierarchical_config(self, key: str, scope: ConfigScope) -> Dict[str, Any]:
        """Get configuration with hierarchical inheritance."""
        # Start with global config as base
        config = self._configs.get("global", {}).copy()
        
        # Override with scope-specific config if available
        scope_config = self._configs.get(f"{scope.value}_{key}", {})
        if scope_config:
            config.update(scope_config)
        
        return config
    
    async def set_config(
        self, 
        key: str, 
        value: Any, 
        scope: ConfigScope = ConfigScope.GLOBAL,
        validate: bool = True,
        source: str = "api_update"
    ) -> bool:
        """Set configuration value."""
        try:
            # Validate if enabled and schema exists
            if validate and self.enable_validation:
                schema_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
                if schema_key in self._schemas:
                    # Validate the actual value, not wrapped in {"value": value}
                    errors = self._schemas[schema_key].validate(value if isinstance(value, dict) else {"value": value})
                    if errors:
                        raise ConfigValidationError(f"Validation errors: {errors}")
                else:
                    # Basic validation for known config structures
                    validation_errors = self._basic_validation(value)
                    if validation_errors:
                        logger.error(f"Basic validation failed: {validation_errors}")
                        return False
            
            # Get current config
            config_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
            current_config = self._configs.get(config_key, {})
            old_value = current_config.copy() if isinstance(current_config, dict) else current_config
            
            # Update configuration
            if scope == ConfigScope.GLOBAL:
                # For global scope, store the entire value as the config
                self._configs[config_key] = value
            else:
                # For non-global scopes, store the entire value as the config
                self._configs[config_key] = value
            
            # Update metadata
            now = datetime.now()
            metadata = {
                "version": "1.0.0",
                "updated_at": now.isoformat(),
                "checksum": self._calculate_checksum(self._configs[config_key]),
                "source": source
            }
            
            if scope == ConfigScope.GLOBAL:
                if "_metadata" not in self._configs[config_key]:
                    metadata["created_at"] = now.isoformat()
                else:
                    metadata["created_at"] = self._configs[config_key]["_metadata"].get("created_at", now.isoformat())
                
                self._configs[config_key]["_metadata"] = metadata
            else:
                # For non-global scopes, add metadata to the config if it's a dict
                if isinstance(self._configs[config_key], dict):
                    if "_metadata" not in self._configs[config_key]:
                        metadata["created_at"] = now.isoformat()
                    else:
                        metadata["created_at"] = self._configs[config_key]["_metadata"].get("created_at", now.isoformat())
                    
                    self._configs[config_key]["_metadata"] = metadata
            
            # Save to file
            await self._save_config_to_file(config_key, self._configs[config_key])
            
            # Notify change handlers
            for handler in self._change_handlers:
                try:
                    if hasattr(handler, 'handle_change'):
                        await handler.handle_change(key, old_value, value, scope)
                    elif callable(handler):
                        # Support simple function callbacks
                        event = ConfigChangeEvent(scope, key, "set", old_value, value)
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                except Exception as e:
                    logger.error(f"Error in config change handler: {e}")
            
            # Clear cache - use the correct cache key format
            cache_key = f"{scope.value}:{key}"
            if cache_key in self._cache:
                del self._cache[cache_key]
            if cache_key in self._cache_ttl:
                del self._cache_ttl[cache_key]
            
            logger.info(f"Configuration updated: {config_key}.{key}")
            return True
            
        except ConfigValidationError:
            # Re-raise validation errors so they can be caught by tests
            raise
        except Exception as e:
            logger.error(f"Failed to set configuration {key}: {e}")
            return False
    
    async def _save_config_to_file(self, config_key: str, config_data: Dict[str, Any]) -> None:
        """Save configuration to file."""
        # Determine file path based on config key
        if config_key == "global":
            file_path = self.global_config_path / "global_config.json"
        elif config_key.startswith("module_"):
            module_name = config_key[7:]  # Remove "module_" prefix
            file_path = self.module_config_path / f"{module_name}.json"
        else:
            # For chat/user configs, create appropriate directory structure
            file_path = self.base_path / "custom" / f"{config_key}.json"
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file if enabled
        if self.backup_on_change and file_path.exists():
            backup_path = self.base_path / "backups" / f"{file_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, 'r') as src:
                content = await src.read()
            async with aiofiles.open(backup_path, 'w') as dst:
                await dst.write(content)
        
        # Save new configuration
        async with self._get_file_lock(str(file_path)):
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(config_data, indent=2))
    
    def register_change_handler(self, handler: ConfigChangeHandler) -> None:
        """Register a configuration change handler."""
        self._change_handlers.append(handler)
        logger.info(f"Registered config change handler: {handler.__class__.__name__}")
    
    def register_schema(self, schema: ConfigSchema) -> None:
        """Register a configuration schema."""
        self._schemas[schema.name] = schema
        logger.info(f"Registered config schema: {schema.name} v{schema.version}")
    
    async def validate_all_configs(self) -> Dict[str, List[str]]:
        """Validate all configurations against their schemas."""
        validation_results = {}
        
        for config_key, config_data in self._configs.items():
            if config_key in self._schemas:
                errors = self._schemas[config_key].validate(config_data)
                if errors:
                    validation_results[config_key] = errors
        
        return validation_results
    
    async def list_configs(self, scope: ConfigScope = ConfigScope.GLOBAL) -> List[str]:
        """List all configuration keys for a given scope."""
        try:
            if scope == ConfigScope.GLOBAL:
                # For global scope, return keys within the global config
                global_config = self._configs.get("global", {})
                return [key for key in global_config.keys() if not key.startswith("_")]
            elif scope == ConfigScope.MODULE:
                # For module scope, return module names
                module_keys = [key for key in self._configs.keys() if key.startswith("module_")]
                return [key[7:] for key in module_keys]  # Remove "module_" prefix
            else:
                # For chat/user scope, return the config IDs
                scope_prefix = f"{scope.value}_"
                scope_keys = [key for key in self._configs.keys() if key.startswith(scope_prefix)]
                return [key[len(scope_prefix):] for key in scope_keys]
                
        except Exception as e:
            logger.error(f"Failed to list configurations for scope {scope}: {e}")
            return []
    
    async def delete_config(
        self, 
        key: str, 
        scope: ConfigScope = ConfigScope.GLOBAL
    ) -> bool:
        """Delete configuration."""
        try:
            config_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
            
            if config_key in self._configs:
                # For global scope, delete the specific key within the config
                if scope == ConfigScope.GLOBAL:
                    if key in self._configs[config_key]:
                        del self._configs[config_key][key]
                        logger.info(f"Configuration key deleted: {config_key}.{key}")
                        return True
                else:
                    # For other scopes, delete the entire config entry
                    del self._configs[config_key]
                    
                    # Remove file if it exists
                    if config_key.startswith("module_"):
                        module_name = config_key[7:]  # Remove "module_" prefix
                        file_path = self.module_config_path / f"{module_name}.json"
                    else:
                        # For chat/user configs
                        file_path = self.base_path / "custom" / f"{config_key}.json"
                    
                    if file_path.exists():
                        file_path.unlink()
                    
                    # Clear related cache entries
                    cache_key = f"{scope.value}:{key}"
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                    if cache_key in self._cache_ttl:
                        del self._cache_ttl[cache_key]
                    
                    logger.info(f"Configuration deleted: {config_key}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete configuration {key}: {e}")
            return False
    
    def _basic_validation(self, config_data: Any) -> List[str]:
        """Perform basic validation on configuration data."""
        errors = []
        
        if isinstance(config_data, dict):
            # Check for common config structures and validate types
            if "config_modules" in config_data:
                modules = config_data["config_modules"]
                if isinstance(modules, dict):
                    for module_name, module_config in modules.items():
                        if isinstance(module_config, dict) and "enabled" in module_config:
                            enabled_value = module_config["enabled"]
                            if not isinstance(enabled_value, bool):
                                errors.append(f"Module '{module_name}' enabled field must be boolean, got {type(enabled_value).__name__}")
        
        return errors
    
    def subscribe_to_changes(self, handler: ConfigChangeHandler) -> None:
        """Subscribe to configuration change events."""
        if handler not in self._change_handlers:
            self._change_handlers.append(handler)
    
    def unsubscribe_from_changes(self, handler: ConfigChangeHandler) -> None:
        """Unsubscribe from configuration change events."""
        if handler in self._change_handlers:
            self._change_handlers.remove(handler)
    
    async def update_config(self, key: str, updates: Dict[str, Any], scope: ConfigScope = ConfigScope.GLOBAL, strategy: str = "deep_merge") -> bool:
        """Update existing configuration with merge strategy."""
        try:
            # Get current config
            current_config = await self.get_config(key, scope)
            if current_config is None:
                current_config = {}
            
            if strategy == "deep_merge":
                # Deep merge the updates
                merged_config = self._deep_merge(current_config, updates)
            else:
                # Replace strategy - replace matching sections
                merged_config = self._replace_merge(current_config, updates)
            
            # Set the merged config
            return await self.set_config(key, merged_config, scope)
            
        except Exception as e:
            logger.error(f"Failed to update configuration {key}: {e}")
            return False
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        import copy
        result = copy.deepcopy(base)
        
        for key, value in updates.items():
            if key in result and isinstance(result.get(key), dict) and isinstance(value, dict) and value:
                # Only deep merge if the update value is a non-empty dict
                result[key] = self._deep_merge(result[key], value)
            else:
                # Replace with the new value (including empty dicts, None, etc.)
                result[key] = copy.deepcopy(value)
        
        return result
    
    def _replace_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Replace merge - replace entire sections completely."""
        import copy
        result = copy.deepcopy(base)
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # For nested dictionaries, use replace nested logic
                result[key] = self._replace_nested(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        
        return result
    
    def _replace_nested(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Helper for nested replace merge - replaces specific nested sections while preserving others."""
        import copy
        result = copy.deepcopy(base)
        
        for key, value in updates.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                # For nested dictionaries, completely replace the section
                result[key] = copy.deepcopy(value)
            else:
                # For non-dict values or new keys, just set the value
                result[key] = copy.deepcopy(value)
        
        return result
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about loaded configurations."""
        return {
            "loaded_configs": list(self._configs.keys()),
            "loaded_schemas": list(self._schemas.keys()),
            "cache_entries": len(self._cache),
            "change_handlers": len(self._change_handlers),
            "hot_reload_enabled": self.enable_hot_reload,
            "validation_enabled": self.enable_validation
        }
    
    async def get_effective_config(self, scope: ConfigScope, key: str) -> Dict[str, Any]:
        """Get effective configuration by merging global defaults with scope-specific overrides."""
        try:
            # Start with global defaults
            global_config = await self.get_config("default", ConfigScope.GLOBAL) or {}
            
            # Get scope-specific config
            scope_config = await self.get_config(key, scope) or {}
            
            # Create effective config by merging
            effective_config = self._deep_merge_configs(global_config, scope_config)
            
            return effective_config
            
        except Exception as e:
            logger.error(f"Failed to get effective config for {scope.value}:{key}: {e}")
            return {}
    
    def _deep_merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration with special handling for config_modules."""
        import copy
        result = self._deep_merge(base, override)

        # Special handling for config_modules: merge settings with overrides
        # Handle both config_modules and default_modules
        modules_key = "config_modules" if "config_modules" in result else None
        base_modules_key = "config_modules" if "config_modules" in base else "default_modules" if "default_modules" in base else None
        
        if modules_key and modules_key in result:
            for module_name, module_config in result[modules_key].items():
                if isinstance(module_config, dict):
                    # Get base module config (could be from default_modules or config_modules)
                    base_module = {}
                    if base_modules_key and base_modules_key in base:
                        base_module = base[base_modules_key].get(module_name, {})
                    
                    # If we have both settings and overrides, merge them
                    if "settings" in module_config and "overrides" in module_config:
                        merged_settings = copy.deepcopy(module_config["settings"])
                        merged_settings.update(module_config["overrides"])
                        module_config["settings"] = merged_settings
                        del module_config["overrides"]
                    # If we only have overrides but base had settings, merge them
                    elif "overrides" in module_config and "settings" in base_module:
                        merged_settings = copy.deepcopy(base_module["settings"])
                        merged_settings.update(module_config["overrides"])
                        module_config["settings"] = merged_settings
                        del module_config["overrides"]

        if "_metadata" in base and "_metadata" in result:
            if "created_at" in base["_metadata"]:
                result["_metadata"]["created_at"] = base["_metadata"]["created_at"]
        
        return result
    
    async def create_backup(self, scope: ConfigScope, key: str) -> Optional[str]:
        """Create a backup of the specified configuration."""
        try:
            config_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
            config_data = self._configs.get(config_key)
            
            if config_data is None:
                raise ValueError(f"Configuration {config_key} not found")
            
            # Deep copy the config data to avoid reference issues
            import copy
            backup_data = copy.deepcopy(config_data)
            
            # Generate backup ID
            backup_id = f"{config_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create backup directory if it doesn't exist
            backup_dir = self.base_path / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Save backup
            backup_file = backup_dir / f"{backup_id}.json"
            async with aiofiles.open(backup_file, 'w') as f:
                await f.write(json.dumps(backup_data, indent=2))
            
            logger.info(f"Created backup {backup_id} for {config_key}")
            return backup_id
            
        except Exception as e:
            logger.error(f"Failed to create backup for {config_key}: {e}")
            return None
    
    async def restore_backup(self, backup_id: str) -> bool:
        """Restore configuration from backup."""
        try:
            backup_file = self.base_path / "backups" / f"{backup_id}.json"
            
            if not backup_file.exists():
                logger.error(f"Backup file {backup_id} not found")
                return False
            
            # Load backup data
            async with aiofiles.open(backup_file, 'r') as f:
                backup_data = json.loads(await f.read())
            
            # Extract config key from backup ID
            config_key = "_".join(backup_id.split("_")[:-2])  # Remove timestamp
            
            logger.info(f"Restoring backup {backup_id} to config_key {config_key}: {backup_data}")
            
            # Restore configuration
            self._configs[config_key] = backup_data
            
            # Save to file
            await self._save_config_to_file(config_key, backup_data)
            
            # Clear cache more thoroughly
            self._clear_cache_for_key(config_key)
            # Also clear any cache entries that might be related to this config
            # The cache key format is "scope:key", so we need to clear that too
            scope_name = config_key.split("_")[0]  # Extract scope from config_key
            key_name = "_".join(config_key.split("_")[1:])  # Extract key from config_key
            cache_key_format = f"{scope_name}:{key_name}"
            self._cache.pop(cache_key_format, None)
            self._cache_ttl.pop(cache_key_format, None)
            
            # Clear any other related cache entries
            cache_keys_to_remove = [k for k in self._cache.keys() if config_key in k or key_name in k]
            for cache_key in cache_keys_to_remove:
                self._cache.pop(cache_key, None)
                self._cache_ttl.pop(cache_key, None)
            
            logger.info(f"Restored configuration from backup {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return False
    
    def _get_config_file_path(self, scope: ConfigScope, key: str) -> Path:
        """Get the file path for a configuration."""
        if scope == ConfigScope.GLOBAL:
            config_key = "global"
        else:
            config_key = f"{scope.value}_{key}"
        
        if config_key == "global":
            return self.global_config_path / "global_config.json"
        elif config_key.startswith("module_"):
            module_name = config_key[7:]  # Remove "module_" prefix
            return self.module_config_path / f"{module_name}.json"
        else:
            # For chat/user configs
            return self.base_path / "custom" / f"{config_key}.json"
    
    async def migrate_config(self, old_config: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate configuration from one version to another."""
        try:
            migrated_config = {}
            
            # Handle migration from version 1.0 to 2.0
            if from_version == "1.0" and to_version == "2.0":
                # Migrate chat_id to chat_metadata structure
                if "chat_id" in old_config:
                    migrated_config["chat_metadata"] = {
                        "chat_id": old_config["chat_id"]
                    }
                
                # Migrate GPT settings to config_modules structure
                config_modules = {}
                if "gpt_enabled" in old_config or "gpt_temperature" in old_config:
                    gpt_config = {"enabled": old_config.get("gpt_enabled", False)}
                    
                    if "gpt_temperature" in old_config:
                        gpt_config["overrides"] = {"temperature": old_config["gpt_temperature"]}
                    
                    config_modules["gpt"] = gpt_config
                
                if config_modules:
                    migrated_config["config_modules"] = config_modules
                
                # Copy any other fields that don't need migration
                for key, value in old_config.items():
                    if key not in ["chat_id", "gpt_enabled", "gpt_temperature"]:
                        migrated_config[key] = value
            else:
                # For unsupported migrations, return the original config
                migrated_config = old_config.copy()
            
            return migrated_config
            
        except Exception as e:
            logger.error(f"Failed to migrate configuration from {from_version} to {to_version}: {e}")
            return old_config
