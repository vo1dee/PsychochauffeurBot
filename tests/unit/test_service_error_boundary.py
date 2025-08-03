"""
Unit tests for ServiceErrorBoundary and related components.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from modules.service_error_boundary import (
    ServiceErrorBoundary,
    ServiceHealthMonitor,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    ServiceHealth,
    ServiceHealthMetrics,
    with_error_boundary,
    health_monitor
)
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory


class TestServiceHealthMetrics:
    """Test cases for ServiceHealthMetrics."""
    
    def test_initial_metrics(self):
        """Test initial state of health metrics."""
        metrics = ServiceHealthMetrics("test_service")
        
        assert metrics.service_name == "test_service"
        assert metrics.status == ServiceHealth.HEALTHY
        assert metrics.error_count == 0
        assert metrics.success_count == 0
        assert metrics.total_requests == 0
        assert metrics.consecutive_failures == 0
        assert metrics.error_rate == 0.0
        assert metrics.success_rate == 100.0
    
    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        metrics = ServiceHealthMetrics("test_service")
        metrics.total_requests = 100
        metrics.error_count = 25
        metrics.success_count = 75
        
        assert metrics.error_rate == 25.0
        assert metrics.success_rate == 75.0
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        metrics = ServiceHealthMetrics("test_service")
        metrics.error_count = 10
        metrics.success_count = 90
        metrics.total_requests = 100
        metrics.consecutive_failures = 5
        
        metrics.reset_metrics()
        
        assert metrics.error_count == 0
        assert metrics.success_count == 0
        assert metrics.total_requests == 0
        assert metrics.consecutive_failures == 0


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""
    
    def test_initial_state(self):
        """Test initial circuit breaker state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)
        
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.can_execute() is True
    
    def test_failure_threshold_opens_circuit(self):
        """Test that reaching failure threshold opens the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)
        
        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.can_execute() is False
    
    def test_recovery_timeout_allows_half_open(self):
        """Test that recovery timeout allows half-open state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0)
        breaker = CircuitBreaker("test", config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Should allow execution after timeout (0 seconds)
        assert breaker.can_execute() is True
        assert breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_success_closes_circuit(self):
        """Test that successes in half-open state close the circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=2)
        breaker = CircuitBreaker("test", config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.state = CircuitBreakerState.HALF_OPEN
        
        # Record successes to close
        breaker.record_success()
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        
        breaker.record_success()
        assert breaker.state == CircuitBreakerState.CLOSED
    
    def test_half_open_failure_reopens_circuit(self):
        """Test that failure in half-open state reopens the circuit."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)
        
        # Set to half-open
        breaker.state = CircuitBreakerState.HALF_OPEN
        
        # Record failure should reopen
        breaker.record_failure()
        assert breaker.state == CircuitBreakerState.OPEN


class TestServiceErrorBoundary:
    """Test cases for ServiceErrorBoundary."""
    
    @pytest.fixture
    def error_boundary(self):
        """Create a test error boundary."""
        return ServiceErrorBoundary("test_service")
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, error_boundary):
        """Test successful operation execution."""
        async def successful_operation():
            return "success"
        
        result = await error_boundary.execute_with_boundary(
            operation=successful_operation,
            operation_name="test_op"
        )
        
        assert result == "success"
        assert error_boundary.metrics.success_count == 1
        assert error_boundary.metrics.error_count == 0
        assert error_boundary.metrics.total_requests == 1
    
    @pytest.mark.asyncio
    async def test_failed_operation_without_fallback(self, error_boundary):
        """Test failed operation without fallback."""
        async def failing_operation():
            raise ValueError("Test error")
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
            result = await error_boundary.execute_with_boundary(
                operation=failing_operation,
                operation_name="test_op"
            )
        
        assert result is None
        assert error_boundary.metrics.error_count == 1
        assert error_boundary.metrics.success_count == 0
        assert error_boundary.metrics.consecutive_failures == 1
        mock_handle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_failed_operation_with_successful_fallback(self, error_boundary):
        """Test failed operation with successful fallback."""
        async def failing_operation():
            raise ValueError("Test error")
        
        async def fallback_operation():
            return "fallback_result"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            result = await error_boundary.execute_with_boundary(
                operation=failing_operation,
                operation_name="test_op",
                fallback=fallback_operation
            )
        
        assert result == "fallback_result"
        assert error_boundary.metrics.error_count == 1
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, error_boundary):
        """Test timeout handling."""
        async def slow_operation():
            await asyncio.sleep(2)
            return "too_slow"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error') as mock_handle:
            result = await error_boundary.execute_with_boundary(
                operation=slow_operation,
                operation_name="slow_op",
                timeout=0.1
            )
        
        assert result is None
        assert error_boundary.metrics.error_count == 1
        mock_handle.assert_called_once()
        
        # Check that the error was a timeout error
        call_args = mock_handle.call_args
        error = call_args[1]['error']
        assert isinstance(error, StandardError)
        assert "timed out" in error.message.lower()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, error_boundary):
        """Test circuit breaker integration."""
        async def failing_operation():
            raise ValueError("Test error")
        
        # Configure circuit breaker with low threshold
        error_boundary.circuit_breaker.config.failure_threshold = 2
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # First failure
            result1 = await error_boundary.execute_with_boundary(
                operation=failing_operation,
                operation_name="test_op"
            )
            assert result1 is None
            assert error_boundary.circuit_breaker.state == CircuitBreakerState.CLOSED
            
            # Second failure should open circuit
            result2 = await error_boundary.execute_with_boundary(
                operation=failing_operation,
                operation_name="test_op"
            )
            assert result2 is None
            assert error_boundary.circuit_breaker.state == CircuitBreakerState.OPEN
            
            # Third attempt should be rejected by circuit breaker
            result3 = await error_boundary.execute_with_boundary(
                operation=failing_operation,
                operation_name="test_op"
            )
            assert result3 is None
    
    @pytest.mark.asyncio
    async def test_health_status_updates(self, error_boundary):
        """Test health status updates based on failures."""
        async def failing_operation():
            raise ValueError("Test error")
        
        # Initial state should be healthy
        assert error_boundary.metrics.status == ServiceHealth.HEALTHY
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # Record multiple failures
            for _ in range(3):
                await error_boundary.execute_with_boundary(
                    operation=failing_operation,
                    operation_name="test_op"
                )
        
        # Should be unhealthy or critical after consecutive failures
        assert error_boundary.metrics.status in [ServiceHealth.UNHEALTHY, ServiceHealth.CRITICAL]
        assert error_boundary.metrics.consecutive_failures == 3
    
    @pytest.mark.asyncio
    async def test_health_check_default(self, error_boundary):
        """Test default health check logic."""
        # Should be healthy initially
        is_healthy = await error_boundary.perform_health_check()
        assert is_healthy is True
        
        # Make service unhealthy
        error_boundary.metrics.consecutive_failures = 5
        error_boundary.metrics.error_count = 50
        error_boundary.metrics.total_requests = 100
        
        is_healthy = await error_boundary.perform_health_check()
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_custom(self, error_boundary):
        """Test custom health check function."""
        custom_check = AsyncMock(return_value=True)
        
        is_healthy = await error_boundary.perform_health_check(custom_check)
        assert is_healthy is True
        custom_check.assert_called_once()
    
    def test_fallback_registration(self, error_boundary):
        """Test fallback handler registration."""
        async def fallback_handler():
            return "fallback"
        
        error_boundary.register_fallback("test_op", fallback_handler)
        assert "test_op" in error_boundary.fallback_handlers
        assert error_boundary.fallback_handlers["test_op"] == fallback_handler
    
    def test_circuit_breaker_reset(self, error_boundary):
        """Test manual circuit breaker reset."""
        # Open the circuit
        error_boundary.circuit_breaker.state = CircuitBreakerState.OPEN
        error_boundary.circuit_breaker.failure_count = 5
        
        error_boundary.reset_circuit_breaker()
        
        assert error_boundary.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert error_boundary.circuit_breaker.failure_count == 0
    
    def test_metrics_reset(self, error_boundary):
        """Test metrics reset."""
        # Set some metrics
        error_boundary.metrics.error_count = 10
        error_boundary.metrics.success_count = 90
        error_boundary.metrics.consecutive_failures = 3
        
        error_boundary.reset_metrics()
        
        assert error_boundary.metrics.error_count == 0
        assert error_boundary.metrics.success_count == 0
        assert error_boundary.metrics.consecutive_failures == 0


