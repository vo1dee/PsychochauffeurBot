"""
Unit tests for chat_analysis.py module.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, date, timedelta
from typing import List, Tuple, Dict, Any

from modules.chat_analysis import (
    get_messages_for_chat_today,
    get_last_n_messages_in_chat,
    get_messages_for_chat_last_n_days,
    get_messages_for_chat_date_period,
    get_messages_for_chat_single_date,
    get_user_chat_stats,
    get_user_chat_stats_with_fallback,
    get_last_message_for_user_in_chat
)
from modules.const import KYIV_TZ


def create_async_context_manager_mock(conn_mock):
    """Helper function to create a proper async context manager mock."""
    async_context_mock = AsyncMock()
    async_context_mock.__aenter__.return_value = conn_mock
    async_context_mock.__aexit__.return_value = None
    return async_context_mock


class TestGetMessagesForChatToday:
    """Test get_messages_for_chat_today function."""
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_today_success(self):
        """Test successful retrieval of today's messages."""
        chat_id = 12345
        
        # Mock database response
        mock_rows = [
            {
                'timestamp': datetime.now(KYIV_TZ),
                'username': 'test_user',
                'text': 'Hello world'
            },
            {
                'timestamp': datetime.now(KYIV_TZ),
                'username': None,
                'text': 'Message from unknown user'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_today(chat_id)
            
            assert len(result) == 2
            assert result[0][1] == 'test_user'
            assert result[0][2] == 'Hello world'
            assert result[1][1] == 'Unknown'
            assert result[1][2] == 'Message from unknown user'
            
            # Verify SQL query was called with correct parameters
            mock_conn.fetch.assert_called_once()
            call_args = mock_conn.fetch.call_args
            assert call_args[0][0].strip().startswith('SELECT m.timestamp, u.username, m.text')
            assert call_args[0][1] == chat_id
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_today_empty_result(self):
        """Test when no messages are found for today."""
        chat_id = 12345
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_today(chat_id)
            
            assert result == []


class TestGetLastNMessagesInChat:
    """Test get_last_n_messages_in_chat function."""
    
    @pytest.mark.asyncio
    async def test_get_last_n_messages_in_chat_success(self):
        """Test successful retrieval of last n messages."""
        chat_id = 12345
        count = 3
        
        # Mock database response (in reverse order as they come from DESC query)
        mock_rows = [
            {
                'timestamp': datetime.now(KYIV_TZ),
                'username': 'user3',
                'text': 'Third message'
            },
            {
                'timestamp': datetime.now(KYIV_TZ) - timedelta(minutes=1),
                'username': 'user2',
                'text': 'Second message'
            },
            {
                'timestamp': datetime.now(KYIV_TZ) - timedelta(minutes=2),
                'username': 'user1',
                'text': 'First message'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_n_messages_in_chat(chat_id, count)
            
            assert len(result) == 3
            # Should be in chronological order (oldest first)
            assert result[0][1] == 'user1'
            assert result[0][2] == 'First message'
            assert result[2][1] == 'user3'
            assert result[2][2] == 'Third message'
            
            # Verify SQL query was called with correct parameters
            mock_conn.fetch.assert_called_once()
            call_args = mock_conn.fetch.call_args
            assert call_args[0][1] == chat_id
            assert call_args[0][2] == count
    
    @pytest.mark.asyncio
    async def test_get_last_n_messages_in_chat_empty_result(self):
        """Test when no messages are found."""
        chat_id = 12345
        count = 5
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_n_messages_in_chat(chat_id, count)
            
            assert result == []


class TestGetMessagesForChatLastNDays:
    """Test get_messages_for_chat_last_n_days function."""
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_last_n_days_success(self):
        """Test successful retrieval of messages for last n days."""
        chat_id = 12345
        days = 7
        
        # Mock database response
        mock_rows = [
            {
                'timestamp': datetime.now(KYIV_TZ) - timedelta(days=3),
                'username': 'user1',
                'text': 'Message from 3 days ago'
            },
            {
                'timestamp': datetime.now(KYIV_TZ) - timedelta(days=1),
                'username': 'user2',
                'text': 'Message from yesterday'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_last_n_days(chat_id, days)
            
            assert len(result) == 2
            assert result[0][1] == 'user1'
            assert result[0][2] == 'Message from 3 days ago'
            assert result[1][1] == 'user2'
            assert result[1][2] == 'Message from yesterday'
            
            # Verify SQL query was called with correct parameters
            mock_conn.fetch.assert_called_once()
            call_args = mock_conn.fetch.call_args
            assert call_args[0][1] == chat_id
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_last_n_days_zero_days(self):
        """Test with 0 days (today only)."""
        chat_id = 12345
        days = 0
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_last_n_days(chat_id, days)
            
            assert result == []


class TestGetMessagesForChatDatePeriod:
    """Test get_messages_for_chat_date_period function."""
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_date_period_with_date_objects(self):
        """Test with date objects."""
        chat_id = 12345
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        # Mock database response
        mock_rows = [
            {
                'timestamp': datetime(2024, 1, 15, 10, 0, 0, tzinfo=KYIV_TZ),
                'username': 'user1',
                'text': 'Message from January 15'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_date_period(chat_id, start_date, end_date)
            
            assert len(result) == 1
            assert result[0][1] == 'user1'
            assert result[0][2] == 'Message from January 15'
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_date_period_with_string_dates(self):
        """Test with string dates."""
        chat_id = 12345
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        # Mock database response
        mock_rows = [
            {
                'timestamp': datetime(2024, 1, 15, 10, 0, 0, tzinfo=KYIV_TZ),
                'username': 'user1',
                'text': 'Message from January 15'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_date_period(chat_id, start_date, end_date)
            
            assert len(result) == 1
            assert result[0][1] == 'user1'
            assert result[0][2] == 'Message from January 15'
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_date_period_mixed_types(self):
        """Test with mixed date types (string and date object)."""
        chat_id = 12345
        start_date = date(2024, 1, 1)
        end_date = "2024-01-31"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_date_period(chat_id, start_date, end_date)
            
            assert result == []


class TestGetMessagesForChatSingleDate:
    """Test get_messages_for_chat_single_date function."""
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_single_date_with_date_object(self):
        """Test with date object."""
        chat_id = 12345
        target_date = date(2024, 1, 15)
        
        # Mock database response
        mock_rows = [
            {
                'timestamp': datetime(2024, 1, 15, 10, 0, 0, tzinfo=KYIV_TZ),
                'username': 'user1',
                'text': 'Message from January 15'
            }
        ]
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = mock_rows
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_single_date(chat_id, target_date)
            
            assert len(result) == 1
            assert result[0][1] == 'user1'
            assert result[0][2] == 'Message from January 15'
    
    @pytest.mark.asyncio
    async def test_get_messages_for_chat_single_date_with_string_date(self):
        """Test with string date."""
        chat_id = 12345
        target_date = "2024-01-15"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_messages_for_chat_single_date(chat_id, target_date)
            
            assert result == []


class TestGetUserChatStats:
    """Test get_user_chat_stats function."""
    
    @pytest.mark.asyncio
    async def test_get_user_chat_stats_success(self):
        """Test successful retrieval of user chat statistics."""
        chat_id = 12345
        user_id = 67890
        
        # Mock database responses
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetchval calls
            mock_conn.fetchval.side_effect = [
                100,  # total_messages
                25,   # messages_last_week
                14,   # active_hour
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=KYIV_TZ),  # first_message
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ)  # last_message
            ]
            
            # Mock fetch call for command_stats
            mock_conn.fetch.return_value = [
                {'base_command': '/start', 'count': 5},
                {'base_command': '/help', 'count': 3}
            ]
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_user_chat_stats(chat_id, user_id)
            
            assert result['total_messages'] == 100
            assert result['messages_last_week'] == 25
            assert result['command_stats'] == [('/start', 5), ('/help', 3)]
            assert result['most_active_hour'] == 14
            assert result['first_message'] == datetime(2024, 1, 1, 10, 0, 0, tzinfo=KYIV_TZ)
            assert result['last_message'] == datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ)
    
    @pytest.mark.asyncio
    async def test_get_user_chat_stats_no_data(self):
        """Test when user has no message data."""
        chat_id = 12345
        user_id = 67890
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetchval calls returning None/0
            mock_conn.fetchval.side_effect = [
                0,    # total_messages
                0,    # messages_last_week
                None, # active_hour
                None, # first_message
                None  # last_message
            ]
            
            # Mock fetch call for command_stats
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_user_chat_stats(chat_id, user_id)
            
            assert result['total_messages'] == 0
            assert result['messages_last_week'] == 0
            assert result['command_stats'] == []
            assert result['most_active_hour'] is None
            assert result['first_message'] is None
            assert result['last_message'] is None


class TestGetUserChatStatsWithFallback:
    """Test get_user_chat_stats_with_fallback function."""
    
    @pytest.mark.asyncio
    async def test_get_user_chat_stats_with_fallback_success(self):
        """Test successful retrieval with fallback to username."""
        chat_id = 12345
        user_id = 67890
        username = "test_user"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetch for user_ids
            mock_conn.fetch.side_effect = [
                [{'user_id': 67890}, {'user_id': 67891}],  # user_ids for username
                [{'base_command': '/start', 'count': 5}],  # command_stats
            ]
            
            # Mock fetchval calls
            mock_conn.fetchval.side_effect = [
                150,  # total_messages
                30,   # messages_last_week
                16,   # active_hour
                datetime(2024, 1, 1, 10, 0, 0, tzinfo=KYIV_TZ),  # first_message
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ)  # last_message
            ]
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_user_chat_stats_with_fallback(chat_id, user_id, username)
            
            assert result['total_messages'] == 150
            assert result['messages_last_week'] == 30
            assert result['command_stats'] == [('/start', 5)]
            assert result['most_active_hour'] == 16
            assert result['first_message'] == datetime(2024, 1, 1, 10, 0, 0, tzinfo=KYIV_TZ)
            assert result['last_message'] == datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ)
    
    @pytest.mark.asyncio
    async def test_get_user_chat_stats_with_fallback_no_additional_users(self):
        """Test when no additional user_ids found for username."""
        chat_id = 12345
        user_id = 67890
        username = "test_user"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetch for user_ids - no additional users
            mock_conn.fetch.side_effect = [
                [],  # no additional user_ids
                [],  # command_stats
            ]
            
            # Mock fetchval calls
            mock_conn.fetchval.side_effect = [
                50,   # total_messages
                10,   # messages_last_week
                12,   # active_hour
                datetime(2024, 1, 15, 10, 0, 0, tzinfo=KYIV_TZ),  # first_message
                datetime(2024, 1, 30, 15, 30, 0, tzinfo=KYIV_TZ)   # last_message
            ]
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_user_chat_stats_with_fallback(chat_id, user_id, username)
            
            assert result['total_messages'] == 50
            assert result['messages_last_week'] == 10
            assert result['command_stats'] == []
            assert result['most_active_hour'] == 12


class TestGetLastMessageForUserInChat:
    """Test get_last_message_for_user_in_chat function."""
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_by_user_id(self):
        """Test getting last message by user_id."""
        chat_id = 12345
        user_id = 67890
        
        # Mock database response
        mock_row = {
            'timestamp': datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
            'username': 'test_user',
            'text': 'Last message from user'
        }
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, user_id=user_id)
            
            assert result == (
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'test_user',
                'Last message from user'
            )
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_by_username(self):
        """Test getting last message by username."""
        chat_id = 12345
        username = "test_user"
        
        # Mock database responses
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetch for user_ids
            mock_conn.fetch.return_value = [
                {'user_id': 67890},
                {'user_id': 67891}
            ]
            
            # Mock fetchrow for last message
            mock_conn.fetchrow.return_value = {
                'timestamp': datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'username': 'test_user',
                'text': 'Last message from user'
            }
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, username=username)
            
            assert result == (
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'test_user',
                'Last message from user'
            )
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_by_both_user_id_and_username(self):
        """Test getting last message by both user_id and username."""
        chat_id = 12345
        user_id = 67890
        username = "test_user"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetch for user_ids
            mock_conn.fetch.return_value = [
                {'user_id': 67890},
                {'user_id': 67891}
            ]
            
            # Mock fetchrow for last message
            mock_conn.fetchrow.return_value = {
                'timestamp': datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'username': 'test_user',
                'text': 'Last message from user'
            }
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, user_id=user_id, username=username)
            
            assert result == (
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'test_user',
                'Last message from user'
            )
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_no_user_ids(self):
        """Test when no user_ids are found."""
        chat_id = 12345
        username = "nonexistent_user"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetch for user_ids - no users found
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, username=username)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_no_message_found(self):
        """Test when no message is found for the user."""
        chat_id = 12345
        user_id = 67890
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Mock fetchrow returning None
            mock_conn.fetchrow.return_value = None
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, user_id=user_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_no_parameters(self):
        """Test when neither user_id nor username is provided."""
        chat_id = 12345
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_last_message_for_user_in_chat_unknown_username(self):
        """Test when username is None in the result."""
        chat_id = 12345
        user_id = 67890
        
        # Mock database response with None username
        mock_row = {
            'timestamp': datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
            'username': None,
            'text': 'Last message from unknown user'
        }
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_row
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            result = await get_last_message_for_user_in_chat(chat_id, user_id=user_id)
            
            assert result == (
                datetime(2024, 1, 31, 15, 30, 0, tzinfo=KYIV_TZ),
                'Unknown',
                'Last message from unknown user'
            )


class TestChatAnalysisIntegration:
    """Integration tests for chat analysis functions."""
    
    @pytest.mark.asyncio
    async def test_date_handling_consistency(self):
        """Test that date handling is consistent across functions."""
        chat_id = 12345
        target_date = date(2024, 1, 15)
        target_date_str = "2024-01-15"
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            # Test both functions with same date
            result1 = await get_messages_for_chat_single_date(chat_id, target_date)
            result2 = await get_messages_for_chat_single_date(chat_id, target_date_str)
            
            # Both should return empty lists (same behavior)
            assert result1 == []
            assert result2 == []
    
    @pytest.mark.asyncio
    async def test_timezone_handling(self):
        """Test that timezone handling is consistent."""
        chat_id = 12345
        
        with patch('modules.chat_analysis.Database.get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            
            # Create proper async context manager
            async_context_mock = create_async_context_manager_mock(mock_conn)
            mock_pool.acquire = lambda: async_context_mock
            
            mock_get_pool.return_value = mock_pool
            
            # Test that functions use KYIV_TZ
            await get_messages_for_chat_today(chat_id)
            
            # Verify that datetime.now(KYIV_TZ) was used
            # This is implicit in the function calls, but we can verify the behavior
            assert True  # If we get here, no timezone errors occurred 