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
        
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._active_connections: set = set()
        self._connection_times: Dict[Any, float] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
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
    try:
        async with asyncio.timeout(seconds):
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
        exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.exceptions = exceptions
    
    async def __call__(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
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
        
        raise last_exception


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for async retry functionality."""
    def decorator(func):
        retry_handler = AsyncRetry(max_attempts, base_delay, max_delay, exponential_base, exceptions)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_handler(func, *args, **kwargs)
        
        return wrapper
    return decorator


class AsyncRateLimiter:
    """Async rate limiter using token bucket algorithm."""
    
    def __init__(self, rate: float, burst: int = 1):
        self.rate = rate  # tokens per second
        self.burst = burst  # maximum tokens
        self.tokens = burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket."""
        async with self._lock:
            now = time.time()
            
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Wait if not enough tokens
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens


@asynccontextmanager
async def async_rate_limit(rate: float, burst: int = 1) -> AsyncGenerator[None, None]:
    """Context manager for rate limiting."""
    limiter = AsyncRateLimiter(rate, burst)
    await limiter.acquire()
    yield


class AsyncBatch:
    """Async batch processor for efficient bulk operations."""
    
    def __init__(
        self,
        batch_size: int = 100,
        max_wait_time: float = 1.0,
        processor: Optional[Callable] = None
    ):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.processor = processor
        
        self._queue: asyncio.Queue = asyncio.Queue()
        self._batch: List[Any] = []
        self._last_process_time = time.time()
        self._processing_task: Optional[asyncio.Task] = None
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
                batch = []
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
                if batch and self.processor:
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
    
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_refs: weakref.WeakSet = weakref.WeakSet()
    
    def create_task(self, coro, name: Optional[str] = None) -> asyncio.Task:
        """Create and track an async task."""
        task = asyncio.create_task(coro, name=name)
        
        if name:
            self._tasks[name] = task
        
        self._task_refs.add(task)
        
        # Add done callback to clean up
        task.add_done_callback(self._task_done_callback)
        
        return task
    
    def _task_done_callback(self, task: asyncio.Task) -> None:
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
    
    def get_task(self, name: str) -> Optional[asyncio.Task]:
        """Get task by name."""
        return self._tasks.get(name)
    
    def cancel_task(self, name: str) -> bool:
        """Cancel task by name."""
        task = self._tasks.get(name)
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


def async_background_task(name: Optional[str] = None):
    """Decorator to run function as background task."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            coro = func(*args, **kwargs)
            return task_manager.create_task(coro, name=name or func.__name__)
        return wrapper
    return decorator


async def gather_with_concurrency(limit: int, *coroutines) -> List[Any]:
    """Execute coroutines with concurrency limit."""
    semaphore = asyncio.Semaphore(limit)
    
    async def limited_coro(coro):
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


class AsyncEventWaiter:
    """Utility for waiting on async events."""
    
    def __init__(self):
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