class TestServiceHealthMonitor:
    """Test cases for ServiceHealthMonitor."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create a test health monitor."""
        monitor = ServiceHealthMonitor()
        yield monitor
        # Cleanup
        monitor.error_boundaries.clear()
    
    def test_service_registration(self, health_monitor):
        """Test service registration."""
        boundary = health_monitor.register_service("test_service")
        
        assert isinstance(boundary, ServiceErrorBoundary)
        assert boundary.service_name == "test_service"
        assert "test_service" in health_monitor.error_boundaries
    
    def test_duplicate_registration(self, health_monitor):
        """Test that duplicate registration returns same boundary."""
        boundary1 = health_monitor.register_service("test_service")
        boundary2 = health_monitor.register_service("test_service")
        
        assert boundary1 is boundary2
    
    def test_get_error_boundary(self, health_monitor):
        """Test getting error boundary."""
        health_monitor.register_service("test_service")
        
        boundary = health_monitor.get_error_boundary("test_service")
        assert boundary is not None
        assert boundary.service_name == "test_service"
        
        # Non-existent service
        boundary = health_monitor.get_error_boundary("non_existent")
        assert boundary is None
    
    def test_get_all_health_metrics(self, health_monitor):
        """Test getting all health metrics."""
        health_monitor.register_service("service1")
        health_monitor.register_service("service2")
        
        metrics = health_monitor.get_all_health_metrics()
        
        assert len(metrics) == 2
        assert "service1" in metrics
        assert "service2" in metrics
        assert isinstance(metrics["service1"], ServiceHealthMetrics)
    
    def test_get_unhealthy_services(self, health_monitor):
        """Test getting unhealthy services."""
        boundary1 = health_monitor.register_service("healthy_service")
        boundary2 = health_monitor.register_service("unhealthy_service")
        
        # Make one service unhealthy
        boundary2.metrics.status = ServiceHealth.UNHEALTHY
        
        unhealthy = health_monitor.get_unhealthy_services()
        
        assert len(unhealthy) == 1
        assert "unhealthy_service" in unhealthy
        assert "healthy_service" not in unhealthy
    
    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(self, health_monitor):
        """Test monitoring start and stop."""
        assert health_monitor.is_monitoring is False
        
        await health_monitor.start_monitoring()
        assert health_monitor.is_monitoring is True
        assert health_monitor.monitoring_task is not None
        
        await health_monitor.stop_monitoring()
        assert health_monitor.is_monitoring is False
    
    def test_health_report_generation(self, health_monitor):
        """Test health report generation."""
        boundary1 = health_monitor.register_service("service1")
        boundary2 = health_monitor.register_service("service2")
        
        # Set some metrics
        boundary1.metrics.total_requests = 100
        boundary1.metrics.success_count = 95
        boundary1.metrics.error_count = 5
        
        boundary2.metrics.status = ServiceHealth.UNHEALTHY
        
        report = health_monitor.generate_health_report()
        
        assert report["total_services"] == 2
        assert report["healthy_services"] == 1
        assert report["unhealthy_services"] == 1
        assert "service1" in report["service_details"]
        assert "service2" in report["service_details"]
        assert report["service_details"]["service1"]["error_rate"] == 5.0


