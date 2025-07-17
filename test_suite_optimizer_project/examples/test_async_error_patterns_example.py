
import pytest
import asyncio

class TestAsyncErrorPatternsReal:
    """Real test file for async error handling patterns."""
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout error handling."""
        async def slow_op():
            await asyncio.sleep(1.0)
            return "done"
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_op(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_retry_pattern(self):
        """Test retry pattern implementation."""
        attempts = 0
        
        async def flaky_operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionError("Failed")
            return "success"
        
        # Implement retry logic
        for i in range(3):
            try:
                result = await flaky_operation()
                break
            except ConnectionError:
                if i == 2:
                    raise
        
        assert result == "success"
        assert attempts == 3
