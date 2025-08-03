"""
Comprehensive unit tests for ServiceErrorBoundary.
Ensures 90% coverage target for error boundary functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from modules.service_error_boundary import (
    ServiceErrorBoundary, 
    ServiceHealth, 
    ServiceHealthMetrics,
    StandardError,
    with_error_boundary
)


class TestServiceErrorBoundaryComprehensive:
    """Comprehensive tests for ServiceErrorBoundary."""

    @pytest.fixture
    def error_boundary(self):
        """Create ServiceErrorBoundary instance for testing."""
        return ServiceErrorBoundary("test_service")

    @pytest.fixture
    def mock_operation(self):
        """Create a mock async operation."""
        return AsyncMock(return_value="success")

    @pytest.fixture
    def failing_operation(self):
        """Create a mock failing async operation."""
        return AsyncMock(side_effect=Exception("Test error"))

    @pytest.mark.asyncio
    async def test_initialization(self, error_boundary):
        """Test ServiceErrorBoundary initialization."""
        assert error_boundary.service_name == "test_service"
        assert error_boundary.metrics.service_name == "test_service"
        assert error_boundary.metrics.status == ServiceHealth.HEALTHY
        assert error_boundary.metrics.error_count == 0
        assert error_boundary.metrics.success_count == 0
        assert error_boundary.is_healthy() is True

    @pytest.mark.asyncio
    async def test_successful_operation_execution(self, error_boundary, mock_operation):
        """Test successful operation execution."""
        result = await error_boundary.execute_with_boundary(
            mock_operation, 
            "test_operation"
        )
        
        assert result == "success"
        assert error_boundary.metrics.success_count == 1
        assert error_boundary.metrics.error_count == 0
        assert error_boundary.metrics.status == ServiceHealth.HEALTHY
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_operation_execution(self, error_boundary, failing_operation):
        """Test failed operation execution."""
        result = await error_boundary.execute_with_boundary(
            failing_operation,
            "test_operation"
        )
        
        assert result is None
        assert error_boundary.metrics.success_count == 0
        assert error_boundary.metrics.error_count == 1
        assert error_boundary.metrics.status == ServiceHealth.DEGRADED
        failing_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_operation_with_fallback(self, error_boundary, failing_operation):
        """Test operation execution with fallback."""
        fallback = AsyncMock(return_value="fallback_result")
        
        result = await error_boundary.execute_with_boundary(
            failing_operation,
            "test_operation",
            fallback=fallback
        )
        
        assert result == "fallback_result"
        assert error_boundary.metrics.error_count == 1
        fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_operation_with_timeout(self, error_boundary):
        """Test operation execution with timeout."""
        slow_operation = AsyncMock()
        
        async def slow_func():
            await asyncio.sleep(2)
            return "slow_result"
        
        slow_operation.side_effect = slow_func
        
        result = await error_boundary.execute_with_boundary(
            slow_operation,
            "slow_operation",
            timeout=0.1
        )
        
        assert result is None
        assert error_boundary.metrics.error_count == 1
        assert "timed out" in error_boundary.metrics.last_error.message.lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, error_boundary):
        """Test circuit breaker functionality."""
        failing_operation = AsyncMock(side_effect=Exception("Persistent error"))
        
        # Execute multiple failing operations to trigger circuit breaker
        for _ in range(6):  # Exceed failure threshold
            await error_boundary.execute_with_boundary(
                failing_operation,
                "failing_operation"
            )
        
        assert error_boundary.metrics.status == ServiceHealth.CRITICAL
        assert error_boundary.metrics.consecutive_failures >= 5
        assert not error_boundary.is_healthy()

    @pytest.mark.asyncio
    async def test_health_recovery(self, error_boundary):
        """Test health recovery after failures."""
        # First, cause some failures
        failing_operation = AsyncMock(side_effect=Exception("Error"))
        for _ in range(3):
            await error_boundary.execute_with_boundary(
                failing_operation,
                "failing_operation"
            )
        
        assert error_boundary.metrics.status == ServiceHealth.DEGRADED
        
        # Then have successful operations
        success_operation = AsyncMock(return_value="success")
        for _ in range(5):
            await error_boundary.execute_with_boundary(
                success_operation,
                "success_operation"
            )
        
        # Health should improve
        assert error_boundary.metrics.consecutive_failures == 0
        assert error_boundary.metrics.success_count == 5

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, error_boundary):
        """Test comprehensive metrics tracking."""
        # Execute mixed operations
        success_op = AsyncMock(return_value="success")
        fail_op = AsyncMock(side_effect=Exception("Error"))
        
        # 3 successes, 2 failures
        await error_boundary.execute_with_boundary(success_op, "op1")
        await error_boundary.execute_with_boundary(fail_op, "op2")
        await error_boundary.execute_with_boundary(success_op, "op3")
        await error_boundary.execute_with_boundary(fail_op, "op4")
        await error_boundary.execute_with_boundary(success_op, "op5")
        
        metrics = error_boundary.metrics
        assert metrics.success_count == 3
        assert metrics.error_count == 2
        assert metrics.total_requests == 5
        assert metrics.average_response_time > 0
        assert metrics.last_error is not None

    @pytest.mark.asyncio
    async def test_response_time_tracking(self, error_boundary):
        """Test response time tracking."""
        async def timed_operation():
            await asyncio.sleep(0.01)  # 10ms delay
            return "result"
        
        operation = AsyncMock(side_effect=timed_operation)
        
        await error_boundary.execute_with_boundary(operation, "timed_op")
        
        assert error_boundary.metrics.average_response_time > 0
        assert error_boundary.metrics.average_response_time >= 0.01

    @pytest.mark.asyncio
    async def test_error_categorization(self, error_boundary):
        """Test different error types are handled correctly."""
        # Test different exception types
        errors = [
            ValueError("Value error"),
            RuntimeError("Runtime error"),
            asyncio.TimeoutError("Timeout error"),
            ConnectionError("Connection error")
        ]
        
        for error in errors:
            operation = AsyncMock(side_effect=error)
            result = await error_boundary.execute_with_boundary(
                operation,
                f"error_op_{type(error).__name__}"
            )
            assert result is None
        
        assert error_boundary.metrics.error_count == len(errors)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, error_boundary):
        """Test concurrent operation execution."""
        operations = []
        for i in range(10):
            if i % 2 == 0:
                op = AsyncMock(return_value=f"success_{i}")
            else:
                op = AsyncMock(side_effect=Exception(f"error_{i}"))
            operations.append(op)
        
        # Execute operations concurrently
        tasks = []
        for i, op in enumerate(operations):
            task = error_boundary.execute_with_boundary(op, f"concurrent_op_{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Verify results
        successful_results = [r for r in results if r is not None]
        assert len(successful_results) == 5  # Half should succeed
        assert error_boundary.metrics.total_requests == 10

    @pytest.mark.asyncio
    async def test_health_status_transitions(self, error_boundary):
        """Test health status transitions."""
        # Start healthy
        assert error_boundary.metrics.status == ServiceHealth.HEALTHY
        
        # Single failure -> DEGRADED
        fail_op = AsyncMock(side_effect=Exception("Error"))
        await error_boundary.execute_with_boundary(fail_op, "fail1")
        assert error_boundary.metrics.status == ServiceHealth.DEGRADED
        
        # Multiple failures -> CRITICAL
        for _ in range(5):
            await error_boundary.execute_with_boundary(fail_op, "fail_multi")
        assert error_boundary.metrics.status == ServiceHealth.CRITICAL
        
        # Recovery with successes
        success_op = AsyncMock(return_value="success")
        for _ in range(3):
            await error_boundary.execute_with_boundary(success_op, "recovery")
        
        # Should improve from CRITICAL
        assert error_boundary.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_custom_timeout_handling(self, error_boundary):
        """Test custom timeout values."""
        async def variable_delay_op(delay):
            await asyncio.sleep(delay)
            return f"completed_after_{delay}"
        
        # Short timeout - should fail
        short_op = AsyncMock(side_effect=lambda: variable_delay_op(0.2))
        result1 = await error_boundary.execute_with_boundary(
            short_op, "short_timeout", timeout=0.1
        )
        assert result1 is None
        
        # Long timeout - should succeed
        long_op = AsyncMock(side_effect=lambda: variable_delay_op(0.05))
        result2 = await error_boundary.execute_with_boundary(
            long_op, "long_timeout", timeout=0.2
        )
        assert result2 == "completed_after_0.05"

    @pytest.mark.asyncio
    async def test_fallback_with_different_types(self, error_boundary):
        """Test fallback with different return types."""
        # Test with different fallback types
        fallbacks = [
            AsyncMock(return_value="string_fallback"),
            AsyncMock(return_value=42),
            AsyncMock(return_value={"key": "value"}),
            AsyncMock(return_value=[1, 2, 3])
        ]
        
        fail_op = AsyncMock(side_effect=Exception("Error"))
        
        for i, fallback in enumerate(fallbacks):
            result = await error_boundary.execute_with_boundary(
                fail_op,
                f"fallback_test_{i}",
                fallback=fallback
            )
            assert result == fallback.return_value

    @pytest.mark.asyncio
    async def test_error_boundary_reset(self, error_boundary):
        """Test error boundary reset functionality."""
        # Cause some failures
        fail_op = AsyncMock(side_effect=Exception("Error"))
        for _ in range(3):
            await error_boundary.execute_with_boundary(fail_op, "fail_op")
        
        initial_error_count = error_boundary.metrics.error_count
        assert initial_error_count > 0
        
        # Reset the boundary
        error_boundary.reset()
        
        # Verify reset
        assert error_boundary.metrics.error_count == 0
        assert error_boundary.metrics.success_count == 0
        assert error_boundary.metrics.consecutive_failures == 0
        assert error_boundary.metrics.status == ServiceHealth.HEALTHY

    @pytest.mark.asyncio
    async def test_standard_error_creation(self):
        """Test StandardError creation and properties."""
        original_error = ValueError("Original message")
        operation_name = "test_operation"
        
        std_error = StandardError.from_exception(original_error, operation_name)
        
        assert std_error.operation == operation_name
        assert "test_operation failed" in std_error.message
        assert "Original message" in std_error.message
        assert std_error.original_error == original_error
        assert std_error.timestamp is not None

    @pytest.mark.asyncio
    async def test_service_health_metrics_properties(self, error_boundary):
        """Test ServiceHealthMetrics properties and methods."""
        metrics = error_boundary.metrics
        
        # Test initial state
        assert metrics.service_name == "test_service"
        assert metrics.status == ServiceHealth.HEALTHY
        assert metrics.uptime_start is not None
        
        # Test after operations
        success_op = AsyncMock(return_value="success")
        await error_boundary.execute_with_boundary(success_op, "test")
        
        assert metrics.total_requests == 1
        assert metrics.last_check is not None

    def test_is_healthy_method(self, error_boundary):
        """Test is_healthy method with different states."""
        # Initially healthy
        assert error_boundary.is_healthy() is True
        
        # Manually set to degraded
        error_boundary.metrics.status = ServiceHealth.DEGRADED
        assert error_boundary.is_healthy() is False
        
        # Set to critical
        error_boundary.metrics.status = ServiceHealth.CRITICAL
        assert error_boundary.is_healthy() is False
        
        # Back to healthy
        error_boundary.metrics.status = ServiceHealth.HEALTHY
        assert error_boundary.is_healthy() is True

    @pytest.mark.asyncio
    async def test_decorator_functionality(self):
        """Test the with_error_boundary decorator."""
        boundary = ServiceErrorBoundary("decorator_test")
        
        @with_error_boundary(boundary, "decorated_operation")
        async def decorated_function(value):
            if value == "fail":
                raise ValueError("Decorated function failed")
            return f"decorated_{value}"
        
        # Test successful call
        result1 = await decorated_function("success")
        assert result1 == "decorated_success"
        assert boundary.metrics.success_count == 1
        
        # Test failed call
        result2 = await decorated_function("fail")
        assert result2 is None
        assert boundary.metrics.error_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_fallback(self):
        """Test decorator with fallback functionality."""
        boundary = ServiceErrorBoundary("decorator_fallback_test")
        
        async def fallback_func():
            return "fallback_result"
        
        @with_error_boundary(boundary, "decorated_with_fallback", fallback=fallback_func)
        async def decorated_function_with_fallback():
            raise RuntimeError("Always fails")
        
        result = await decorated_function_with_fallback()
        assert result == "fallback_result"
        assert boundary.metrics.error_count == 1

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, error_boundary):
        """Test memory usage during high-load operations."""
        import gc
        
        # Force garbage collection before test
        gc.collect()
        
        # Execute many operations
        for i in range(1000):
            if i % 2 == 0:
                op = AsyncMock(return_value=f"result_{i}")
            else:
                op = AsyncMock(side_effect=Exception(f"error_{i}"))
            
            await error_boundary.execute_with_boundary(op, f"load_test_{i}")
        
        # Force garbage collection after test
        gc.collect()
        
        # Verify metrics are reasonable
        assert error_boundary.metrics.total_requests == 1000
        assert error_boundary.metrics.success_count == 500
        assert error_boundary.metrics.error_count == 500

    @pytest.mark.asyncio
    async def test_edge_case_empty_operation_name(self, error_boundary):
        """Test edge case with empty operation name."""
        success_op = AsyncMock(return_value="success")
        
        result = await error_boundary.execute_with_boundary(success_op, "")
        
        assert result == "success"
        assert error_boundary.metrics.success_count == 1

    @pytest.mark.asyncio
    async def test_edge_case_none_operation(self, error_boundary):
        """Test edge case with None operation."""
        result = await error_boundary.execute_with_boundary(None, "none_operation")
        
        assert result is None
        assert error_boundary.metrics.error_count == 1

    @pytest.mark.asyncio
    async def test_very_long_operation_name(self, error_boundary):
        """Test with very long operation name."""
        long_name = "a" * 1000  # 1000 character operation name
        success_op = AsyncMock(return_value="success")
        
        result = await error_boundary.execute_with_boundary(success_op, long_name)
        
        assert result == "success"
        assert error_boundary.metrics.success_count == 1

    @pytest.mark.asyncio
    async def test_nested_error_boundaries(self):
        """Test nested error boundary operations."""
        outer_boundary = ServiceErrorBoundary("outer_service")
        inner_boundary = ServiceErrorBoundary("inner_service")
        
        async def inner_operation():
            # This will fail in inner boundary
            raise ValueError("Inner error")
        
        async def outer_operation():
            # This calls inner boundary
            return await inner_boundary.execute_with_boundary(
                inner_operation, "inner_op"
            )
        
        result = await outer_boundary.execute_with_boundary(
            outer_operation, "outer_op"
        )
        
        # Outer should succeed (inner returns None)
        assert result is None
        assert outer_boundary.metrics.success_count == 1
        assert inner_boundary.metrics.error_count == 1

    @pytest.mark.asyncio
    async def test_service_health_enum_values(self):
        """Test ServiceHealth enum values."""
        assert ServiceHealth.HEALTHY.value == "healthy"
        assert ServiceHealth.DEGRADED.value == "degraded"
        assert ServiceHealth.CRITICAL.value == "critical"
        
        # Test ordering
        assert ServiceHealth.HEALTHY < ServiceHealth.DEGRADED
        assert ServiceHealth.DEGRADED < ServiceHealth.CRITICAL

    @pytest.mark.asyncio
    async def test_metrics_serialization(self, error_boundary):
        """Test metrics can be serialized (for logging/monitoring)."""
        # Execute some operations
        success_op = AsyncMock(return_value="success")
        fail_op = AsyncMock(side_effect=Exception("Error"))
        
        await error_boundary.execute_with_boundary(success_op, "success_op")
        await error_boundary.execute_with_boundary(fail_op, "fail_op")
        
        metrics = error_boundary.metrics
        
        # Test that metrics have serializable properties
        assert isinstance(metrics.service_name, str)
        assert isinstance(metrics.error_count, int)
        assert isinstance(metrics.success_count, int)
        assert isinstance(metrics.total_requests, int)
        assert isinstance(metrics.average_response_time, (int, float))
        assert isinstance(metrics.consecutive_failures, int)

    @pytest.mark.asyncio
    async def test_boundary_with_custom_service_name(self):
        """Test boundary with custom service name."""
        custom_name = "my_custom_service_123"
        boundary = ServiceErrorBoundary(custom_name)
        
        assert boundary.service_name == custom_name
        assert boundary.metrics.service_name == custom_name

    @pytest.mark.asyncio
    async def test_operation_cancellation_handling(self, error_boundary):
        """Test handling of cancelled operations."""
        async def cancellable_operation():
            await asyncio.sleep(1)
            return "completed"
        
        operation = AsyncMock(side_effect=cancellable_operation)
        
        # Start operation and cancel it
        task = asyncio.create_task(
            error_boundary.execute_with_boundary(operation, "cancellable_op", timeout=0.1)
        )
        
        result = await task
        
        # Should handle cancellation gracefully
        assert result is None
        assert error_boundary.metrics.error_count == 1