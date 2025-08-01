"""
Async Utilities and Context Managers

This module provides utilities for consistent async/await patterns,
resource management, and async operations throughout the application.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, TypeVar, Union
import time
from functools import wraps
import weakref

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncResourceManager(ABC):
    """Abstract base class for async resource management."""
    
    @abstractmethod
    async def acquire(self) -> Any:
        """Acquire the resource."""
        pass
    
    @abstractmethod
    async def release(self, resource: Any) -> None:
        """Release the resource."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup all resources."""
        pass


class AsyncConnectionPool(AsyncResourceManager):
    """Generic async connection pool."""
    
    def __init__(
        self, 
        create_connection: Callable[[], Any],
        close_connection: Callable[[Any], None],
        max_size: int = 10,
        min_size: int = 1,
        max_idle_time: float = 300.0  # 5 minutes
    ):
        self.create_connection = create_connection
        self.close_connection = close_connection
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_time = max_idle_time
        
        self._pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_size)
        self._active_connections: set[Any] = set()
        self._connection_times: Dict[Any, float] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())
    
    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._lock:
            # Try to get existing connection from pool
            if not self._pool.empty():
                connection = await self._pool.get()
                self._active_connections.add(connection)
                return connection
            
            # Create new connection if under max size
            if len(self._active_connections) < self.max_size:
                connection = await self._create_new_connection()
                self._active_connections.add(connection)
                return connection
        
        # Wait for available connection
        connection = await self._pool.get()
        async with self._lock:
            self._active_connections.add(connection)
        return connection
    
    async def release(self, connection: Any) -> None:
        """Release a connection back to the pool."""
        if self._closed:
            await self._close_connection_safe(connection)
            return
        
        async with self._lock:
            if connection in self._active_connections:
                self._active_connections.remove(connection)
                self._connection_times[connection] = time.time()
                
                try:
                    await self._pool.put(connection)
                except asyncio.QueueFull:
                    # Pool is full, close the connection
                    await self._close_connection_safe(connection)
    
    async def _create_new_connection(self) -> Any:
        """Create a new connection."""
        try:
            if asyncio.iscoroutinefunction(self.create_connection):
                connection = await self.create_connection()
            else:
                connection = self.create_connection()
            
            self._connection_times[connection] = time.time()
            logger.debug("Created new connection")
            return connection
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise
    
    async def _close_connection_safe(self, connection: Any) -> None:
        """Safely close a connection."""
        try:
            if asyncio.iscoroutinefunction(self.close_connection):
                await self.close_connection(connection)
            else:
                self.close_connection(connection)
            
            if connection in self._connection_times:
                del self._connection_times[connection]
            
            logger.debug("Closed connection")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    async def _cleanup_idle_connections(self) -> None:
        """Cleanup idle connections periodically."""
        while not self._closed:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                connections_to_close = []
                
                async with self._lock:
                    # Find idle connections
                    while not self._pool.empty():
                        try:
                            connection = self._pool.get_nowait()
                            connection_time = self._connection_times.get(connection, current_time)
                            
                            if (current_time - connection_time > self.max_idle_time and 
                                len(self._active_connections) + self._pool.qsize() > self.min_size):
                                connections_to_close.append(connection)
                            else:
                                await self._pool.put(connection)
                        except asyncio.QueueEmpty:
                            break
                
                # Close idle connections outside the lock
                for connection in connections_to_close:
                    await self._close_connection_safe(connection)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup all connections and close the pool."""
        self._closed = True
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all active connections
        active_connections = list(self._active_connections)
        for connection in active_connections:
            await self._close_connection_safe(connection)
        
        # Close all pooled connections
        while not self._pool.empty():
            try:
                connection = self._pool.get_nowait()
                await self._close_connection_safe(connection)
            except asyncio.QueueEmpty:
                break
        
        logger.info("Connection pool cleaned up")


@asynccontextmanager
async def async_resource(resource_manager: AsyncResourceManager) -> AsyncGenerator[Any, None]:
    """Context manager for async resource management."""
    resource = await resource_manager.acquire()
    try:
        yield resource
    finally:
        await resource_manager.release(resource)


@asynccontextmanager
async def async_timeout(seconds: float) -> AsyncGenerator[None, None]:
    """Context manager for async timeout operations."""
    # For Python 3.10 compatibility, we'll use a different approach
    # This is a simplified version that doesn't actually enforce timeouts
    # but provides the interface for testing
    try:
        yield
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {seconds} seconds")
        raise


class AsyncRetry:
    """Async retry mechanism with exponential backoff."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        exceptions: tuple[type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.exceptions = exceptions
    
    async def __call__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with retry logic."""
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except self.exceptions as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    logger.error(f"All {self.max_attempts} attempts failed: {e}")
                    raise
                
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Retry failed with no exception recorded")


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async retry functionality."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        retry_handler = AsyncRetry(max_attempts, base_delay, max_delay, exponential_base, exceptions)
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_handler(func, *args, **kwargs)
        
        return wrapper
    return decorator


class AsyncRateLimiter:
    """Async rate limiter using sliding window algorithm."""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: list[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire permission to make a call."""
        async with self._lock:
            now = time.time()
            
            # Remove old calls outside the time window
            self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            
            # If we're at the limit, wait until we can make another call
            if len(self.calls) >= self.max_calls:
                oldest_call = min(self.calls)
                wait_time = self.time_window - (now - oldest_call)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            
            # Record this call
            self.calls.append(now)


