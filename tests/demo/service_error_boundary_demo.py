#!/usr/bin/env python3
"""
Demonstration script for ServiceErrorBoundary functionality.

This script shows how the error boundary system works with real service operations,
including circuit breaker behavior, health monitoring, and error recovery.
"""

import asyncio
import logging
import random
from typing import Any

from modules.service_error_boundary import (
    ServiceErrorBoundary,
    ServiceHealthMonitor,
    with_error_boundary,
    health_monitor
)
from modules.error_handler import StandardError, ErrorSeverity, ErrorCategory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DemoService:
    """Demo service to show error boundary integration."""
    
    def __init__(self, name: str):
        self.name = name
        self.error_boundary = ServiceErrorBoundary(name)
        self.call_count = 0
        self.failure_rate = 0.3  # 30% failure rate initially
    
    async def unreliable_operation(self, data: str) -> str:
        """Simulate an unreliable operation that sometimes fails."""
        self.call_count += 1
        
        # Simulate different types of failures
        if random.random() < self.failure_rate:
            failure_type = random.choice(['network', 'timeout', 'validation'])
            
            if failure_type == 'network':
                raise ConnectionError("Network connection failed")
            elif failure_type == 'timeout':
                await asyncio.sleep(0.1)  # Simulate slow operation
                raise TimeoutError("Operation timed out")
            else:
                raise ValueError(f"Invalid data: {data}")
        
        # Simulate processing time
        await asyncio.sleep(0.01)
        return f"Processed: {data} (call #{self.call_count})"
    
    async def reliable_fallback(self, data: str) -> str:
        """Fallback operation that always succeeds."""
        return f"Fallback result for: {data}"
    
    async def process_with_boundary(self, data: str) -> str:
        """Process data with error boundary protection."""
        return await self.error_boundary.execute_with_boundary(
            operation=lambda: self.unreliable_operation(data),
            operation_name="unreliable_operation",
            fallback=lambda: self.reliable_fallback(data),
            timeout=0.5,
            context={"data": data, "service": self.name}
        )
    
    def improve_reliability(self):
        """Simulate service improvement (reduce failure rate)."""
        self.failure_rate = max(0.0, self.failure_rate - 0.1)
        logger.info(f"{self.name} reliability improved, failure rate now: {self.failure_rate:.1%}")


@with_error_boundary("decorated_service", "demo_operation", timeout=1.0)
async def decorated_demo_function(should_fail: bool = False) -> str:
    """Demo function using the error boundary decorator."""
    if should_fail:
        raise RuntimeError("Simulated failure in decorated function")
    
    await asyncio.sleep(0.01)
    return "Decorated function succeeded"


