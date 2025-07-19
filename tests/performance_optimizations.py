"""
Performance optimization utilities for test suite.

This module provides optimized fixtures and utilities to improve test execution speed.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Callable, Dict, List
import time


class FastAsyncMock(AsyncMock):
    """Optimized AsyncMock that doesn't introduce unnecessary delays."""
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Pre-configure common return values to avoid computation overhead
        self._fast_returns = {}
    
    async def __call__(self, *args, **kwargs) -> None:
        """Fast async call that returns immediately."""
        # Skip actual async behavior for performance
        return self.return_value


class OptimizedTimeoutMock:
    """Mock for timeout operations that completes immediately."""
    
    def __init__(self, timeout_duration: float = 0.1):
        self.timeout_duration = timeout_duration
        self.call_count = 0
    
    async def __call__(self, *args, **kwargs) -> None:
        """Simulate timeout without actual waiting."""
        self.call_count += 1
        # Immediately raise timeout for performance
        raise asyncio.TimeoutError("Mocked timeout")


class PerformanceOptimizedFixtures:
    """Collection of performance-optimized test fixtures."""
    
    @staticmethod
    @pytest.fixture
    def fast_async_sleep() -> None:
        """Replace asyncio.sleep with immediate return for performance."""
        async def mock_sleep(duration):
            # Don't actually sleep, just return immediately
            pass
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            yield mock_sleep
    
    @staticmethod
    @pytest.fixture
    def optimized_timeout_context() -> None:
        """Provide optimized timeout context for tests."""
        async def fast_timeout(coro, timeout):
            # Immediately raise timeout for performance testing
            raise asyncio.TimeoutError("Fast timeout for testing")
        
        with patch('asyncio.wait_for', side_effect=fast_timeout):
            yield fast_timeout
    
    @staticmethod
    @pytest.fixture
    def batch_async_operations() -> None:
        """Optimize batch async operations for better performance."""
        async def run_batch(operations: List[Callable]):
            # Run operations concurrently for better performance
            tasks = [op() for op in operations if asyncio.iscoroutinefunction(op)]
            if tasks:
                return await asyncio.gather(*tasks, return_exceptions=True)
            return []
        
        return run_batch


class TestExecutionOptimizer:
    """Utilities for optimizing test execution."""
    
    @staticmethod
    def optimize_async_test_setup():
        """Optimize async test setup to reduce overhead."""
        # Configure asyncio for better test performance
        if hasattr(asyncio, 'set_event_loop_policy'):
            # Use faster event loop policy if available
            try:
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                # Fall back to default policy
                pass
    
    @staticmethod
    def create_fast_mock_objects() -> Dict[str, Any]:
        """Create pre-configured mock objects for common use cases."""
        return {
            'fast_bot': FastAsyncMock(),
            'fast_update': FastAsyncMock(),
            'fast_message': FastAsyncMock(),
            'fast_callback_query': FastAsyncMock(),
            'fast_user': FastAsyncMock(),
        }
    
    @staticmethod
    def optimize_fixture_scoping():
        """Recommendations for fixture scoping to improve performance."""
        return {
            'session_fixtures': [
                'database_connection',
                'test_config',
                'mock_services'
            ],
            'module_fixtures': [
                'mock_bot',
                'mock_api_clients'
            ],
            'function_fixtures': [
                'test_data',
                'temporary_files'
            ]
        }


# Performance monitoring utilities
class TestPerformanceMonitor:
    """Monitor and report test performance metrics."""
    
    def __init__(self):
        self.test_times = {}
        self.slow_tests = []
        self.optimization_suggestions = []
    
    def start_test_timer(self, test_name: str):
        """Start timing a test."""
        self.test_times[test_name] = time.time()
    
    def end_test_timer(self, test_name: str):
        """End timing a test and record duration."""
        if test_name in self.test_times:
            duration = time.time() - self.test_times[test_name]
            if duration > 1.0:  # Tests taking more than 1 second
                self.slow_tests.append((test_name, duration))
            return duration
        return 0
    
    def generate_performance_report(self) -> str:
        """Generate a performance optimization report."""
        report = ["Test Performance Optimization Report", "=" * 40]
        
        if self.slow_tests:
            report.append("\nSlow Tests (>1s):")
            for test_name, duration in sorted(self.slow_tests, key=lambda x: x[1], reverse=True):
                report.append(f"  {test_name}: {duration:.2f}s")
        
        report.extend([
            "\nOptimization Recommendations:",
            "1. Replace asyncio.sleep() with mocked immediate returns",
            "2. Use session-scoped fixtures for expensive setup",
            "3. Batch async operations where possible",
            "4. Mock external service calls to avoid network delays",
            "5. Use fast mock objects for common Telegram API objects"
        ])
        
        return "\n".join(report)


# Optimized test patterns
async def run_async_test_with_timeout(test_func, timeout=5.0):
    """Run async test with optimized timeout handling."""
    try:
        return await asyncio.wait_for(test_func(), timeout=timeout)
    except asyncio.TimeoutError:
        pytest.fail(f"Test {test_func.__name__} timed out after {timeout}s")


def optimize_mock_setup(mock_obj, **kwargs):
    """Optimize mock object setup for better performance."""
    # Pre-configure common attributes to avoid runtime overhead
    common_attrs = {
        'id': 12345,
        'username': 'test_user',
        'first_name': 'Test',
        'is_bot': False,
        'chat_id': 67890
    }
    
    for attr, value in {**common_attrs, **kwargs}.items():
        setattr(mock_obj, attr, value)
    
    return mock_obj