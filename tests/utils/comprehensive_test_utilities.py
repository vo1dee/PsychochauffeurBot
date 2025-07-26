"""
Comprehensive test utilities that integrate all enhanced testing components.
This module provides a unified interface for all testing utilities.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Union, Callable
from unittest.mock import Mock, AsyncMock
from contextlib import asynccontextmanager

# Import all enhanced components
from tests.mocks.enhanced_mocks import (
    EnhancedOpenAIMock, EnhancedDatabaseMock, EnhancedFileSystemMock,
    EnhancedConfigManagerMock, EnhancedSecurityValidatorMock, mock_registry
)
from tests.utils.async_test_utilities import (
    AsyncTestEventLoopManager, AsyncMockManager, AsyncTestPatterns,
    AsyncTestFixtures, AsyncAssertions
)


class ComprehensiveTestUtilities:
    """
    Unified interface for all enhanced testing utilities.
    This class provides a single entry point for all testing needs.
    """
    
    def __init__(self):
        self.mock_registry = mock_registry
        self.async_manager = AsyncTestEventLoopManager()
        self.async_mock_manager = AsyncMockManager()
        self.async_patterns = AsyncTestPatterns()
        self.async_fixtures = AsyncTestFixtures()
        self.async_assertions = AsyncAssertions()
        
    # ========================================================================
    # Mock Management
    # ========================================================================
    
    def get_openai_mock(self) -> EnhancedOpenAIMock:
        """Get enhanced OpenAI mock."""
        return self.mock_registry.get_openai_mock()
        
    def get_database_mock(self) -> EnhancedDatabaseMock:
        """Get enhanced database mock."""
        return self.mock_registry.get_database_mock()
        
    def get_filesystem_mock(self) -> EnhancedFileSystemMock:
        """Get enhanced file system mock."""
        return self.mock_registry.get_filesystem_mock()
        
    def get_config_mock(self) -> EnhancedConfigManagerMock:
        """Get enhanced configuration manager mock."""
        return self.mock_registry.get_config_mock()
        
    def get_security_mock(self) -> EnhancedSecurityValidatorMock:
        """Get enhanced security validator mock."""
        return self.mock_registry.get_security_mock()
        
    def configure_test_scenario(self, scenario: str = "default") -> None:
        """Configure all mocks for a specific test scenario."""
        self.mock_registry.configure_for_testing(scenario)
        
    def reset_all_mocks(self) -> None:
        """Reset all mocks to initial state."""
        self.mock_registry.reset_all_mocks()
        self.async_mock_manager.reset_all_mocks()
        
    # ========================================================================
    # Async Test Management
    # ========================================================================
    
    def setup_async_environment(self) -> asyncio.AbstractEventLoop:
        """Set up async test environment."""
        return self.async_manager.setup_event_loop()
        
    def cleanup_async_environment(self) -> None:
        """Clean up async test environment."""
        self.async_manager.cleanup_event_loop()
        
    def create_async_mock(self, **kwargs) -> AsyncMock:
        """Create an async mock with standard configuration."""
        return self.async_mock_manager.create_async_mock(**kwargs)
        
    async def run_with_timeout(self, coro, timeout: float = 5.0) -> Any:
        """Run coroutine with timeout."""
        return await self.async_patterns.run_with_timeout(coro, timeout)
        
    async def run_concurrently(self, *coroutines, timeout: float = 10.0) -> List[Any]:
        """Run multiple coroutines concurrently."""
        return await self.async_patterns.run_concurrently(*coroutines, timeout=timeout)
        
    async def assert_async_operation_completes(self, coro, timeout: float = 5.0) -> Any:
        """Assert that async operation completes within timeout."""
        return await self.async_assertions.assert_async_operation_completes(coro, timeout)
        
    # ========================================================================
    # Test Data Management
    # ========================================================================
    
    def seed_database_data(self, table: str, records: List[Dict[str, Any]]) -> None:
        """Seed data into database mock."""
        db_mock = self.get_database_mock()
        db_mock.seed_data(table, records)
        
    def create_filesystem_structure(self, structure: Dict[str, Any]) -> None:
        """Create file system structure in mock."""
        fs_mock = self.get_filesystem_mock()
        
        def create_structure(path_prefix: str, items: Dict[str, Any]):
            for name, content in items.items():
                full_path = f"{path_prefix}/{name}" if path_prefix else name
                
                if isinstance(content, dict):
                    # Directory
                    fs_mock.create_directory(full_path)
                    create_structure(full_path, content)
                else:
                    # File
                    fs_mock.create_file(full_path, str(content))
                    
        create_structure("", structure)
        
    def setup_config_data(self, configs: Dict[str, Dict[str, Any]]) -> None:
        """Set up configuration data in mock."""
        config_mock = self.get_config_mock()
        for config_id, config_data in configs.items():
            config_mock.configs[config_id] = config_data
            
    # ========================================================================
    # Performance Testing
    # ========================================================================
    
    async def measure_performance(
        self,
        operation: Callable,
        *args,
        expected_max_time: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Measure operation performance."""
        if asyncio.iscoroutinefunction(operation):
            coro = operation(*args, **kwargs)
            return await self.async_patterns.measure_async_performance(
                coro, expected_max_time
            )
        else:
            start_time = time.perf_counter()
            try:
                result = operation(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
            end_time = time.perf_counter()
            
            execution_time = end_time - start_time
            
            if expected_max_time and execution_time > expected_max_time:
                raise AssertionError(
                    f"Operation took {execution_time:.4f}s, expected max {expected_max_time}s"
                )
                
            return {
                "execution_time": execution_time,
                "success": success,
                "result": result,
                "error": error
            }
            
    # ========================================================================
    # Error Testing
    # ========================================================================
    
    def inject_errors(self, error_config: Dict[str, Any]) -> None:
        """Inject errors into various components for testing."""
        if "openai" in error_config:
            openai_mock = self.get_openai_mock()
            openai_mock.set_error_rate(error_config["openai"].get("rate", 0.5))
            
        if "database" in error_config:
            db_mock = self.get_database_mock()
            db_mock.set_error_rate(error_config["database"].get("rate", 0.5))
            
        if "filesystem" in error_config:
            fs_mock = self.get_filesystem_mock()
            fs_mock.set_error_rate(error_config["filesystem"].get("rate", 0.5))
            
    def clear_all_errors(self) -> None:
        """Clear all injected errors."""
        self.get_openai_mock().set_error_rate(0.0)
        self.get_database_mock().set_error_rate(0.0)
        self.get_filesystem_mock().set_error_rate(0.0)
        
    # ========================================================================
    # Integration Testing
    # ========================================================================
    
    @asynccontextmanager
    async def integration_test_context(
        self,
        scenario: str = "default",
        database_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        filesystem_structure: Optional[Dict[str, Any]] = None,
        config_data: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """Context manager for integration tests with full setup."""
        try:
            # Setup
            self.configure_test_scenario(scenario)
            
            if database_data:
                for table, records in database_data.items():
                    self.seed_database_data(table, records)
                    
            if filesystem_structure:
                self.create_filesystem_structure(filesystem_structure)
                
            if config_data:
                self.setup_config_data(config_data)
                
            yield self
            
        finally:
            # Cleanup
            self.reset_all_mocks()
            self.clear_all_errors()
            
    # ========================================================================
    # Validation and Assertions
    # ========================================================================
    
    def validate_mock_interactions(self) -> Dict[str, Any]:
        """Validate that mocks were used correctly."""
        validation_results = {
            "openai_calls": self.get_openai_mock().call_count,
            "database_queries": self.get_database_mock().query_count,
            "async_mock_calls": self.async_mock_manager.get_mock_call_counts(),
            "validation_passed": True,
            "issues": []
        }
        
        # Add validation logic here as needed
        
        return validation_results
        
    async def assert_system_behavior(
        self,
        operation: Callable,
        expected_behavior: Dict[str, Any],
        *args,
        **kwargs
    ) -> None:
        """Assert that system behaves as expected."""
        # Run operation
        if asyncio.iscoroutinefunction(operation):
            result = await operation(*args, **kwargs)
        else:
            result = operation(*args, **kwargs)
            
        # Validate behavior
        if "result" in expected_behavior:
            assert result == expected_behavior["result"], (
                f"Expected result {expected_behavior['result']}, got {result}"
            )
            
        if "openai_called" in expected_behavior:
            openai_mock = self.get_openai_mock()
            if expected_behavior["openai_called"]:
                assert openai_mock.call_count > 0, "Expected OpenAI to be called"
            else:
                assert openai_mock.call_count == 0, "Expected OpenAI not to be called"
                
        if "database_queries" in expected_behavior:
            db_mock = self.get_database_mock()
            expected_queries = expected_behavior["database_queries"]
            assert db_mock.query_count == expected_queries, (
                f"Expected {expected_queries} database queries, got {db_mock.query_count}"
            )
            
    # ========================================================================
    # Convenience Methods
    # ========================================================================
    
    def quick_setup(
        self,
        scenario: str = "default",
        with_database: bool = True,
        with_filesystem: bool = True,
        with_config: bool = True
    ) -> Dict[str, Any]:
        """Quick setup for common test scenarios."""
        self.configure_test_scenario(scenario)
        
        components = {}
        
        if with_database:
            components["database"] = self.get_database_mock()
            
        if with_filesystem:
            components["filesystem"] = self.get_filesystem_mock()
            
        if with_config:
            components["config"] = self.get_config_mock()
            
        components["openai"] = self.get_openai_mock()
        components["security"] = self.get_security_mock()
        
        return components
        
    def create_test_suite_context(self) -> Dict[str, Any]:
        """Create a comprehensive test suite context."""
        return {
            "utils": self,
            "mocks": {
                "openai": self.get_openai_mock(),
                "database": self.get_database_mock(),
                "filesystem": self.get_filesystem_mock(),
                "config": self.get_config_mock(),
                "security": self.get_security_mock()
            },
            "async_utils": {
                "patterns": self.async_patterns,
                "fixtures": self.async_fixtures,
                "assertions": self.async_assertions,
                "mock_manager": self.async_mock_manager
            }
        }


# ============================================================================
# Global Instance and Convenience Functions
# ============================================================================

# Global instance for easy access
test_utils = ComprehensiveTestUtilities()


def get_test_utils() -> ComprehensiveTestUtilities:
    """Get the global test utilities instance."""
    return test_utils


def quick_test_setup(scenario: str = "default", **kwargs) -> Dict[str, Any]:
    """Quick test setup with default configuration."""
    return test_utils.quick_setup(scenario, **kwargs)


async def run_integration_test(
    test_func: Callable,
    scenario: str = "default",
    **setup_kwargs
) -> Any:
    """Run an integration test with full setup."""
    async with test_utils.integration_test_context(scenario, **setup_kwargs):
        if asyncio.iscoroutinefunction(test_func):
            return await test_func(test_utils)
        else:
            return test_func(test_utils)


def reset_test_environment() -> None:
    """Reset the entire test environment."""
    test_utils.reset_all_mocks()
    test_utils.clear_all_errors()
    test_utils.cleanup_async_environment()


# ============================================================================
# Pytest Integration
# ============================================================================

import pytest

@pytest.fixture
def comprehensive_test_utils() -> ComprehensiveTestUtilities:
    """Pytest fixture for comprehensive test utilities."""
    utils = ComprehensiveTestUtilities()
    yield utils
    utils.reset_all_mocks()
    utils.clear_all_errors()


@pytest.fixture
def quick_setup(comprehensive_test_utils: ComprehensiveTestUtilities):
    """Pytest fixture for quick test setup."""
    def _setup(scenario: str = "default", **kwargs):
        return comprehensive_test_utils.quick_setup(scenario, **kwargs)
    return _setup


@pytest.fixture
async def integration_context(comprehensive_test_utils: ComprehensiveTestUtilities):
    """Pytest fixture for integration test context."""
    def _context(**kwargs):
        return comprehensive_test_utils.integration_test_context(**kwargs)
    return _context