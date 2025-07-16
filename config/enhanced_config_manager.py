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
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from modules.service_registry import ServiceInterface
from modules.event_system import event_bus, EventType

logger = logging.getLogger(__name__)


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
    validators: Dict[str, Callable] = field(default_factory=dict)
    
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


class ConfigWatcher(FileSystemEventHandler):
    """File system watcher for configuration changes."""
    
    def __init__(self, config_manager: 'EnhancedConfigManager'):
        self.config_manager = config_manager
        self.debounce_delay = 1.0  # seconds
        self.pending_changes: Dict[str, float] = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if file_path.endswith('.json'):
            # Debounce rapid changes
            current_time = asyncio.get_event_loop().time()
            self.pending_changes[file_path] = current_time
            
            # Schedule reload after debounce delay
            asyncio.create_task(self._debounced_reload(file_path, current_time))
    
    async def _debounced_reload(self, file_path: str, change_time: float):
        """Reload configuration after debounce delay."""
        await asyncio.sleep(self.debounce_delay)
        
        # Check if this is still the latest change
        if self.pending_changes.get(file_path) == change_time:
            await self.config_manager._reload_config_file(file_path)
            del self.pending_changes[file_path]


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
            await self._load_config_file(str(global_config_file))
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
        
        await self.set_config("global", default_config, ConfigScope.GLOBAL)
    
    async def _load_config_file(self, file_path: str) -> None:
        """Load a specific configuration file."""
        try:
            async with aiofiles.open(file_path, 'r') as f:
                config_data = json.loads(await f.read())
            
            # Extract key from file path
            path_obj = Path(file_path)
            if "global" in str(path_obj):
                key = "global"
            elif "modules" in str(path_obj):
                key = f"module_{path_obj.stem}"
            else:
                key = path_obj.stem
            
            self._configs[key] = config_data
            
            # Validate if schema exists
            if self.enable_validation and key in self._schemas:
                errors = self._schemas[key].validate(config_data)
                if errors:
                    logger.warning(f"Configuration validation errors for {key}: {errors}")
            
            logger.debug(f"Loaded configuration: {key}")
            
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
    
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
        if scope == ConfigScope.GLOBAL:
            config = self._configs.get("global", {})
        elif scope == ConfigScope.MODULE:
            config = self._configs.get(f"module_{key}", {})
        else:
            # For chat/user scope, implement hierarchical lookup
            config = await self._get_hierarchical_config(key, scope)
        
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
            value = config.get(key, default)
        
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
        validate: bool = True
    ) -> bool:
        """Set configuration value."""
        try:
            # Validate if enabled and schema exists
            if validate and self.enable_validation:
                schema_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
                if schema_key in self._schemas:
                    errors = self._schemas[schema_key].validate({"value": value})
                    if errors:
                        raise ConfigValidationError(f"Validation errors: {errors}")
            
            # Get current config
            config_key = key if scope == ConfigScope.GLOBAL else f"{scope.value}_{key}"
            current_config = self._configs.get(config_key, {})
            old_value = current_config.get(key)
            
            # Update configuration
            if config_key not in self._configs:
                self._configs[config_key] = {}
            
            self._configs[config_key][key] = value
            
            # Update metadata
            now = datetime.now()
            metadata = {
                "version": "1.0.0",
                "updated_at": now.isoformat(),
                "checksum": self._calculate_checksum(self._configs[config_key]),
                "source": "api_update"
            }
            
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
                    await handler.handle_change(key, old_value, value, scope)
                except Exception as e:
                    logger.error(f"Error in config change handler: {e}")
            
            # Clear cache
            self._clear_cache_for_key(config_key)
            
            logger.info(f"Configuration updated: {config_key}.{key}")
            return True
            
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