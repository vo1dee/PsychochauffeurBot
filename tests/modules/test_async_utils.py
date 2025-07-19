"""
Unit tests for async utilities and patterns.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Any

from modules.async_utils import (
    AsyncTaskManager, AsyncConnectionPool, AsyncRateLimiter,
    AsyncRetry, AsyncBatch, AsyncEventWaiter, AsyncResourcePool,
    AsyncCircuitBreaker, AsyncRetryManager, AsyncBatchProcessor,
    async_timeout, async_retry, async_rate_limit,
    timeout_after, retry_async, rate_limit, circuit_breaker_async
)


class TestAsyncTaskManager:
    """Test cases for AsyncTaskManager."""
    
    @pytest.fixture
    def task_manager(self):
        """Create an AsyncTaskManager instance."""
        return AsyncTaskManager()
    
    @pytest.mark.asyncio
    async def test_task_creation_and_tracking(self, task_manager) -> None:
        """Test task creation and tracking."""
        async def test_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        task_id = await task_manager.create_task(test_task(), name="test_task")
        assert task_id is not None
        assert task_manager.get_task_count() == 1
        
        # Wait for completion
        result = await task_manager.wait_for_task(task_id)
        assert result == "completed"
        assert task_manager.get_task_count() == 0
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self, task_manager) -> None:
        """Test task cancellation."""
        async def long_running_task():
            await asyncio.sleep(10)
            return "should_not_complete"
        
        task_id = await task_manager.create_task(long_running_task(), name="long_task")
        
        # Cancel the task
        success = await task_manager.cancel_task(task_id)
        assert success
        
        # Task should be cancelled
        with pytest.raises(asyncio.CancelledError):
            await task_manager.wait_for_task(task_id)
    
    @pytest.mark.asyncio
    async def test_task_timeout(self, task_manager):
        """Test task timeout handling."""
        async def slow_task():
            await asyncio.sleep(1)
            return "completed"
        
        task_id = await task_manager.create_task(slow_task(), name="slow_task", timeout=0.1)
        
        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await task_manager.wait_for_task(task_id)
    
    @pytest.mark.asyncio
    async def test_concurrent_tasks(self, task_manager):
        """Test handling multiple concurrent tasks."""
        async def numbered_task(number: int):
            await asyncio.sleep(0.1)
            return f"task_{number}"
        
        # Create multiple tasks
        task_ids = []
        for i in range(5):
            task_id = await task_manager.create_task(
                numbered_task(i), name=f"task_{i}"
            )
            task_ids.append(task_id)
        
        assert task_manager.get_task_count() == 5
        
        # Wait for all tasks
        results = []
        for task_id in task_ids:
            result = await task_manager.wait_for_task(task_id)
            results.append(result)
        
        assert len(results) == 5
        assert all(f"task_{i}" in results for i in range(5))
        assert task_manager.get_task_count() == 0
    
    @pytest.mark.asyncio
    async def test_task_error_handling(self, task_manager):
        """Test task error handling."""
        async def failing_task():
            raise ValueError("Task failed")
        
        task_id = await task_manager.create_task(failing_task(), name="failing_task")
        
        # Should propagate the exception
        with pytest.raises(ValueError, match="Task failed"):
            await task_manager.wait_for_task(task_id)
    
    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self, task_manager):
        """Test cleanup of completed tasks."""
        async def quick_task():
            return "done"
        
        # Create and complete several tasks
        for i in range(3):
            task_id = await task_manager.create_task(quick_task(), name=f"quick_{i}")
            await task_manager.wait_for_task(task_id)
        
        # All tasks should be cleaned up
        assert task_manager.get_task_count() == 0
    
    @pytest.mark.asyncio
    async def test_shutdown(self, task_manager):
        """Test task manager shutdown."""
        async def persistent_task():
            await asyncio.sleep(10)
            return "done"
        
        # Create some tasks
        for i in range(3):
            await task_manager.create_task(persistent_task(), name=f"persistent_{i}")
        
        assert task_manager.get_task_count() == 3
        
        # Shutdown should cancel all tasks
        await task_manager.shutdown()
        assert task_manager.get_task_count() == 0


class TestAsyncResourcePool:
    """Test cases for AsyncResourcePool."""
    
    class MockResource:
        """Mock resource for testing."""
        def __init__(self, resource_id: str):
            self.id = resource_id
            self.in_use = False
            self.closed = False
        
        async def close(self):
            self.closed = True
    
    @pytest.fixture
    def resource_factory(self):
        """Factory function for creating mock resources."""
        counter = 0
        
        async def factory():
            nonlocal counter
            counter += 1
            return self.MockResource(f"resource_{counter}")
        
        return factory
    
    @pytest.mark.asyncio
    async def test_resource_acquisition_and_release(self, resource_factory):
        """Test resource acquisition and release."""
        pool = AsyncResourcePool(resource_factory, max_size=3)
        await pool.initialize()
        
        # Acquire resource
        async with pool.acquire() as resource:
            assert isinstance(resource, self.MockResource)
            assert resource.id == "resource_1"
        
        # Resource should be returned to pool
        assert pool.available_count() == 1
        assert pool.total_count() == 1
        
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_pool_size_limit(self, resource_factory):
        """Test pool size limit enforcement."""
        pool = AsyncResourcePool(resource_factory, max_size=2)
        await pool.initialize()
        
        # Acquire all resources
        resource1 = await pool.acquire_resource()
        resource2 = await pool.acquire_resource()
        
        assert pool.available_count() == 0
        assert pool.total_count() == 2
        
        # Third acquisition should wait
        acquire_task = asyncio.create_task(pool.acquire_resource())
        await asyncio.sleep(0.1)  # Give it time to try
        assert not acquire_task.done()
        
        # Release one resource
        await pool.release_resource(resource1)
        
        # Now third acquisition should complete
        resource3 = await acquire_task
        assert resource3 is resource1  # Should reuse the released resource
        
        await pool.release_resource(resource2)
        await pool.release_resource(resource3)
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_resource_health_check(self, resource_factory):
        """Test resource health checking."""
        async def health_check(resource):
            return not resource.closed
        
        pool = AsyncResourcePool(
            resource_factory, 
            max_size=2, 
            health_check=health_check
        )
        await pool.initialize()
        
        # Acquire and "damage" a resource
        resource = await pool.acquire_resource()
        resource.closed = True
        await pool.release_resource(resource)
        
        # Next acquisition should get a new resource (old one failed health check)
        new_resource = await pool.acquire_resource()
        assert new_resource.id != resource.id
        assert not new_resource.closed
        
        await pool.release_resource(new_resource)
        await pool.shutdown()
    
    @pytest.mark.asyncio
    async def test_pool_shutdown(self, resource_factory):
        """Test pool shutdown and resource cleanup."""
        pool = AsyncResourcePool(resource_factory, max_size=3)
        await pool.initialize()
        
        # Create some resources
        resources = []
        for _ in range(3):
            resource = await pool.acquire_resource()
            resources.append(resource)
        
        # Release them back to pool
        for resource in resources:
            await pool.release_resource(resource)
        
        assert pool.total_count() == 3
        
        # Shutdown should close all resources
        await pool.shutdown()
        
        for resource in resources:
            assert resource.closed


class TestAsyncRateLimiter:
    """Test cases for AsyncRateLimiter."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test basic rate limiting functionality."""
        limiter = AsyncRateLimiter(max_calls=2, time_window=1.0)
        
        start_time = time.time()
        
        # First two calls should be immediate
        await limiter.acquire()
        await limiter.acquire()
        
        # Third call should be delayed
        await limiter.acquire()
        
        elapsed = time.time() - start_time
        assert elapsed >= 1.0  # Should have waited for window reset
    
    @pytest.mark.asyncio
    async def test_rate_limiter_reset(self):
        """Test rate limiter window reset."""
        limiter = AsyncRateLimiter(max_calls=1, time_window=0.5)
        
        # First call
        await limiter.acquire()
        
        # Wait for window reset
        await asyncio.sleep(0.6)
        
        # Second call should be immediate (new window)
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # Should be immediate
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """Test rate limiting with concurrent requests."""
        limiter = AsyncRateLimiter(max_calls=3, time_window=1.0)
        
        async def make_request(request_id: int):
            await limiter.acquire()
            return request_id
        
        start_time = time.time()
        
        # Make 5 concurrent requests
        tasks = [make_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        
        # Should have taken at least 1 second (for the rate limit reset)
        assert elapsed >= 1.0
        assert len(results) == 5
        assert results == list(range(5))


class TestAsyncCircuitBreaker:
    """Test cases for AsyncCircuitBreaker."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        
        async def successful_operation():
            return "success"
        
        # Multiple successful calls should work
        for _ in range(5):
            result = await breaker.call(successful_operation)
            assert result == "success"
        
        assert breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opening after failure threshold."""
        breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        
        async def failing_operation():
            raise ValueError("Operation failed")
        
        # First two failures should raise original exception
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_operation)
        
        assert breaker.state == "open"
        
        # Third call should raise circuit breaker exception
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await breaker.call(failing_operation)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_then_succeeding_operation():
            if not hasattr(failing_then_succeeding_operation, 'call_count'):
                failing_then_succeeding_operation.call_count = 0
            failing_then_succeeding_operation.call_count += 1
            
            if failing_then_succeeding_operation.call_count <= 1:
                raise ValueError("Initial failure")
            return "success"
        
        # Trigger circuit opening
        with pytest.raises(ValueError):
            await breaker.call(failing_then_succeeding_operation)
        
        assert breaker.state == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Next call should succeed and close circuit
        result = await breaker.call(failing_then_succeeding_operation)
        assert result == "success"
        assert breaker.state == "closed"


