"""
Enhanced reusable mock classes for external services and internal components.
This module provides comprehensive mocks for OpenAI, database, file system, and other services.
"""

import asyncio
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, AsyncGenerator
from unittest.mock import Mock, AsyncMock, MagicMock, PropertyMock
from contextlib import asynccontextmanager

# Import for type hints
from modules.const import KYIV_TZ


# ============================================================================
# Enhanced OpenAI Mock Classes
# ============================================================================

class EnhancedOpenAIMock:
    """Enhanced OpenAI API mock with realistic behavior and error simulation."""
    
    def __init__(self):
        self.responses = []
        self.call_count = 0
        self.error_rate = 0.0
        self.delay_range = (0.1, 0.5)
        self.token_usage = {"prompt": 50, "completion": 25}
        self.model = "gpt-4o-mini"
        
    def set_responses(self, responses: List[str]) -> None:
        """Set predefined responses."""
        self.responses = responses
        
    def set_error_rate(self, rate: float) -> None:
        """Set error rate (0.0 to 1.0)."""
        self.error_rate = rate
        
    def set_delay_range(self, min_delay: float, max_delay: float) -> None:
        """Set response delay range in seconds."""
        self.delay_range = (min_delay, max_delay)
        
    def set_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Set token usage for responses."""
        self.token_usage = {"prompt": prompt_tokens, "completion": completion_tokens}
        
    async def create_completion(self, messages: List[Dict[str, str]], **kwargs) -> Mock:
        """Mock completion creation with realistic behavior."""
        import random
        
        self.call_count += 1
        
        # Simulate delay
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
        
        # Simulate errors
        if random.random() < self.error_rate:
            if random.random() < 0.3:
                raise Exception("Rate limit exceeded")
            elif random.random() < 0.5:
                raise Exception("API key invalid")
            else:
                raise Exception("Service temporarily unavailable")
        
        # Get response
        if self.responses:
            response_text = self.responses[self.call_count % len(self.responses)]
        else:
            response_text = f"Mock response {self.call_count}"
            
        # Create mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = response_text
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].finish_reason = "stop"
        
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = self.token_usage["prompt"]
        mock_response.usage.completion_tokens = self.token_usage["completion"]
        mock_response.usage.total_tokens = sum(self.token_usage.values())
        
        mock_response.model = self.model
        mock_response.id = f"chatcmpl-{self.call_count}"
        mock_response.created = int(datetime.now().timestamp())
        
        return mock_response
    
    def create_client_mock(self) -> Mock:
        """Create a mock OpenAI client."""
        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = AsyncMock(side_effect=self.create_completion)
        return mock_client


# ============================================================================
# Enhanced Database Mock Classes
# ============================================================================

class EnhancedDatabaseMock:
    """Enhanced database mock with realistic behavior and data persistence."""
    
    def __init__(self):
        self.data = {}
        self.connection_pool = []
        self.transaction_active = False
        self.query_count = 0
        self.error_rate = 0.0
        self.delay_range = (0.01, 0.05)
        
    def set_error_rate(self, rate: float) -> None:
        """Set database error rate."""
        self.error_rate = rate
        
    def set_delay_range(self, min_delay: float, max_delay: float) -> None:
        """Set query delay range."""
        self.delay_range = (min_delay, max_delay)
        
    def seed_data(self, table: str, records: List[Dict[str, Any]]) -> None:
        """Seed test data into a table."""
        if table not in self.data:
            self.data[table] = []
        self.data[table].extend(records)
        
    def clear_data(self, table: Optional[str] = None) -> None:
        """Clear data from table or all tables."""
        if table:
            self.data[table] = []
        else:
            self.data.clear()
            
    async def _simulate_query_delay(self) -> None:
        """Simulate realistic query delay."""
        import random
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
        
    async def _check_for_errors(self) -> None:
        """Check if we should simulate an error."""
        import random
        if random.random() < self.error_rate:
            error_types = [
                "Connection lost",
                "Query timeout",
                "Table does not exist",
                "Constraint violation",
                "Deadlock detected"
            ]
            raise Exception(random.choice(error_types))
            
    async def execute(self, query: str, *params) -> None:
        """Mock execute method."""
        self.query_count += 1
        await self._simulate_query_delay()
        await self._check_for_errors()
        
        # Simple query parsing for INSERT/UPDATE/DELETE
        query_lower = query.lower().strip()
        if query_lower.startswith('insert'):
            # Mock insert behavior
            pass
        elif query_lower.startswith('update'):
            # Mock update behavior
            pass
        elif query_lower.startswith('delete'):
            # Mock delete behavior
            pass
            
    async def fetch(self, query: str, *params) -> List[Dict[str, Any]]:
        """Mock fetch method."""
        self.query_count += 1
        await self._simulate_query_delay()
        await self._check_for_errors()
        
        # Simple query parsing for SELECT
        query_lower = query.lower().strip()
        if 'from' in query_lower:
            # Extract table name (very basic parsing)
            parts = query_lower.split()
            try:
                from_index = parts.index('from')
                if from_index + 1 < len(parts):
                    table = parts[from_index + 1]
                    return self.data.get(table, [])
            except (ValueError, IndexError):
                pass
                
        return []
        
    async def fetchrow(self, query: str, *params) -> Optional[Dict[str, Any]]:
        """Mock fetchrow method."""
        results = await self.fetch(query, *params)
        return results[0] if results else None
        
    async def fetchval(self, query: str, *params) -> Any:
        """Mock fetchval method."""
        row = await self.fetchrow(query, *params)
        if row:
            return list(row.values())[0]
        return None
        
    @asynccontextmanager
    async def transaction(self):
        """Mock transaction context manager."""
        self.transaction_active = True
        try:
            yield self
        except Exception:
            # Rollback
            self.transaction_active = False
            raise
        else:
            # Commit
            self.transaction_active = False
            
    def create_connection_mock(self) -> Mock:
        """Create a mock database connection."""
        mock_conn = Mock()
        mock_conn.execute = AsyncMock(side_effect=self.execute)
        mock_conn.fetch = AsyncMock(side_effect=self.fetch)
        mock_conn.fetchrow = AsyncMock(side_effect=self.fetchrow)
        mock_conn.fetchval = AsyncMock(side_effect=self.fetchval)
        mock_conn.transaction = self.transaction
        return mock_conn
        
    def create_pool_mock(self) -> Mock:
        """Create a mock database pool."""
        mock_pool = Mock()
        
        @asynccontextmanager
        async def acquire():
            yield self.create_connection_mock()
            
        mock_pool.acquire = acquire
        mock_pool.close = AsyncMock()
        mock_pool.wait_closed = AsyncMock()
        return mock_pool


# ============================================================================
# Enhanced File System Mock Classes
# ============================================================================

class EnhancedFileSystemMock:
    """Enhanced file system mock with realistic behavior."""
    
    def __init__(self):
        self.files = {}
        self.directories = set()
        self.permissions = {}
        self.error_rate = 0.0
        self.delay_range = (0.001, 0.01)
        
    def set_error_rate(self, rate: float) -> None:
        """Set file operation error rate."""
        self.error_rate = rate
        
    def set_delay_range(self, min_delay: float, max_delay: float) -> None:
        """Set file operation delay range."""
        self.delay_range = (min_delay, max_delay)
        
    def create_file(self, path: str, content: str = "", permissions: str = "rw") -> None:
        """Create a mock file."""
        self.files[path] = content
        self.permissions[path] = permissions
        
        # Create parent directories
        parent = str(Path(path).parent)
        if parent != path:
            self.directories.add(parent)
            
    def create_directory(self, path: str, permissions: str = "rwx") -> None:
        """Create a mock directory."""
        self.directories.add(path)
        self.permissions[path] = permissions
        
    async def _simulate_io_delay(self) -> None:
        """Simulate realistic I/O delay."""
        import random
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
        
    async def _check_for_errors(self, operation: str) -> None:
        """Check if we should simulate an error."""
        import random
        if random.random() < self.error_rate:
            error_types = {
                "read": [FileNotFoundError("File not found"), PermissionError("Permission denied")],
                "write": [PermissionError("Permission denied"), OSError("Disk full")],
                "delete": [FileNotFoundError("File not found"), PermissionError("Permission denied")]
            }
            errors = error_types.get(operation, [OSError("I/O error")])
            raise random.choice(errors)
            
    async def read_file(self, path: str) -> str:
        """Mock file reading."""
        await self._simulate_io_delay()
        await self._check_for_errors("read")
        
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
            
        if "r" not in self.permissions.get(path, ""):
            raise PermissionError(f"Permission denied: {path}")
            
        return self.files[path]
        
    async def write_file(self, path: str, content: str) -> None:
        """Mock file writing."""
        await self._simulate_io_delay()
        await self._check_for_errors("write")
        
        if path in self.files and "w" not in self.permissions.get(path, ""):
            raise PermissionError(f"Permission denied: {path}")
            
        self.files[path] = content
        if path not in self.permissions:
            self.permissions[path] = "rw"
            
    async def delete_file(self, path: str) -> None:
        """Mock file deletion."""
        await self._simulate_io_delay()
        await self._check_for_errors("delete")
        
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
            
        if "w" not in self.permissions.get(path, ""):
            raise PermissionError(f"Permission denied: {path}")
            
        del self.files[path]
        if path in self.permissions:
            del self.permissions[path]
            
    def exists(self, path: str) -> bool:
        """Check if file or directory exists."""
        return path in self.files or path in self.directories
        
    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return path in self.files
        
    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        return path in self.directories
        
    def list_directory(self, path: str) -> List[str]:
        """List directory contents."""
        if path not in self.directories:
            raise FileNotFoundError(f"Directory not found: {path}")
            
        contents = []
        for file_path in self.files:
            if str(Path(file_path).parent) == path:
                contents.append(Path(file_path).name)
                
        for dir_path in self.directories:
            if str(Path(dir_path).parent) == path:
                contents.append(Path(dir_path).name)
                
        return contents
        
    def create_pathlib_mock(self) -> Mock:
        """Create a mock pathlib.Path object."""
        mock_path = Mock()
        mock_path.exists = Mock(side_effect=self.exists)
        mock_path.is_file = Mock(side_effect=self.is_file)
        mock_path.is_dir = Mock(side_effect=self.is_directory)
        mock_path.read_text = AsyncMock(side_effect=self.read_file)
        mock_path.write_text = AsyncMock(side_effect=self.write_file)
        mock_path.unlink = AsyncMock(side_effect=self.delete_file)
        mock_path.iterdir = Mock(side_effect=self.list_directory)
        return mock_path


# ============================================================================
# Enhanced Configuration Manager Mock
# ============================================================================

class EnhancedConfigManagerMock:
    """Enhanced configuration manager mock with realistic behavior."""
    
    def __init__(self):
        self.configs = {}
        self.schemas = {}
        self.validation_enabled = True
        self.backup_enabled = True
        self.change_history = []
        
    def set_validation_enabled(self, enabled: bool) -> None:
        """Enable or disable validation."""
        self.validation_enabled = enabled
        
    def set_backup_enabled(self, enabled: bool) -> None:
        """Enable or disable backups."""
        self.backup_enabled = enabled
        
    def load_config(self, config_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load configuration."""
        config = self.configs.get(config_id, default or {})
        self.change_history.append({
            "action": "load",
            "config_id": config_id,
            "timestamp": datetime.now(timezone.utc)
        })
        return config
        
    async def save_config(self, config_id: str, config: Dict[str, Any]) -> bool:
        """Save configuration."""
        if self.validation_enabled:
            await self._validate_config(config_id, config)
            
        if self.backup_enabled:
            await self._create_backup(config_id)
            
        self.configs[config_id] = config.copy()
        self.change_history.append({
            "action": "save",
            "config_id": config_id,
            "timestamp": datetime.now(timezone.utc)
        })
        return True
        
    async def update_config(self, config_id: str, updates: Dict[str, Any]) -> bool:
        """Update configuration."""
        current_config = self.configs.get(config_id, {})
        updated_config = {**current_config, **updates}
        return await self.save_config(config_id, updated_config)
        
    async def delete_config(self, config_id: str) -> bool:
        """Delete configuration."""
        if config_id in self.configs:
            if self.backup_enabled:
                await self._create_backup(config_id)
            del self.configs[config_id]
            self.change_history.append({
                "action": "delete",
                "config_id": config_id,
                "timestamp": datetime.now(timezone.utc)
            })
            return True
        return False
        
    def list_configs(self) -> List[str]:
        """List all configuration IDs."""
        return list(self.configs.keys())
        
    async def _validate_config(self, config_id: str, config: Dict[str, Any]) -> None:
        """Validate configuration against schema."""
        schema = self.schemas.get(config_id)
        if schema:
            # Simple validation - check required fields
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Required field '{field}' missing in config")
                    
    async def _create_backup(self, config_id: str) -> None:
        """Create configuration backup."""
        # Mock backup creation
        pass
        
    def create_mock(self) -> Mock:
        """Create a mock configuration manager."""
        mock_config = Mock()
        mock_config.initialize = AsyncMock()
        mock_config.load_config = Mock(side_effect=self.load_config)
        mock_config.save_config = AsyncMock(side_effect=self.save_config)
        mock_config.update_config = AsyncMock(side_effect=self.update_config)
        mock_config.delete_config = AsyncMock(side_effect=self.delete_config)
        mock_config.list_configs = Mock(side_effect=self.list_configs)
        return mock_config


