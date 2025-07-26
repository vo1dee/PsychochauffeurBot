"""
Async test utilities and patterns for consistent async testing.
This module provides utilities for managing async tests, event loops, and async operations.
"""

import asyncio
import functools
import inspect
import time
from typing import Any, Callable, Coroutine, Optional, Dict, List, Union, TypeVar, Generic
from unittest.mock import AsyncMock, Mock
from contextlib import asynccontextmanager
import pytest
import logging

# Configure logging for async test debugging
logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Event Loop Management
# ============================================================================

class AsyncTestEventLoopManager:
    """Manager for async test event loops with proper isolation."""
    
    def __init__(self):
        self.loop = None
        self.original_policy = None
        
    def setup_event_loop(self) -> asyncio.AbstractEventLoop:
        """Set up event loop for async tests with proper isolation."""
        try:
            # Try to get existing loop first
            self.loop = asyncio.get_running_loop()
            logger.debug("Using existing event loop")
        except RuntimeError:
            # No running loop, create a new one with optimizations
            self.original_policy = asyncio.get_event_loop_policy()
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            logger.debug("Created new event loop")
            
            # Performance optimizations
            if hasattr(self.loop, 'set_debug'):
                self.loop.set_debug(False)  # Disable debug mode for performance
                
        return self.loop
    
    def cleanup_event_loop(self) -> None:
        """Clean up event loop after async tests with comprehensive task cancellation."""
        if not self.loop or self.loop.is_closed():
            return
            
        try:
            # Cancel all pending tasks with timeout
            pending = asyncio.all_tasks(self.loop)
            if pending:
                logger.debug(f"Cancelling {len(pending)} pending tasks")
                for task in pending:
                    if not task.done():
                        task.cancel()
                
                # Wait for tasks to complete cancellation with timeout
                try:
                    self.loop.run_until_complete(
                        asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=2.0  # Reduced timeout for faster cleanup
                        )
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some tasks did not complete cancellation within timeout")
                    # Force cleanup if timeout exceeded
                    pass
            
            # Close the loop if we created it
            if self.original_policy is not None:
                if not self.loop.is_closed():
                    self.loop.close()
                # Restore original policy
                asyncio.set_event_loop_policy(self.original_policy)
                
        except Exception as e:
            logger.error(f"Error during event loop cleanup: {e}")
            # Ignore cleanup errors to prevent test failures
            pass


# ============================================================================
# Async Test Decorators and Wrappers
# ============================================================================