class TestAsyncRetryManager:
    """Test cases for AsyncRetryManager."""
    
    @pytest.mark.asyncio
    async def test_successful_retry(self):
        """Test retry manager with eventual success."""
        retry_manager = AsyncRetryManager(max_attempts=3, base_delay=0.1)
        
        call_count = 0
        
        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await retry_manager.execute(eventually_successful_operation)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test retry manager when all attempts fail."""
        retry_manager = AsyncRetryManager(max_attempts=2, base_delay=0.1)
        
        async def always_failing_operation():
            raise ValueError("Persistent failure")
        
        with pytest.raises(ValueError, match="Persistent failure"):
            await retry_manager.execute(always_failing_operation)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        retry_manager = AsyncRetryManager(
            max_attempts=3, 
            base_delay=0.1, 
            backoff_multiplier=2.0
        )
        
        delays = []
        original_sleep = asyncio.sleep
        
        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.01)  # Short actual delay for testing
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Failure")
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with pytest.raises(ConnectionError):
                await retry_manager.execute(failing_operation)
        
        # Should have exponential backoff: 0.1, 0.2
        assert len(delays) == 2
        assert delays[0] == 0.1
        assert delays[1] == 0.2


class TestAsyncBatchProcessor:
    """Test cases for AsyncBatchProcessor."""
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test basic batch processing functionality."""
        processed_batches = []
        
        async def batch_processor(batch: List[Any]):
            processed_batches.append(batch.copy())
            return [f"processed_{item}" for item in batch]
        
        processor = AsyncBatchProcessor(
            batch_processor, 
            batch_size=3, 
            flush_interval=1.0
        )
        
        await processor.start()
        
        # Add items
        results = []
        for i in range(5):
            result = await processor.add_item(f"item_{i}")
            results.append(result)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Should have processed in batches
        assert len(processed_batches) >= 1
        assert len(results) == 5
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_batch_size_trigger(self):
        """Test batch processing triggered by size."""
        processed_batches = []
        
        async def batch_processor(batch: List[Any]):
            processed_batches.append(len(batch))
            return [f"processed_{item}" for item in batch]
        
        processor = AsyncBatchProcessor(
            batch_processor, 
            batch_size=2, 
            flush_interval=10.0  # Long interval to test size trigger
        )
        
        await processor.start()
        
        # Add exactly batch_size items
        await processor.add_item("item1")
        await processor.add_item("item2")
        
        # Should trigger processing immediately
        await asyncio.sleep(0.1)
        
        assert len(processed_batches) == 1
        assert processed_batches[0] == 2
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_flush_interval_trigger(self):
        """Test batch processing triggered by time interval."""
        processed_batches = []
        
        async def batch_processor(batch: List[Any]):
            processed_batches.append(len(batch))
            return [f"processed_{item}" for item in batch]
        
        processor = AsyncBatchProcessor(
            batch_processor, 
            batch_size=10,  # Large batch size
            flush_interval=0.2  # Short interval
        )
        
        await processor.start()
        
        # Add fewer items than batch size
        await processor.add_item("item1")
        
        # Wait for flush interval
        await asyncio.sleep(0.3)
        
        # Should have processed due to time trigger
        assert len(processed_batches) == 1
        assert processed_batches[0] == 1
        
        await processor.stop()


