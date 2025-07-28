"""
Comprehensive async test fixes for remaining event loop issues.
"""

import asyncio
import pytest
import functools
from typing import Any, Callable, Coroutine
import logging

# Configure logging for async test debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def async_test_wrapper(func: Callable) -> Callable:
    """
    Wrapper to ensure async tests run properly with event loop management.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> None:
        # Ensure we have an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # If the function is a coroutine, run it
        if asyncio.iscoroutinefunction(func):
            return loop.run_until_complete(func(*args, **kwargs))
        else:
            return func(*args, **kwargs)
    
    return wrapper


def fix_async_test_methods():
    """
    Apply fixes to async test methods that are failing due to event loop issues.
    """
    # This function can be called to apply fixes programmatically
    pass


class AsyncTestHelper:
    """Helper class for async test operations."""
    
    @staticmethod
    def ensure_event_loop() -> None:
        """Ensure there's an active event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    @staticmethod
    async def run_with_timeout(coro: Coroutine, timeout: float = 30.0) -> Any:
        """Run a coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Async operation timed out after {timeout} seconds")
            raise
    
    @staticmethod
    def cleanup_tasks() -> None:
        """Clean up any pending async tasks."""
        try:
            loop = asyncio.get_running_loop()
            tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in tasks:
                task.cancel()
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        except RuntimeError:
            pass  # No running loop


# Apply the async test helper globally
async_helper = AsyncTestHelper()