# ============================================================================
# Enhanced Security Validator Mock
# ============================================================================

class EnhancedSecurityValidatorMock:
    """Enhanced security validator mock with realistic validation."""
    
    def __init__(self):
        self.validation_rules = {
            "sql_injection": [
                "select", "insert", "update", "delete", "drop", "union",
                "exec", "execute", "sp_", "xp_", "script"
            ],
            "xss": [
                "<script", "</script>", "javascript:", "onload=", "onerror=",
                "onclick=", "onmouseover=", "eval(", "alert("
            ],
            "path_traversal": [
                "../", "..\\", "/etc/", "\\windows\\", "~/"
            ]
        }
        self.blocked_extensions = [".exe", ".bat", ".cmd", ".scr", ".vbs", ".js"]
        self.max_input_length = 10000
        self.rate_limits = {}
        
    def validate_input(self, input_text: str, validation_type: str = "general") -> Dict[str, Any]:
        """Validate input text."""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "sanitized": input_text
        }
        
        # Length check
        if len(input_text) > self.max_input_length:
            result["valid"] = False
            result["errors"].append(f"Input too long (max {self.max_input_length} characters)")
            
        # SQL injection check
        input_lower = input_text.lower()
        for pattern in self.validation_rules["sql_injection"]:
            if pattern in input_lower:
                result["valid"] = False
                result["errors"].append(f"Potential SQL injection detected: {pattern}")
                
        # XSS check
        for pattern in self.validation_rules["xss"]:
            if pattern.lower() in input_lower:
                result["valid"] = False
                result["errors"].append(f"Potential XSS detected: {pattern}")
                
        # Path traversal check
        for pattern in self.validation_rules["path_traversal"]:
            if pattern in input_text:
                result["valid"] = False
                result["errors"].append(f"Potential path traversal detected: {pattern}")
                
        return result
        
    def validate_file(self, filename: str, content: bytes = b"") -> Dict[str, Any]:
        """Validate file upload."""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Extension check
        file_ext = Path(filename).suffix.lower()
        if file_ext in self.blocked_extensions:
            result["valid"] = False
            result["errors"].append(f"File type not allowed: {file_ext}")
            
        # Size check (mock - 10MB limit)
        if len(content) > 10 * 1024 * 1024:
            result["valid"] = False
            result["errors"].append("File too large (max 10MB)")
            
        return result
        
    def check_rate_limit(self, user_id: int, action: str, limit: int = 10, window: int = 60) -> Dict[str, Any]:
        """Check rate limiting."""
        now = datetime.now(timezone.utc)
        key = f"{user_id}:{action}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
            
        # Clean old entries
        cutoff = now - timedelta(seconds=window)
        self.rate_limits[key] = [
            timestamp for timestamp in self.rate_limits[key]
            if timestamp > cutoff
        ]
        
        # Check limit
        if len(self.rate_limits[key]) >= limit:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": self.rate_limits[key][0] + timedelta(seconds=window)
            }
            
        # Add current request
        self.rate_limits[key].append(now)
        
        return {
            "allowed": True,
            "remaining": limit - len(self.rate_limits[key]),
            "reset_time": now + timedelta(seconds=window)
        }
        
    def create_mock(self) -> Mock:
        """Create a mock security validator."""
        mock_validator = Mock()
        mock_validator.validate_input = Mock(side_effect=self.validate_input)
        mock_validator.validate_file = Mock(side_effect=self.validate_file)
        mock_validator.check_rate_limit = Mock(side_effect=self.check_rate_limit)
        return mock_validator