def async_test(timeout: float = 30.0, setup_loop: bool = True):
    """
    Decorator for async test functions with proper event loop management.
    
    Args:
        timeout: Maximum time to wait for test completion
        setup_loop: Whether to set up a new event loop
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            loop_manager = AsyncTestEventLoopManager() if setup_loop else None
            
            try:
                if loop_manager:
                    loop = loop_manager.setup_event_loop()
                else:
                    loop = asyncio.get_event_loop()
                
                # Run the test with timeout
                if asyncio.iscoroutinefunction(func):
                    coro = func(*args, **kwargs)
                    return loop.run_until_complete(
                        asyncio.wait_for(coro, timeout=timeout)
                    )
                else:
                    return func(*args, **kwargs)
                    
            except asyncio.TimeoutError:
                raise AssertionError(f"Async test timed out after {timeout} seconds")
            except Exception as e:
                logger.error(f"Async test failed: {e}")
                raise
            finally:
                if loop_manager:
                    loop_manager.cleanup_event_loop()
                    
        return wrapper
    return decorator


def async_test_case(cls):
    """
    Class decorator to automatically wrap async test methods.
    """
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith('test_') and asyncio.iscoroutinefunction(method):
            setattr(cls, name, async_test()(method))
    return cls


# ============================================================================
# Async Mock Utilities
# ============================================================================

class AsyncMockManager:
    """Manager for creating and configuring async mocks."""
    
    def __init__(self):
        self.created_mocks: List[AsyncMock] = []
        
    def create_async_mock(
        self,
        return_value: Any = None,
        side_effect: Any = None,
        spec: Any = None,
        **kwargs
    ) -> AsyncMock:
        """Create an AsyncMock with standardized configuration."""
        mock = AsyncMock(spec=spec, **kwargs)
        
        if return_value is not None:
            mock.return_value = return_value
            
        if side_effect is not None:
            mock.side_effect = side_effect
            
        self.created_mocks.append(mock)
        return mock
        
    def create_async_context_manager_mock(self, return_value: Any = None) -> AsyncMock:
        """Create an async context manager mock."""
        mock = AsyncMock()
        mock.__aenter__ = AsyncMock(return_value=return_value)
        mock.__aexit__ = AsyncMock(return_value=None)
        self.created_mocks.append(mock)
        return mock
        
    def create_async_iterator_mock(self, items: List[Any]) -> AsyncMock:
        """Create an async iterator mock."""
        async def async_iter():
            for item in items:
                yield item
                
        mock = AsyncMock()
        mock.__aiter__ = AsyncMock(return_value=async_iter())
        self.created_mocks.append(mock)
        return mock
        
    def create_async_callable_mock(
        self,
        return_values: List[Any] = None,
        side_effects: List[Any] = None
    ) -> AsyncMock:
        """Create an async callable mock with multiple return values."""
        if return_values:
            mock = AsyncMock(side_effect=return_values)
        elif side_effects:
            mock = AsyncMock(side_effect=side_effects)
        else:
            mock = AsyncMock()
            
        self.created_mocks.append(mock)
        return mock
        
    def reset_all_mocks(self) -> None:
        """Reset all created mocks."""
        for mock in self.created_mocks:
            mock.reset_mock()
            
    def assert_all_mocks_called(self) -> None:
        """Assert that all created mocks were called."""
        for mock in self.created_mocks:
            mock.assert_called()
            
    def get_mock_call_counts(self) -> Dict[str, int]:
        """Get call counts for all mocks."""
        return {
            f"mock_{i}": mock.call_count
            for i, mock in enumerate(self.created_mocks)
        }


# ============================================================================
# Async Test Patterns
# ============================================================================

class AsyncTestPatterns:
    """Common async test patterns and utilities."""
    
    @staticmethod
    async def run_with_timeout(
        coro: Coroutine,
        timeout: float = 5.0,
        error_message: str = "Operation timed out"
    ) -> Any:
        """Run a coroutine with timeout and custom error message."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"{error_message} (timeout: {timeout}s)")
            
    @staticmethod
    async def run_concurrently(
        *coroutines: Coroutine,
        timeout: float = 10.0,
        return_exceptions: bool = False
    ) -> List[Any]:
        """Run multiple coroutines concurrently."""
        try:
            return await asyncio.wait_for(
                asyncio.gather(*coroutines, return_exceptions=return_exceptions),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise AssertionError(f"Concurrent operations timed out after {timeout}s")
            
    @staticmethod
    async def simulate_delay(
        delay: float = 0.1,
        jitter: float = 0.0
    ) -> None:
        """Simulate async delay with optional jitter."""
        import random
        actual_delay = delay + (random.uniform(-jitter, jitter) if jitter > 0 else 0)
        await asyncio.sleep(max(0, actual_delay))
        
    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        check_interval: float = 0.1,
        error_message: str = "Condition not met"
    ) -> None:
        """Wait for a condition to become true."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition():
                return
            await asyncio.sleep(check_interval)
        raise AssertionError(f"{error_message} (timeout: {timeout}s)")
        
    @staticmethod
    async def assert_async_raises(
        exception_type: type,
        coro: Coroutine,
        match: Optional[str] = None
    ) -> None:
        """Assert that an async operation raises a specific exception."""
        try:
            await coro
            raise AssertionError(f"Expected {exception_type.__name__} to be raised")
        except exception_type as e:
            if match and match not in str(e):
                raise AssertionError(f"Exception message '{str(e)}' does not match '{match}'")
        except Exception as e:
            raise AssertionError(f"Expected {exception_type.__name__}, got {type(e).__name__}: {e}")
            
    @staticmethod
    async def measure_async_performance(
        coro: Coroutine,
        expected_max_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Measure async operation performance."""
        start_time = time.perf_counter()
        try:
            result = await coro
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        
        performance_data = {
            "execution_time": execution_time,
            "success": success,
            "result": result,
            "error": error
        }
        
        if expected_max_time and execution_time > expected_max_time:
            raise AssertionError(
                f"Operation took {execution_time:.4f}s, expected max {expected_max_time}s"
            )
            
        return performance_data


# ============================================================================
# Async Test Context Managers
# ============================================================================

@asynccontextmanager
async def async_test_context(
    setup_coro: Optional[Coroutine] = None,
    teardown_coro: Optional[Coroutine] = None,
    timeout: float = 30.0
):
    """
    Async context manager for test setup and teardown.
    
    Args:
        setup_coro: Optional setup coroutine
        teardown_coro: Optional teardown coroutine
        timeout: Timeout for setup/teardown operations
    """
    try:
        # Setup
        if setup_coro:
            await asyncio.wait_for(setup_coro, timeout=timeout)
        yield
    finally:
        # Teardown
        if teardown_coro:
            try:
                await asyncio.wait_for(teardown_coro, timeout=timeout)
            except Exception as e:
                logger.error(f"Error during async test teardown: {e}")