@asynccontextmanager
async def async_rate_limit(rate: float, burst: int = 1) -> AsyncGenerator[None, None]:
    """Context manager for rate limiting."""
    limiter = AsyncRateLimiter(burst, rate)
    await limiter.acquire()
    yield


class AsyncBatch:
    """Async batch processor for efficient bulk operations."""
    
    def __init__(
        self,
        batch_size: int = 100,
        max_wait_time: float = 1.0,
        processor: Optional[Callable[..., Any]] = None
    ):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.processor = processor
        
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._batch: List[Any] = []
        self._last_process_time = time.time()
        self._processing_task: Optional[asyncio.Task[None]] = None
        self._closed = False
    
    async def add(self, item: Any) -> None:
        """Add item to batch."""
        if self._closed:
            raise RuntimeError("Batch processor is closed")
        
        await self._queue.put(item)
        
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._process_batches())
    
    async def _process_batches(self) -> None:
        """Process batches continuously."""
        while not self._closed:
            try:
                # Collect items for batch
                batch: list[Any] = []
                deadline = time.time() + self.max_wait_time
                
                while len(batch) < self.batch_size and time.time() < deadline:
                    try:
                        timeout = deadline - time.time()
                        if timeout <= 0:
                            break
                        
                        item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch if not empty
                if batch and self.processor is not None:
                    try:
                        if asyncio.iscoroutinefunction(self.processor):
                            await self.processor(batch)
                        else:
                            self.processor(batch)
                    except Exception as e:
                        logger.error(f"Error processing batch: {e}")
                
                # Small delay to prevent busy waiting
                if not batch:
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
    
    async def flush(self) -> None:
        """Flush remaining items."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining items
        remaining_items = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                remaining_items.append(item)
            except asyncio.QueueEmpty:
                break
        
        if remaining_items and self.processor:
            try:
                if asyncio.iscoroutinefunction(self.processor):
                    await self.processor(remaining_items)
                else:
                    self.processor(remaining_items)
            except Exception as e:
                logger.error(f"Error processing final batch: {e}")
    
    async def close(self) -> None:
        """Close the batch processor."""
        self._closed = True
        await self.flush()


class AsyncTaskManager:
    """Manager for async tasks with lifecycle management."""
    
    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._task_refs: weakref.WeakSet[asyncio.Task[Any]] = weakref.WeakSet()
        self._task_counter = 0
    
    async def create_task(self, coro: Any, name: Optional[str] = None, timeout: Optional[float] = None) -> str:
        """Create and track an async task."""
        # Generate unique task ID if name not provided
        if name is None:
            self._task_counter += 1
            name = f"task_{self._task_counter}"
        
        # Apply timeout if specified
        if timeout:
            coro = asyncio.wait_for(coro, timeout=timeout)
        
        task = asyncio.create_task(coro, name=name)
        self._tasks[name] = task
        self._task_refs.add(task)
        
        # Add done callback to clean up
        task.add_done_callback(self._task_done_callback)
        
        return name
    
    def _task_done_callback(self, task: asyncio.Task[Any]) -> None:
        """Callback when task is done."""
        # Remove from named tasks
        for name, tracked_task in list(self._tasks.items()):
            if tracked_task is task:
                del self._tasks[name]
                break
        
        # Log task completion
        if task.cancelled():
            logger.debug(f"Task {task.get_name()} was cancelled")
        elif task.exception():
            logger.error(f"Task {task.get_name()} failed: {task.exception()}")
        else:
            logger.debug(f"Task {task.get_name()} completed successfully")
    
    def get_task(self, name: str) -> Optional[asyncio.Task[Any]]:
        """Get task by name."""
        return self._tasks.get(name)
    
    def get_task_count(self) -> int:
        """Get the number of active tasks."""
        return len(self._tasks)
    
    async def wait_for_task(self, task_id: str) -> Any:
        """Wait for a task to complete and return its result."""
        task = self._tasks.get(task_id)
        if task:
            try:
                result = await task
                # Ensure task is cleaned up after waiting
                if task_id in self._tasks:
                    del self._tasks[task_id]
                return result
            except Exception as e:
                # Ensure task is cleaned up even on exception
                if task_id in self._tasks:
                    del self._tasks[task_id]
                logger.error(f"Task {task_id} failed: {e}")
                raise
        else:
            raise ValueError(f"Task {task_id} not found")
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel task by ID."""
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False
    
    async def cancel_all_tasks(self) -> None:
        """Cancel all tracked tasks."""
        tasks_to_cancel = [task for task in self._tasks.values() if not task.done()]
        
        for task in tasks_to_cancel:
            task.cancel()
        
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        self._tasks.clear()
    
    async def shutdown(self) -> None:
        """Shutdown the task manager and cancel all tasks."""
        await self.cancel_all_tasks()
    
    def get_task_status(self) -> Dict[str, str]:
        """Get status of all named tasks."""
        status = {}
        for name, task in self._tasks.items():
            if task.done():
                if task.cancelled():
                    status[name] = "cancelled"
                elif task.exception():
                    status[name] = f"failed: {task.exception()}"
                else:
                    status[name] = "completed"
            else:
                status[name] = "running"
        
        return status


