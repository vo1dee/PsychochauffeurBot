"""
Enhanced pytest configuration with comprehensive fixtures and utilities.
This module integrates all the enhanced test infrastructure components.
"""

import pytest
import asyncio
from typing import Dict, Any, Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock

# Import enhanced components
from tests.mocks.enhanced_mocks import mock_registry, EnhancedMockRegistry
from tests.utils.async_test_utilities import (
    AsyncTestEventLoopManager, AsyncMockManager, AsyncTestPatterns,
    AsyncTestFixtures, AsyncAssertions
)
from tests.utils.comprehensive_test_utilities import ComprehensiveTestUtilities


# ============================================================================
# Enhanced Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def enhanced_event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Enhanced event loop with better performance and cleanup."""
    loop_manager = AsyncTestEventLoopManager()
    loop = loop_manager.setup_event_loop()
    
    yield loop
    
    loop_manager.cleanup_event_loop()


@pytest.fixture(autouse=True)
def ensure_enhanced_event_loop():
    """Automatically ensure enhanced event loop is available for all tests."""
    loop_manager = AsyncTestEventLoopManager()
    loop = loop_manager.setup_event_loop()
    
    yield loop
    
    # Cleanup after each test
    loop_manager.cleanup_event_loop()


# ============================================================================
# Enhanced Mock Registry Fixtures
# ============================================================================

@pytest.fixture
def enhanced_mock_registry() -> Generator[EnhancedMockRegistry, None, None]:
    """Provide access to the enhanced mock registry."""
    # Reset registry to clean state
    mock_registry.reset_all_mocks()
    yield mock_registry
    # Cleanup after test
    mock_registry.reset_all_mocks()


@pytest.fixture
def openai_mock(enhanced_mock_registry: EnhancedMockRegistry):
    """Enhanced OpenAI mock with realistic behavior."""
    return enhanced_mock_registry.get_openai_mock()


@pytest.fixture
def database_mock(enhanced_mock_registry: EnhancedMockRegistry):
    """Enhanced database mock with data persistence."""
    return enhanced_mock_registry.get_database_mock()


@pytest.fixture
def filesystem_mock(enhanced_mock_registry: EnhancedMockRegistry):
    """Enhanced file system mock."""
    return enhanced_mock_registry.get_filesystem_mock()


@pytest.fixture
def config_mock(enhanced_mock_registry: EnhancedMockRegistry):
    """Enhanced configuration manager mock."""
    return enhanced_mock_registry.get_config_mock()


@pytest.fixture
def security_mock(enhanced_mock_registry: EnhancedMockRegistry):
    """Enhanced security validator mock."""
    return enhanced_mock_registry.get_security_mock()


# ============================================================================
# Enhanced Async Test Utilities
# ============================================================================

@pytest.fixture
def async_mock_manager() -> Generator[AsyncMockManager, None, None]:
    """Async mock manager for creating and managing async mocks."""
    manager = AsyncMockManager()
    yield manager
    manager.reset_all_mocks()


@pytest.fixture
def async_test_patterns() -> AsyncTestPatterns:
    """Async test patterns and utilities."""
    return AsyncTestPatterns()


@pytest.fixture
def async_test_fixtures() -> AsyncTestFixtures:
    """Async test fixtures."""
    return AsyncTestFixtures()


@pytest.fixture
def async_assertions() -> AsyncAssertions:
    """Async assertion utilities."""
    return AsyncAssertions()


# ============================================================================
# Comprehensive Test Utilities
# ============================================================================

@pytest.fixture
def comprehensive_test_utils() -> Generator[ComprehensiveTestUtilities, None, None]:
    """Comprehensive test utilities fixture."""
    utils = ComprehensiveTestUtilities()
    yield utils
    utils.reset_all_mocks()
    utils.clear_all_errors()


# ============================================================================
# Enhanced Test Scenarios
# ============================================================================

@pytest.fixture(params=["default", "error_prone", "slow_network", "fast"])
def test_scenario(request, enhanced_mock_registry: EnhancedMockRegistry) -> str:
    """Parametrized test scenarios."""
    scenario = request.param
    enhanced_mock_registry.configure_for_testing(scenario)
    return scenario


# ============================================================================
# Enhanced Pytest Markers
# ============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "async_test: mark test as async test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "external_service: mark test as requiring external services"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database"
    )
    config.addinivalue_line(
        "markers", "filesystem: mark test as requiring file system operations"
    )