@asynccontextmanager
async def async_mock_context(*mocks: AsyncMock):
    """Context manager for async mocks with automatic cleanup."""
    try:
        yield mocks if len(mocks) > 1 else mocks[0]
    finally:
        for mock in mocks:
            mock.reset_mock()


# ============================================================================
# Async Test Fixtures and Utilities
# ============================================================================

class AsyncTestFixtures:
    """Collection of async test fixtures."""
    
    @staticmethod
    async def create_async_database_connection() -> AsyncMock:
        """Create a mock async database connection."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.close = AsyncMock()
        
        # Context manager support
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        
        return mock_conn
        
    @staticmethod
    async def create_async_http_client() -> AsyncMock:
        """Create a mock async HTTP client."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"status": "success"})
        mock_response.text = AsyncMock(return_value="response text")
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        
        # Context manager support
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        return mock_client
        
    @staticmethod
    async def create_async_file_handler() -> AsyncMock:
        """Create a mock async file handler."""
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value="file content")
        mock_file.write = AsyncMock()
        mock_file.close = AsyncMock()
        
        # Context manager support
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        
        return mock_file


# ============================================================================
# Async Test Assertions
# ============================================================================

class AsyncAssertions:
    """Async-specific assertion utilities."""
    
    @staticmethod
    async def assert_async_mock_called_with(
        mock: AsyncMock,
        *args,
        timeout: float = 1.0,
        **kwargs
    ) -> None:
        """Assert that an async mock was called with specific arguments."""
        await AsyncTestPatterns.wait_for_condition(
            lambda: mock.called,
            timeout=timeout,
            error_message=f"Mock {mock} was not called within {timeout}s"
        )
        mock.assert_called_with(*args, **kwargs)
        
    @staticmethod
    async def assert_async_mock_awaited(
        mock: AsyncMock,
        timeout: float = 1.0
    ) -> None:
        """Assert that an async mock was awaited."""
        await AsyncTestPatterns.wait_for_condition(
            lambda: mock.await_count > 0,
            timeout=timeout,
            error_message=f"Mock {mock} was not awaited within {timeout}s"
        )
        
    @staticmethod
    async def assert_async_operation_completes(
        coro: Coroutine,
        timeout: float = 5.0
    ) -> Any:
        """Assert that an async operation completes within timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"Async operation did not complete within {timeout}s")
            
    @staticmethod
    async def assert_async_operations_concurrent(
        *coroutines: Coroutine,
        max_total_time: float = None,
        min_concurrency_ratio: float = 0.8
    ) -> List[Any]:
        """Assert that async operations run concurrently."""
        start_time = time.perf_counter()
        
        # Run operations concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Check if operations were truly concurrent
        if max_total_time:
            expected_sequential_time = max_total_time
            concurrency_ratio = expected_sequential_time / total_time
            
            if concurrency_ratio < min_concurrency_ratio:
                raise AssertionError(
                    f"Operations may not have run concurrently. "
                    f"Concurrency ratio: {concurrency_ratio:.2f}, "
                    f"expected >= {min_concurrency_ratio}"
                )
                
        return results


# ============================================================================
# Global Utilities
# ============================================================================

# Global instances for convenience
async_mock_manager = AsyncMockManager()
async_patterns = AsyncTestPatterns()
async_fixtures = AsyncTestFixtures()
async_assertions = AsyncAssertions()


def reset_async_test_state():
    """Reset global async test state."""
    global async_mock_manager
    async_mock_manager.reset_all_mocks()


# Pytest integration
@pytest.fixture
def async_test_manager():
    """Pytest fixture for async test manager."""
    return AsyncTestEventLoopManager()


@pytest.fixture
def async_mock_factory():
    """Pytest fixture for async mock factory."""
    manager = AsyncMockManager()
    yield manager
    manager.reset_all_mocks()


@pytest.fixture
def async_test_patterns():
    """Pytest fixture for async test patterns."""
    return AsyncTestPatterns()


@pytest.fixture
def async_test_fixtures():
    """Pytest fixture for async test fixtures."""
    return AsyncTestFixtures()


@pytest.fixture
def async_assertions():
    """Pytest fixture for async assertions."""
    return AsyncAssertions()