class TestErrorBoundaryDecorator:
    """Test cases for the error boundary decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful operation."""
        @with_error_boundary("test_service", "test_operation")
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
        
        # Check that service was registered
        boundary = health_monitor.get_error_boundary("test_service")
        assert boundary is not None
        assert boundary.metrics.success_count == 1
    
    @pytest.mark.asyncio
    async def test_decorator_failure(self):
        """Test decorator with failing operation."""
        @with_error_boundary("test_service", "test_operation")
        async def test_function():
            raise ValueError("Test error")
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            result = await test_function()
        
        assert result is None
        
        # Check that error was recorded
        boundary = health_monitor.get_error_boundary("test_service")
        assert boundary is not None
        assert boundary.metrics.error_count == 1
    
    @pytest.mark.asyncio
    async def test_decorator_with_timeout(self):
        """Test decorator with timeout."""
        @with_error_boundary("test_service", "slow_operation", timeout=0.1)
        async def slow_function():
            await asyncio.sleep(1)
            return "too_slow"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            result = await slow_function()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_decorator_with_fallback(self):
        """Test decorator with fallback."""
        async def fallback_func():
            return "fallback_result"
        
        @with_error_boundary("test_service", "test_operation", fallback=fallback_func)
        async def test_function():
            raise ValueError("Test error")
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            result = await test_function()
        
        assert result == "fallback_result"


