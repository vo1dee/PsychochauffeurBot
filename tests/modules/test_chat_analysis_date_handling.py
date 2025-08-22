"""Tests for chat analysis date handling functionality."""
import pytest
from datetime import datetime, date, time, timedelta
import pytz
from unittest.mock import AsyncMock, patch, MagicMock, ANY
import logging

from modules.chat_analysis import get_messages_for_chat_single_date

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper class to mock async context manager
class AsyncContextManagerMock:
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_timezone_handling():
    """Test that timezone handling works correctly for message retrieval."""
    # Create a mock connection with the necessary methods
    mock_conn = AsyncMock()
    
    # Mock fetchval to return test data
    async def mock_fetchval(*args, **kwargs):
        if 'COUNT(*)' in str(args[0]):
            return 1
        return datetime(2025, 8, 20, 10, 30, 0)
    
    mock_conn.fetchval = mock_fetchval
    
    # Mock fetch to return test message
    mock_conn.fetch = AsyncMock(return_value=[
        {'timestamp': datetime(2025, 8, 20, 10, 30, 0), 'username': 'testuser', 'text': 'Test message'}
    ])
    
    # Create a mock pool that returns our mock connection
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=AsyncContextManagerMock(mock_conn))
    
    # Patch the database pool
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        result = await get_messages_for_chat_single_date(
            chat_id=12345,
            target_date=date(2025, 8, 20)
        )
        
        # Verify the result
        assert len(result) == 1
        timestamp, username, text = result[0]
        assert username == 'testuser'
        assert text == 'Test message'
        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo.zone == 'Europe/Kyiv'

@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_empty_result():
    """Test handling when no messages are found for the given date."""
    # Create a mock connection
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=0)  # No messages found
    mock_conn.fetch = AsyncMock(return_value=[])
    
    # Create a mock pool that returns our mock connection
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=AsyncContextManagerMock(mock_conn))
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        result = await get_messages_for_chat_single_date(
            chat_id=12345,
            target_date=date(2025, 1, 1)
        )
        
        # Should return an empty list when no messages found
        assert result == []

@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_string_input():
    """Test that string date input is properly parsed."""
    # Create a mock connection
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)  # Found messages
    mock_conn.fetch = AsyncMock(return_value=[
        {'timestamp': datetime(2025, 12, 25, 15, 0, 0), 'username': 'santa', 'text': 'Merry Christmas!'}
    ])
    
    # Create a mock pool that returns our mock connection
    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=AsyncContextManagerMock(mock_conn))
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        # Test with string date
        result = await get_messages_for_chat_single_date(
            chat_id=54321,
            target_date="2025-12-25"
        )
        
        # Verify the result
        assert len(result) == 1
        timestamp, username, text = result[0]
        assert username == 'santa'
        assert text == 'Merry Christmas!'
        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo.zone == 'Europe/Kyiv'
