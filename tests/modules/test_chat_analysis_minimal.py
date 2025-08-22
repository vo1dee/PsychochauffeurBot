"""Tests for chat analysis date handling functionality."""
import pytest
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytz

from modules.chat_analysis import get_messages_for_chat_single_date

# Helper function to create a mock connection with specific return values
def create_mock_connection(count=1, messages=None, min_date=None, max_date=None):
    if messages is None:
        messages = [{'timestamp': datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), 
                    'username': 'test', 'text': 'test'}]
    
    if min_date is None:
        min_date = datetime(2025, 1, 1, 0, 0)
    if max_date is None:
        max_date = datetime(2025, 1, 1, 23, 59, 59)
    
    mock_conn = AsyncMock()
    
    async def mock_fetchval(query, *args, **kwargs):
        if 'COUNT' in query:
            return count
        elif 'MIN' in query:
            return min_date
        elif 'MAX' in query:
            return max_date
        return 1
    
    mock_conn.fetchval = mock_fetchval
    mock_conn.fetch = AsyncMock(return_value=messages)
    return mock_conn

# Create an async context manager for the connection
class AsyncContextManager:
    def __init__(self, conn):
        self.conn = conn
    
    async def __aenter__(self):
        return self.conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

# Test with valid date and messages
@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date():
    # Setup
    mock_conn = create_mock_connection()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncContextManager(mock_conn)
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        # Test
        result = await get_messages_for_chat_single_date(
            chat_id=123,
            target_date=date(2025, 1, 1)
        )
        
        # Verify
        assert len(result) == 1
        assert result[0][1] == 'test'  # username
        assert result[0][2] == 'test'  # text
        assert result[0][0].tzinfo is not None  # timestamp has timezone info

# Test with empty result
@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_empty():
    # Setup
    mock_conn = create_mock_connection(count=0, messages=[])
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncContextManager(mock_conn)
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        # Test
        result = await get_messages_for_chat_single_date(
            chat_id=123,
            target_date=date(2025, 1, 1)
        )
        
        # Verify
        assert result == []

# Test with string date input
@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_string_input():
    # Setup
    test_date = "2025-01-01"
    mock_conn = create_mock_connection()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncContextManager(mock_conn)
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        # Test with string date
        result = await get_messages_for_chat_single_date(
            chat_id=123,
            target_date=test_date
        )
        
        # Verify
        assert len(result) == 1
        assert result[0][1] == 'test'  # username
        assert result[0][2] == 'test'  # text

# Test timezone handling
@pytest.mark.asyncio
async def test_get_messages_for_chat_single_date_timezone():
    # Setup - create a message in UTC
    utc_time = datetime(2025, 1, 1, 22, 0, tzinfo=timezone.utc)  # 22:00 UTC
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    kyiv_time = utc_time.astimezone(kyiv_tz)
    
    mock_conn = create_mock_connection(
        messages=[{'timestamp': utc_time, 'username': 'test', 'text': 'test'}]
    )
    
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = AsyncContextManager(mock_conn)
    
    with patch('modules.chat_analysis.Database.get_pool', return_value=mock_pool):
        # Test with date that includes our test time in Kyiv timezone
        result = await get_messages_for_chat_single_date(
            chat_id=123,
            target_date=kyiv_time.date()
        )
        
        # Verify the timestamp was properly converted to Kyiv timezone
        assert len(result) == 1
        result_time = result[0][0]  # Get timestamp from result
        assert result_time.tzinfo is not None
        assert result_time.hour == kyiv_time.hour
        assert result_time.tzinfo.zone == 'Europe/Kyiv'
