"""
Service Error Boundary and Resilience Module

This module provides error isolation, graceful degradation, and recovery mechanisms
for services in the PsychoChauffeur bot application.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, Union
from contextlib import asynccontextmanager

from modules.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory, StandardError

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ServiceHealth(Enum):
    """Service health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class CircuitBreakerState(Enum):
    """Circuit breaker state enumeration."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class ServiceHealthMetrics:
    """Metrics for tracking service health."""
    service_name: str
    status: ServiceHealth = ServiceHealth.HEALTHY
    last_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    average_response_time: float = 0.0
    last_error: Optional[StandardError] = None
    consecutive_failures: int = 0
    uptime_start: datetime = field(default_factory=datetime.now)
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.error_count / self.total_requests) * 100
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return 100.0 - self.error_rate
    
    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self.error_count = 0
        self.success_count = 0
        self.total_requests = 0
        self.consecutive_failures = 0
        self.average_response_time = 0.0
        self.last_error = None
        self.uptime_start = datetime.now()


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds


class CircuitBreaker:
    """Circuit breaker implementation for service resilience."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None
    
    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution."""
        now = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.next_attempt_time and now >= self.next_attempt_time:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        else:  # CircuitBreakerState.HALF_OPEN
            return True
    
    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} closed after recovery")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.next_attempt_time = datetime.now() + timedelta(seconds=self.config.recovery_timeout)
                logger.warning(f"Circuit breaker {self.name} opened due to failures")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.next_attempt_time = datetime.now() + timedelta(seconds=self.config.recovery_timeout)
            logger.warning(f"Circuit breaker {self.name} reopened during half-open test")


class ServiceErrorBoundary:
    """
    Error boundary for service operations providing isolation and resilience.
    
    This class implements error isolation, graceful degradation, circuit breaker
    patterns, and health monitoring for services.
    """
    
    def __init__(self, service_name: str, circuit_breaker_config: Optional[CircuitBreakerConfig] = None):
        self.service_name = service_name
        self.metrics = ServiceHealthMetrics(service_name)
        self.circuit_breaker = CircuitBreaker(service_name, circuit_breaker_config or CircuitBreakerConfig())
        self.fallback_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = datetime.now()
        
    async def execute_with_boundary(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "unknown",
        fallback: Optional[Callable[[], Awaitable[T]]] = None,
        timeout: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[T]:
        """
        Execute an operation within the error boundary.
        
        Args:
            operation: The async operation to execute
            operation_name: Name of the operation for logging
            fallback: Optional fallback operation if main operation fails
            timeout: Optional timeout for the operation
            context: Additional context for error reporting
            
        Returns:
            Result of the operation or fallback, None if both fail
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker {self.service_name} is open, rejecting {operation_name}")
            if fallback:
                return await self._execute_fallback(fallback, operation_name, context)
            return None
        
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            # Execute with timeout if specified
            if timeout:
                result = await asyncio.wait_for(operation(), timeout=timeout)
            else:
                result = await operation()
            
            # Record success
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            self.circuit_breaker.record_success()
            
            return result
            
        except asyncio.TimeoutError as e:
            # Handle timeout specifically
            execution_time = time.time() - start_time
            error = StandardError(
                message=f"Operation {operation_name} timed out after {execution_time:.2f}s",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.NETWORK,
                context={
                    "service_name": self.service_name,
                    "operation_name": operation_name,
                    "timeout": timeout,
                    "execution_time": execution_time,
                    **(context or {})
                },
                original_exception=e
            )
            
            return await self._handle_operation_error(error, fallback, operation_name, context)
            
        except Exception as e:
            # Handle general exceptions
            execution_time = time.time() - start_time
            
            # Convert to StandardError if needed
            if isinstance(e, StandardError):
                error = e
            else:
                error = StandardError(
                    message=f"Operation {operation_name} failed: {str(e)}",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.GENERAL,
                    context={
                        "service_name": self.service_name,
                        "operation_name": operation_name,
                        "execution_time": execution_time,
                        **(context or {})
                    },
                    original_exception=e
                )
            
            return await self._handle_operation_error(error, fallback, operation_name, context)
    
    async def _handle_operation_error(
        self,
        error: StandardError,
        fallback: Optional[Callable[[], Awaitable[T]]],
        operation_name: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[T]:
        """Handle operation error with fallback and circuit breaker logic."""
        self._record_failure(error)
        self.circuit_breaker.record_failure()
        
        # Log the error
        await ErrorHandler.handle_error(
            error=error,
            context_data=context,
            propagate=False
        )
        
        # Try fallback if available
        if fallback:
            return await self._execute_fallback(fallback, operation_name, context)
        
        return None
    
    async def _execute_fallback(
        self,
        fallback: Callable[[], Awaitable[T]],
        operation_name: str,
        context: Optional[Dict[str, Any]]
    ) -> Optional[T]:
        """Execute fallback operation with error handling."""
        try:
            logger.info(f"Executing fallback for {self.service_name}.{operation_name}")
            result = await fallback()
            logger.info(f"Fallback succeeded for {self.service_name}.{operation_name}")
            return result
        except Exception as e:
            fallback_error = StandardError(
                message=f"Fallback for {operation_name} also failed: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.GENERAL,
                context={
                    "service_name": self.service_name,
                    "operation_name": operation_name,
                    "fallback": True,
                    **(context or {})
                },
                original_exception=e
            )
            
            await ErrorHandler.handle_error(
                error=fallback_error,
                context_data=context,
                propagate=False
            )
            
            return None
    
    def _record_success(self, execution_time: float) -> None:
        """Record a successful operation."""
        self.metrics.success_count += 1
        self.metrics.consecutive_failures = 0
        
        # Update average response time
        total_time = self.metrics.average_response_time * (self.metrics.success_count - 1)
        self.metrics.average_response_time = (total_time + execution_time) / self.metrics.success_count
        
        # Update health status based on current metrics
        # When consecutive failures is 0, reassess health based on overall error rate
        if self.metrics.consecutive_failures == 0:
            # More lenient recovery thresholds - focus on recent success
            if self.metrics.error_rate < 30.0:  # Allow up to 30% error rate for healthy if no consecutive failures
                old_status = self.metrics.status
                self.metrics.status = ServiceHealth.HEALTHY
                if old_status != ServiceHealth.HEALTHY:
                    logger.info(f"Service {self.service_name} recovered to healthy status")
            elif self.metrics.error_rate < 50.0:
                self.metrics.status = ServiceHealth.DEGRADED
            elif self.metrics.error_rate < 75.0:
                self.metrics.status = ServiceHealth.UNHEALTHY
            else:
                self.metrics.status = ServiceHealth.CRITICAL
    
    def _record_failure(self, error: StandardError) -> None:
        """Record a failed operation."""
        self.metrics.error_count += 1
        self.metrics.consecutive_failures += 1
        self.metrics.last_error = error
        self.metrics.last_check = datetime.now()
        
        # Update health status based on error rate and consecutive failures
        if self.metrics.consecutive_failures >= 5 or self.metrics.error_rate > 50:
            self.metrics.status = ServiceHealth.CRITICAL
        elif self.metrics.consecutive_failures >= 3 or self.metrics.error_rate > 25:
            self.metrics.status = ServiceHealth.UNHEALTHY
        elif self.metrics.consecutive_failures >= 1 or self.metrics.error_rate > 0:
            self.metrics.status = ServiceHealth.DEGRADED
    
    def register_fallback(self, operation_name: str, fallback: Callable[..., Awaitable[Any]]) -> None:
        """Register a fallback handler for a specific operation."""
        self.fallback_handlers[operation_name] = fallback
        logger.info(f"Registered fallback for {self.service_name}.{operation_name}")
    
    def get_health_status(self) -> ServiceHealthMetrics:
        """Get current health metrics."""
        return self.metrics
    
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.metrics.status in [ServiceHealth.HEALTHY, ServiceHealth.DEGRADED]
    
    async def perform_health_check(self, health_check_fn: Optional[Callable[[], Awaitable[bool]]] = None) -> bool:
        """
        Perform a health check on the service.
        
        Args:
            health_check_fn: Optional custom health check function
            
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            if health_check_fn:
                is_healthy = await health_check_fn()
            else:
                # Default health check based on metrics
                is_healthy = (
                    self.metrics.consecutive_failures < 3 and
                    self.metrics.error_rate < 25 and
                    self.circuit_breaker.state != CircuitBreakerState.OPEN
                )
            
            if is_healthy and self.metrics.status != ServiceHealth.HEALTHY:
                # Service recovered
                old_status = self.metrics.status
                self.metrics.status = ServiceHealth.HEALTHY
                self.metrics.consecutive_failures = 0
                logger.info(f"Service {self.service_name} health check passed, status changed from {old_status.value} to healthy")
            elif not is_healthy and self.metrics.status == ServiceHealth.HEALTHY:
                # Service degraded
                self.metrics.status = ServiceHealth.DEGRADED
                logger.warning(f"Service {self.service_name} health check failed, status changed to degraded")
            
            self.last_health_check = datetime.now()
            return is_healthy
            
        except Exception as e:
            error = StandardError(
                message=f"Health check failed for {self.service_name}: {str(e)}",
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.GENERAL,
                context={"service_name": self.service_name},
                original_exception=e
            )
            
            await ErrorHandler.handle_error(error=error, propagate=False)
            return False
    
    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self.circuit_breaker.state = CircuitBreakerState.CLOSED
        self.circuit_breaker.failure_count = 0
        self.circuit_breaker.success_count = 0
        self.circuit_breaker.next_attempt_time = None
        logger.info(f"Circuit breaker for {self.service_name} manually reset")
    
    def reset_metrics(self) -> None:
        """Reset all health metrics."""
        self.metrics.reset_metrics()
        logger.info(f"Health metrics reset for {self.service_name}")
    
    def reset(self) -> None:
        """Reset the entire error boundary to initial state."""
        self.metrics.reset_metrics()
        self.reset_circuit_breaker()
        self.fallback_handlers.clear()
        self.last_health_check = datetime.now()
        logger.info(f"Error boundary reset for {self.service_name}")


class ServiceHealthMonitor:
    """
    Centralized health monitoring for all services with error boundaries.
    """
    
    def __init__(self) -> None:
        self.error_boundaries: Dict[str, ServiceErrorBoundary] = {}
        self.monitoring_task: Optional[asyncio.Task[None]] = None
        self.monitoring_interval = 300  # 5 minutes
        self.is_monitoring = False
    
    def register_service(
        self,
        service_name: str,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ) -> ServiceErrorBoundary:
        """Register a service for health monitoring."""
        if service_name not in self.error_boundaries:
            self.error_boundaries[service_name] = ServiceErrorBoundary(
                service_name, circuit_breaker_config
            )
            logger.info(f"Registered service {service_name} for health monitoring")
        
        return self.error_boundaries[service_name]
    
    def get_error_boundary(self, service_name: str) -> Optional[ServiceErrorBoundary]:
        """Get error boundary for a service."""
        return self.error_boundaries.get(service_name)
    
    def get_all_health_metrics(self) -> Dict[str, ServiceHealthMetrics]:
        """Get health metrics for all monitored services."""
        return {
            name: boundary.get_health_status()
            for name, boundary in self.error_boundaries.items()
        }
    
    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy service names."""
        return [
            name for name, boundary in self.error_boundaries.items()
            if not boundary.is_healthy()
        ]
    
    async def start_monitoring(self) -> None:
        """Start the health monitoring background task."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started service health monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop the health monitoring background task."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped service health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self.is_monitoring:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all registered services."""
        for service_name, boundary in self.error_boundaries.items():
            try:
                await boundary.perform_health_check()
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate a comprehensive health report."""
        metrics = self.get_all_health_metrics()
        unhealthy_services = self.get_unhealthy_services()
        
        total_services = len(metrics)
        healthy_services = total_services - len(unhealthy_services)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": len(unhealthy_services),
            "unhealthy_service_names": unhealthy_services,
            "overall_health_percentage": (healthy_services / total_services * 100) if total_services > 0 else 100,
            "service_details": {
                name: {
                    "status": metrics.status.value,
                    "error_rate": metrics.error_rate,
                    "success_rate": metrics.success_rate,
                    "consecutive_failures": metrics.consecutive_failures,
                    "total_requests": metrics.total_requests,
                    "average_response_time": metrics.average_response_time,
                    "last_error": metrics.last_error.message if metrics.last_error else None
                }
                for name, metrics in metrics.items()
            }
        }
    
    def clear_all_services(self) -> None:
        """Clear all registered services (useful for testing)."""
        self.error_boundaries.clear()
        logger.info("Cleared all registered services from health monitor")


# Global health monitor instance
health_monitor = ServiceHealthMonitor()


# Decorator for automatic error boundary wrapping
def with_error_boundary(
    service_name: str,
    operation_name: Optional[str] = None,
    timeout: Optional[float] = None,
    fallback: Optional[Callable[[], Awaitable[Any]]] = None
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[Optional[T]]]]:
    """
    Decorator to wrap service methods with error boundary protection.
    
    Args:
        service_name: Name of the service
        operation_name: Name of the operation (defaults to function name)
        timeout: Optional timeout for the operation
        fallback: Optional fallback function
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Optional[T]]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            boundary = health_monitor.get_error_boundary(service_name)
            if not boundary:
                boundary = health_monitor.register_service(service_name)
            
            op_name = operation_name or func.__name__
            
            async def operation() -> T:
                return await func(*args, **kwargs)
            
            return await boundary.execute_with_boundary(
                operation=operation,
                operation_name=op_name,
                fallback=fallback,
                timeout=timeout,
                context={"function": func.__name__, "args_count": len(args)}
            )
        
        return wrapper
    return decorator