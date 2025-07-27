"""
Test to verify that pytest-asyncio is properly configured and working.
"""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_async_basic():
    """Test basic async functionality."""
    result = await asyncio.sleep(0.01, result="test_passed")
    assert result == "test_passed"


@pytest.mark.asyncio
async def test_async_coroutine():
    """Test async coroutine execution."""
    async def sample_coroutine():
        await asyncio.sleep(0.01)
        return "coroutine_result"
    
    result = await sample_coroutine()
    assert result == "coroutine_result"


@pytest.mark.asyncio
async def test_async_exception_handling():
    """Test async exception handling."""
    async def failing_coroutine():
        await asyncio.sleep(0.01)
        raise ValueError("Test exception")
    
    with pytest.raises(ValueError, match="Test exception"):
        await failing_coroutine()


def test_sync_test_still_works():
    """Ensure sync tests still work alongside async tests."""
    assert True