class TestAsyncDecorators:
    """Test cases for async decorators."""
    
    @pytest.mark.asyncio
    async def test_timeout_after_decorator(self):
        """Test timeout_after decorator."""
        @timeout_after(0.1)
        async def slow_function():
            await asyncio.sleep(1)
            return "completed"
        
        with pytest.raises(asyncio.TimeoutError):
            await slow_function()
    
    @pytest.mark.asyncio
    async def test_timeout_after_success(self):
        """Test timeout_after decorator with successful completion."""
        @timeout_after(1.0)
        async def fast_function():
            await asyncio.sleep(0.1)
            return "completed"
        
        result = await fast_function()
        assert result == "completed"
    
    @pytest.mark.asyncio
    async def test_retry_async_decorator(self):
        """Test retry_async decorator."""
        call_count = 0
        
        @retry_async(max_attempts=3, delay=0.1)
        async def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await eventually_successful()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator(self):
        """Test rate_limit decorator."""
        @rate_limit(max_calls=2, time_window=0.5)
        async def limited_function():
            return "called"
        
        start_time = time.time()
        
        # First two calls should be fast
        await limited_function()
        await limited_function()
        
        # Third call should be delayed
        await limited_function()
        
        elapsed = time.time() - start_time
        assert elapsed >= 0.5
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_async_decorator(self):
        """Test circuit_breaker_async decorator."""
        call_count = 0
        
        @circuit_breaker_async(failure_threshold=2, recovery_timeout=0.1)
        async def unreliable_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Failure")
            return "success"
        
        # First two calls should fail with original exception
        for _ in range(2):
            with pytest.raises(ValueError):
                await unreliable_function()
        
        # Third call should fail with circuit breaker exception
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await unreliable_function()
        
        # Wait for recovery
        await asyncio.sleep(0.2)
        
        # Should succeed after recovery
        result = await unreliable_function()
        assert result == "success"