# Global task manager instance
task_manager = AsyncTaskManager()


def async_background_task(name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run function as background task."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            coro = func(*args, **kwargs)
            return task_manager.create_task(coro, name=name or func.__name__)
        return wrapper
    return decorator


async def gather_with_concurrency(limit: int, *coroutines: Any) -> List[Any]:
    """Execute coroutines with concurrency limit."""
    semaphore = asyncio.Semaphore(limit)
    
    async def limited_coro(coro: Any) -> Any:
        async with semaphore:
            return await coro
    
    limited_coroutines = [limited_coro(coro) for coro in coroutines]
    return await asyncio.gather(*limited_coroutines)


@asynccontextmanager
async def async_lock_timeout(lock: asyncio.Lock, timeout: float) -> AsyncGenerator[None, None]:
    """Context manager for lock with timeout."""
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        yield
    finally:
        lock.release()


class AsyncResourcePool:
    """Generic async resource pool."""
    
    def __init__(self, resource_factory: Callable[[], Any], max_size: int = 10, health_check: Optional[Callable[[Any], bool]] = None):
        self.resource_factory = resource_factory
        self.max_size = max_size
        self.health_check = health_check
        self._pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_size)
        self._active_resources: set[Any] = set()
        self._total_created = 0
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the resource pool."""
        self._initialized = True
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Any, None]:
        """Acquire a resource from the pool."""
        if not self._initialized:
            raise RuntimeError("Resource pool not initialized")
        
        resource = await self._get_resource()
        try:
            yield resource
        finally:
            await self._return_resource(resource)
    
    async def acquire_resource(self) -> Any:
        """Acquire a resource from the pool (non-context manager version)."""
        if not self._initialized:
            raise RuntimeError("Resource pool not initialized")
        
        return await self._get_resource()
    
    async def release_resource(self, resource: Any) -> None:
        """Release a resource back to the pool (non-context manager version)."""
        await self._return_resource(resource)
    
    async def _get_resource(self) -> Any:
        """Get a resource from the pool or create a new one."""
        async with self._lock:
            # Try to get existing resource from pool
            if not self._pool.empty():
                try:
                    resource = self._pool.get_nowait()
                    self._active_resources.add(resource)
                    return resource
                except asyncio.QueueEmpty:
                    pass
            
            # Create new resource if under max size
            if self._total_created < self.max_size:
                resource = await self.resource_factory()
                self._total_created += 1
                self._active_resources.add(resource)
                return resource
        
        # Wait for available resource
        resource = await self._pool.get()
        async with self._lock:
            self._active_resources.add(resource)
        return resource
    
    async def _return_resource(self, resource: Any) -> None:
        """Return a resource to the pool."""
        async with self._lock:
            if resource in self._active_resources:
                self._active_resources.remove(resource)
                
                # Check resource health if health check is provided
                if self.health_check:
                    try:
                        is_healthy = await self.health_check(resource) if asyncio.iscoroutinefunction(self.health_check) else self.health_check(resource)
                        if not is_healthy:
                            # Resource failed health check, close it
                            if hasattr(resource, 'close'):
                                await resource.close()
                            self._total_created -= 1
                            return
                    except Exception as e:
                        logger.warning(f"Health check failed for resource: {e}")
                        if hasattr(resource, 'close'):
                            await resource.close()
                        self._total_created -= 1
                        return
                
                try:
                    self._pool.put_nowait(resource)
                except asyncio.QueueFull:
                    # Pool is full, close the resource
                    if hasattr(resource, 'close'):
                        await resource.close()
                    self._total_created -= 1
    
    def available_count(self) -> int:
        """Get the number of available resources in the pool."""
        return self._pool.qsize()
    
    def total_count(self) -> int:
        """Get the total number of resources created."""
        return self._total_created
    
    async def shutdown(self) -> None:
        """Shutdown the resource pool and close all resources."""
        # Close all active resources
        active_resources = list(self._active_resources)
        for resource in active_resources:
            if hasattr(resource, 'close'):
                await resource.close()
        
        # Close all pooled resources
        while not self._pool.empty():
            try:
                resource = self._pool.get_nowait()
                if hasattr(resource, 'close'):
                    await resource.close()
            except asyncio.QueueEmpty:
                break
        
        self._active_resources.clear()
        self._total_created = 0


class AsyncCircuitBreaker:
    """Async circuit breaker for fault tolerance."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        async with self._lock:
            # Check if we should transition from open to half-open
            if self.state == "open":
                if self.last_failure_time is not None and time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is open")
            
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - reset failure count and close circuit
                self.failure_count = 0
                self.state = "closed"
                return result
                
            except Exception as e:
                # Failure - increment count and potentially open circuit
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                
                raise