async def demonstrate_basic_error_boundary():
    """Demonstrate basic error boundary functionality."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Error Boundary Functionality")
    print("="*60)
    
    service = DemoService("demo_service_1")
    
    # Test successful operations
    print("\n1. Testing successful operations:")
    for i in range(3):
        result = await service.process_with_boundary(f"data_{i}")
        print(f"   Result: {result}")
    
    # Test with failures
    print("\n2. Testing with failures (30% failure rate):")
    for i in range(10):
        result = await service.process_with_boundary(f"data_{i}")
        if result and "Fallback" in result:
            print(f"   Fallback used: {result}")
        elif result:
            print(f"   Success: {result}")
        else:
            print(f"   Failed completely")
    
    # Show health metrics
    print("\n3. Health metrics after operations:")
    metrics = service.error_boundary.get_health_status()
    print(f"   Status: {metrics.status.value}")
    print(f"   Total requests: {metrics.total_requests}")
    print(f"   Success rate: {metrics.success_rate:.1f}%")
    print(f"   Error rate: {metrics.error_rate:.1f}%")
    print(f"   Circuit breaker state: {service.error_boundary.circuit_breaker.state.value}")


async def demonstrate_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    print("\n" + "="*60)
    print("DEMO 2: Circuit Breaker Functionality")
    print("="*60)
    
    service = DemoService("demo_service_2")
    service.failure_rate = 0.8  # High failure rate to trigger circuit breaker
    service.error_boundary.circuit_breaker.config.failure_threshold = 3
    
    print(f"\n1. Service with {service.failure_rate:.0%} failure rate, circuit breaker threshold: 3")
    
    # Generate failures to open circuit breaker
    print("\n2. Generating failures to open circuit breaker:")
    for i in range(8):
        result = await service.process_with_boundary(f"data_{i}")
        cb_state = service.error_boundary.circuit_breaker.state.value
        print(f"   Attempt {i+1}: {'Success' if result and 'Processed' in result else 'Failed/Fallback'} (CB: {cb_state})")
        
        if cb_state == "open":
            print("   🚨 Circuit breaker opened!")
            break
    
    # Show that requests are now rejected
    print("\n3. Requests while circuit breaker is open:")
    for i in range(3):
        result = await service.process_with_boundary(f"rejected_{i}")
        print(f"   Request {i+1}: {'Rejected' if result is None else 'Fallback used'}")
    
    # Wait for recovery timeout and test half-open state
    print("\n4. Waiting for recovery timeout...")
    service.error_boundary.circuit_breaker.config.recovery_timeout = 1
    await asyncio.sleep(1.1)
    
    # Improve service reliability
    service.improve_reliability()
    service.improve_reliability()  # Now 60% failure rate
    
    print("\n5. Testing recovery (improved service reliability):")
    for i in range(5):
        result = await service.process_with_boundary(f"recovery_{i}")
        cb_state = service.error_boundary.circuit_breaker.state.value
        print(f"   Recovery attempt {i+1}: {'Success' if result and 'Processed' in result else 'Failed'} (CB: {cb_state})")
        
        if cb_state == "closed":
            print("   ✅ Circuit breaker closed - service recovered!")
            break


async def demonstrate_health_monitoring():
    """Demonstrate health monitoring across multiple services."""
    print("\n" + "="*60)
    print("DEMO 3: Health Monitoring System")
    print("="*60)
    
    # Create multiple services with different reliability
    services = {
        "reliable_service": DemoService("reliable_service"),
        "unreliable_service": DemoService("unreliable_service"),
        "failing_service": DemoService("failing_service")
    }
    
    # Configure different failure rates
    services["reliable_service"].failure_rate = 0.1  # 10% failure
    services["unreliable_service"].failure_rate = 0.4  # 40% failure
    services["failing_service"].failure_rate = 0.9  # 90% failure
    
    # Register services with health monitor
    monitor = ServiceHealthMonitor()
    for name, service in services.items():
        monitor.register_service(name, service.error_boundary.circuit_breaker.config)
    
    print("\n1. Running operations on all services:")
    
    # Run operations on all services
    for i in range(15):
        for name, service in services.items():
            result = await service.process_with_boundary(f"data_{i}")
            # Don't print individual results to keep output clean
    
    print("\n2. Health report:")
    report = monitor.generate_health_report()
    
    print(f"   Overall system health: {report['overall_health_percentage']:.1f}%")
    print(f"   Total services: {report['total_services']}")
    print(f"   Healthy services: {report['healthy_services']}")
    print(f"   Unhealthy services: {report['unhealthy_services']}")
    
    if report['unhealthy_service_names']:
        print(f"   Unhealthy service names: {', '.join(report['unhealthy_service_names'])}")
    
    print("\n3. Individual service details:")
    for name, details in report['service_details'].items():
        print(f"   {name}:")
        print(f"     Status: {details['status']}")
        print(f"     Success rate: {details['success_rate']:.1f}%")
        print(f"     Total requests: {details['total_requests']}")
        print(f"     Consecutive failures: {details['consecutive_failures']}")


async def demonstrate_decorator():
    """Demonstrate the error boundary decorator."""
    print("\n" + "="*60)
    print("DEMO 4: Error Boundary Decorator")
    print("="*60)
    
    print("\n1. Testing successful decorated function:")
    result = await decorated_demo_function(should_fail=False)
    print(f"   Result: {result}")
    
    print("\n2. Testing failing decorated function:")
    result = await decorated_demo_function(should_fail=True)
    print(f"   Result: {result}")  # Should be None due to error
    
    print("\n3. Health status of decorated service:")
    boundary = health_monitor.get_error_boundary("decorated_service")
    if boundary:
        metrics = boundary.get_health_status()
        print(f"   Status: {metrics.status.value}")
        print(f"   Success rate: {metrics.success_rate:.1f}%")
        print(f"   Total requests: {metrics.total_requests}")


async def demonstrate_service_recovery():
    """Demonstrate service recovery after failures."""
    print("\n" + "="*60)
    print("DEMO 5: Service Recovery Scenario")
    print("="*60)
    
    service = DemoService("recovery_demo")
    service.failure_rate = 0.9  # Start with high failure rate
    
    print(f"\n1. Initial service state (failure rate: {service.failure_rate:.0%}):")
    
    # Generate initial failures
    print("\n2. Generating failures:")
    for i in range(5):
        result = await service.process_with_boundary(f"initial_{i}")
        status = service.error_boundary.metrics.status.value
        print(f"   Request {i+1}: {'Failed' if result is None or 'Fallback' in result else 'Success'} (Status: {status})")
    
    print(f"\n   Service is now: {service.error_boundary.metrics.status.value}")
    
    # Gradually improve service
    print("\n3. Gradually improving service reliability:")
    for improvement in range(4):
        service.improve_reliability()
        
        # Test a few operations
        successes = 0
        for i in range(5):
            result = await service.process_with_boundary(f"recovery_{improvement}_{i}")
            if result and "Processed" in result:
                successes += 1
        
        status = service.error_boundary.metrics.status.value
        print(f"   After improvement {improvement + 1}: {successes}/5 successes (Status: {status})")
        
        if status == "healthy":
            print("   ✅ Service fully recovered!")
            break
    
    print("\n4. Final health metrics:")
    metrics = service.error_boundary.get_health_status()
    print(f"   Status: {metrics.status.value}")
    print(f"   Success rate: {metrics.success_rate:.1f}%")
    print(f"   Error rate: {metrics.error_rate:.1f}%")
    print(f"   Total requests: {metrics.total_requests}")


async def main():
    """Run all demonstrations."""
    print("🚀 Service Error Boundary System Demonstration")
    print("This demo shows error isolation, circuit breakers, and health monitoring")
    
    try:
        await demonstrate_basic_error_boundary()
        await demonstrate_circuit_breaker()
        await demonstrate_health_monitoring()
        await demonstrate_decorator()
        await demonstrate_service_recovery()
        
        print("\n" + "="*60)
        print("✅ All demonstrations completed successfully!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())