class TestAsyncUtilsIntegration:
    """Integration tests for async utilities."""
    
    @pytest.mark.asyncio
    async def test_combined_async_patterns(self):
        """Test combining multiple async patterns."""
        # Simulate a service that uses multiple async patterns
        
        class AsyncService:
            def __init__(self):
                self.task_manager = AsyncTaskManager()
                self.rate_limiter = AsyncRateLimiter(max_calls=5, time_window=1.0)
                self.circuit_breaker = AsyncCircuitBreaker(
                    failure_threshold=3, 
                    recovery_timeout=1.0
                )
                self.retry_manager = AsyncRetryManager(max_attempts=3, base_delay=0.1)
            
            async def process_request(self, request_id: str):
                # Rate limiting
                await self.rate_limiter.acquire()
                
                # Circuit breaker protection
                async def protected_operation():
                    # Retry logic for transient failures
                    async def processing_func():
                        return await self._actual_processing(request_id)
                    return await self.retry_manager.execute(processing_func)
                
                return await self.circuit_breaker.call(protected_operation)
            
            async def _actual_processing(self, request_id: str):
                # Simulate some processing
                await asyncio.sleep(0.01)
                return f"processed_{request_id}"
            
            async def shutdown(self):
                await self.task_manager.shutdown()
        
        service = AsyncService()
        
        # Process multiple requests concurrently
        tasks = []
        for i in range(10):
            task = asyncio.create_task(service.process_request(f"req_{i}"))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(result.startswith("processed_req_") for result in results)
        
        await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_error_propagation_through_async_layers(self):
        """Test error propagation through multiple async layers."""
        
        @circuit_breaker_async(failure_threshold=2, recovery_timeout=0.1)
        @retry_async(max_attempts=2, delay=0.01)
        @timeout_after(1.0)
        async def layered_function(should_fail: bool = True):
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"
        
        # Should fail through all layers
        with pytest.raises(ValueError):
            await layered_function(True)
        
        # Should succeed when not failing
        result = await layered_function(False)
        assert result == "success"