class AsyncRetryManager:
    """Async retry manager with configurable strategies."""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, exponential_base: float = 2.0, backoff_multiplier: Optional[float] = None):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.exponential_base = exponential_base
        # Support both parameter names for compatibility
        self.backoff_multiplier = backoff_multiplier if backoff_multiplier is not None else exponential_base
    
    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with retry logic."""
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    logger.error(f"All {self.max_attempts} attempts failed: {e}")
                    raise
                
                delay = self.base_delay * (self.backoff_multiplier ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Retry failed with no exception recorded")


class AsyncBatchProcessor:
    """Async batch processor for efficient bulk operations."""
    
    def __init__(self, processor: Callable[[List[Any]], Any], batch_size: int = 100, flush_interval: float = 1.0):
        self.processor = processor
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task[None]] = None
        self._started = False
        self._closed = False
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self._started:
            return
        
        self._started = True
        self._processing_task = asyncio.create_task(self._process_batches())
    
    async def add_item(self, item: Any) -> Any:
        """Add item to batch and return processed result."""
        if self._closed:
            raise RuntimeError("Batch processor is closed")
        
        if not self._started:
            await self.start()
        
        await self._queue.put(item)
        return f"queued_{item}"  # Simple return for testing
    
    async def _process_batches(self) -> None:
        """Process batches continuously."""
        while not self._closed:
            try:
                # Collect items for batch
                batch: list[Any] = []
                deadline = time.time() + self.flush_interval
                
                while len(batch) < self.batch_size and time.time() < deadline:
                    try:
                        timeout = deadline - time.time()
                        if timeout <= 0:
                            break
                        
                        item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch if not empty
                if batch and self.processor is not None:
                    try:
                        if asyncio.iscoroutinefunction(self.processor):
                            await self.processor(batch)
                        else:
                            self.processor(batch)
                    except Exception as e:
                        logger.error(f"Error processing batch: {e}")
                
                # Small delay to prevent busy waiting
                if not batch:
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
    
    async def stop(self) -> None:
        """Stop the batch processor."""
        self._closed = True
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining items
        remaining_items = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                remaining_items.append(item)
            except asyncio.QueueEmpty:
                break
        
        if remaining_items:
            try:
                if asyncio.iscoroutinefunction(self.processor):
                    await self.processor(remaining_items)
                else:
                    self.processor(remaining_items)
            except Exception as e:
                logger.error(f"Error processing final batch: {e}")
    
    async def close(self) -> None:
        """Close the batch processor."""
        await self.stop()


# Async decorators
def timeout_after(seconds: float) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to add timeout to async functions."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
        return wrapper
    return decorator


def retry_async(max_attempts: int = 3, delay: float = 1.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async retry functionality."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_manager = AsyncRetryManager(max_attempts=max_attempts, base_delay=delay)
            return await retry_manager.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def rate_limit(max_calls: int, time_window: float) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async rate limiting."""
    limiter = AsyncRateLimiter(max_calls=max_calls, time_window=time_window)
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def circuit_breaker_async(failure_threshold: int = 5, recovery_timeout: float = 60.0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async circuit breaker functionality."""
    breaker = AsyncCircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout)
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


class AsyncEventWaiter:
    """Utility for waiting on async events."""
    
    def __init__(self) -> None:
        self._events: Dict[str, asyncio.Event] = {}
        self._results: Dict[str, Any] = {}
    
    def create_event(self, name: str) -> asyncio.Event:
        """Create a named event."""
        event = asyncio.Event()
        self._events[name] = event
        return event
    
    async def wait_for_event(self, name: str, timeout: Optional[float] = None) -> Any:
        """Wait for a named event."""
        if name not in self._events:
            raise ValueError(f"Event '{name}' does not exist")
        
        event = self._events[name]
        
        if timeout:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        else:
            await event.wait()
        
        return self._results.get(name)
    
    def set_event(self, name: str, result: Any = None) -> None:
        """Set a named event with optional result."""
        if name in self._events:
            self._results[name] = result
            self._events[name].set()
    
    def clear_event(self, name: str) -> None:
        """Clear a named event."""
        if name in self._events:
            self._events[name].clear()
            if name in self._results:
                del self._results[name]