class TestIntegrationScenarios:
    """Integration test scenarios for error boundary system."""
    
    @pytest.mark.asyncio
    async def test_service_recovery_scenario(self):
        """Test complete service failure and recovery scenario."""
        boundary = ServiceErrorBoundary("recovery_test")
        
        async def intermittent_operation():
            # Simulate intermittent failures
            if boundary.metrics.total_requests < 3:
                raise ValueError("Intermittent failure")
            return "success"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # First few requests should fail
            for i in range(3):
                result = await boundary.execute_with_boundary(
                    operation=intermittent_operation,
                    operation_name="intermittent_op"
                )
                # Only first 2 should fail, 3rd should succeed
                if i < 2:
                    assert result is None
                else:
                    assert result == "success"
            
            # Service should be unhealthy or critical
            assert boundary.metrics.status in [ServiceHealth.UNHEALTHY, ServiceHealth.DEGRADED, ServiceHealth.CRITICAL]
            
            # Next request should succeed and start recovery
            result = await boundary.execute_with_boundary(
                operation=intermittent_operation,
                operation_name="intermittent_op"
            )
            assert result == "success"
            
            # Continue with successful requests
            for _ in range(5):
                result = await boundary.execute_with_boundary(
                    operation=intermittent_operation,
                    operation_name="intermittent_op"
                )
                assert result == "success"
            
            # Service should recover to healthy
            assert boundary.metrics.status == ServiceHealth.HEALTHY
    
    @pytest.mark.asyncio
    async def test_cascading_failure_isolation(self):
        """Test that failures in one service don't affect others."""
        monitor = ServiceHealthMonitor()
        
        boundary1 = monitor.register_service("service1")
        boundary2 = monitor.register_service("service2")
        
        async def failing_operation():
            raise ValueError("Service1 failure")
        
        async def working_operation():
            return "service2_success"
        
        with patch('modules.service_error_boundary.ErrorHandler.handle_error'):
            # Fail service1 multiple times
            for _ in range(5):
                await boundary1.execute_with_boundary(
                    operation=failing_operation,
                    operation_name="fail_op"
                )
            
            # Service2 should still work normally
            result = await boundary2.execute_with_boundary(
                operation=working_operation,
                operation_name="work_op"
            )
            assert result == "service2_success"
        
        # Service1 should be unhealthy, service2 should be healthy
        assert not boundary1.is_healthy()
        assert boundary2.is_healthy()
        
        unhealthy_services = monitor.get_unhealthy_services()
        assert "service1" in unhealthy_services
        assert "service2" not in unhealthy_services