# ============================================================================
# Mock Registry for Managing All Mocks
# ============================================================================

class EnhancedMockRegistry:
    """Registry for managing all enhanced mocks."""
    
    def __init__(self):
        self.mocks = {}
        self.openai_mock = EnhancedOpenAIMock()
        self.database_mock = EnhancedDatabaseMock()
        self.filesystem_mock = EnhancedFileSystemMock()
        self.config_mock = EnhancedConfigManagerMock()
        self.security_mock = EnhancedSecurityValidatorMock()
        
    def get_openai_mock(self) -> EnhancedOpenAIMock:
        """Get OpenAI mock."""
        return self.openai_mock
        
    def get_database_mock(self) -> EnhancedDatabaseMock:
        """Get database mock."""
        return self.database_mock
        
    def get_filesystem_mock(self) -> EnhancedFileSystemMock:
        """Get file system mock."""
        return self.filesystem_mock
        
    def get_config_mock(self) -> EnhancedConfigManagerMock:
        """Get configuration manager mock."""
        return self.config_mock
        
    def get_security_mock(self) -> EnhancedSecurityValidatorMock:
        """Get security validator mock."""
        return self.security_mock
        
    def reset_all_mocks(self) -> None:
        """Reset all mocks to initial state."""
        self.openai_mock = EnhancedOpenAIMock()
        self.database_mock = EnhancedDatabaseMock()
        self.filesystem_mock = EnhancedFileSystemMock()
        self.config_mock = EnhancedConfigManagerMock()
        self.security_mock = EnhancedSecurityValidatorMock()
        
    def configure_for_testing(self, scenario: str = "default") -> None:
        """Configure mocks for specific testing scenarios."""
        if scenario == "error_prone":
            self.openai_mock.set_error_rate(0.2)
            self.database_mock.set_error_rate(0.1)
            self.filesystem_mock.set_error_rate(0.1)
        elif scenario == "slow_network":
            self.openai_mock.set_delay_range(1.0, 3.0)
            self.database_mock.set_delay_range(0.1, 0.5)
        elif scenario == "fast":
            self.openai_mock.set_delay_range(0.01, 0.05)
            self.database_mock.set_delay_range(0.001, 0.01)
            self.filesystem_mock.set_delay_range(0.001, 0.005)


# Global registry instance
mock_registry = EnhancedMockRegistry()