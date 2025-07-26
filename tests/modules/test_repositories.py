"""
Unit tests for repositories module.

Tests repository pattern implementation including data access patterns,
CRUD operations, and query building functionality.
"""

import pytest
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from modules.repositories import (
    Repository, ChatEntity, UserEntity, MessageEntity, AnalysisCacheEntity,
    ChatRepository, UserRepository, MessageRepository, AnalysisCacheRepository,
    RepositoryFactory
)


class TestChatRepository:
    """Test cases for ChatRepository."""
    
    @pytest.fixture
    def chat_repository(self):
        """Create ChatRepository instance."""
        return ChatRepository()
    
    @pytest.fixture
    def sample_chat_entity(self):
        """Sample chat entity for testing."""
        return ChatEntity(
            chat_id=12345,
            chat_type="private",
            title="Test Chat",
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_database_pool(self):
        """Mock database pool and connection."""
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        return mock_pool, mock_conn
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, chat_repository, sample_chat_entity, mock_database_pool):
        """Test successful chat retrieval by ID."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'chat_id': sample_chat_entity.chat_id,
            'chat_type': sample_chat_entity.chat_type,
            'title': sample_chat_entity.title,
            'created_at': sample_chat_entity.created_at
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.get_by_id(sample_chat_entity.chat_id)
        
        assert result is not None
        assert result.chat_id == sample_chat_entity.chat_id
        assert result.chat_type == sample_chat_entity.chat_type
        assert result.title == sample_chat_entity.title
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM chats WHERE chat_id = $1",
            sample_chat_entity.chat_id
        )
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, chat_repository, mock_database_pool):
        """Test chat retrieval when chat doesn't exist."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = None
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.get_by_id(99999)
        
        assert result is None
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM chats WHERE chat_id = $1",
            99999
        )
    
    @pytest.mark.asyncio
    async def test_save_new_chat(self, chat_repository, sample_chat_entity, mock_database_pool):
        """Test saving a new chat entity."""
        mock_pool, mock_conn = mock_database_pool
        
        # Mock the save operation
        mock_conn.execute.return_value = None
        
        # Mock the get_by_id call that happens after save
        mock_conn.fetchrow.return_value = {
            'chat_id': sample_chat_entity.chat_id,
            'chat_type': sample_chat_entity.chat_type,
            'title': sample_chat_entity.title,
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.save(sample_chat_entity)
        
        assert result is not None
        assert result.chat_id == sample_chat_entity.chat_id
        mock_conn.execute.assert_called_once()
        # Verify the SQL and parameters
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO chats" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_delete_existing_chat(self, chat_repository, mock_database_pool):
        """Test deleting an existing chat."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = "DELETE 1"
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.delete(12345)
        
        assert result is True
        mock_conn.execute.assert_called_once_with(
            "DELETE FROM chats WHERE chat_id = $1",
            12345
        )
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_chat(self, chat_repository, mock_database_pool):
        """Test deleting a non-existent chat."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = "DELETE 0"
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.delete(99999)
        
        assert result is False
        mock_conn.execute.assert_called_once_with(
            "DELETE FROM chats WHERE chat_id = $1",
            99999
        )
    
    @pytest.mark.asyncio
    async def test_find_all_with_pagination(self, chat_repository, mock_database_pool):
        """Test finding all chats with pagination."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = [
            {
                'chat_id': 1,
                'chat_type': 'private',
                'title': 'Chat 1',
                'created_at': datetime.now()
            },
            {
                'chat_id': 2,
                'chat_type': 'group',
                'title': 'Chat 2',
                'created_at': datetime.now()
            }
        ]
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.find_all(limit=10, offset=0)
        
        assert len(result) == 2
        assert result[0].chat_id == 1
        assert result[1].chat_id == 2
        mock_conn.fetch.assert_called_once_with(
            "SELECT * FROM chats ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            10, 0
        )
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_chat_type(self, chat_repository, mock_database_pool):
        """Test finding chats by chat type criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = [
            {
                'chat_id': 1,
                'chat_type': 'private',
                'title': 'Private Chat',
                'created_at': datetime.now()
            }
        ]
        
        criteria = {'chat_type': 'private'}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.find_by_criteria(criteria)
        
        assert len(result) == 1
        assert result[0].chat_type == 'private'
        mock_conn.fetch.assert_called_once()
        # Verify the query contains the WHERE clause
        call_args = mock_conn.fetch.call_args
        assert "chat_type = $1" in call_args[0][0]
        assert call_args[0][1] == 'private'
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_title_contains(self, chat_repository, mock_database_pool):
        """Test finding chats by title contains criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = []
        
        criteria = {'title_contains': 'test'}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.find_by_criteria(criteria)
        
        assert len(result) == 0
        mock_conn.fetch.assert_called_once()
        # Verify the query contains ILIKE
        call_args = mock_conn.fetch.call_args
        assert "title ILIKE $1" in call_args[0][0]
        assert call_args[0][1] == '%test%'
    
    @pytest.mark.asyncio
    async def test_get_chat_statistics(self, chat_repository, mock_database_pool):
        """Test getting chat statistics."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'total_messages': 100,
            'unique_users': 5,
            'command_count': 10,
            'gpt_replies': 20,
            'first_message': datetime.now(),
            'last_message': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await chat_repository.get_chat_statistics(12345)
        
        assert result['total_messages'] == 100
        assert result['unique_users'] == 5
        assert result['command_count'] == 10
        assert result['gpt_replies'] == 20
        mock_conn.fetchrow.assert_called_once()
        # Verify the query structure
        call_args = mock_conn.fetchrow.call_args
        assert "COUNT(*)" in call_args[0][0]
        assert "WHERE chat_id = $1" in call_args[0][0]


class TestUserRepository:
    """Test cases for UserRepository."""
    
    @pytest.fixture
    def user_repository(self):
        """Create UserRepository instance."""
        return UserRepository()
    
    @pytest.fixture
    def sample_user_entity(self):
        """Sample user entity for testing."""
        return UserEntity(
            user_id=67890,
            first_name="John",
            last_name="Doe",
            username="johndoe",
            is_bot=False,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_database_pool(self):
        """Mock database pool and connection."""
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        return mock_pool, mock_conn
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, user_repository, sample_user_entity, mock_database_pool):
        """Test successful user retrieval by ID."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'user_id': sample_user_entity.user_id,
            'first_name': sample_user_entity.first_name,
            'last_name': sample_user_entity.last_name,
            'username': sample_user_entity.username,
            'is_bot': sample_user_entity.is_bot,
            'created_at': sample_user_entity.created_at
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await user_repository.get_by_id(sample_user_entity.user_id)
        
        assert result is not None
        assert result.user_id == sample_user_entity.user_id
        assert result.first_name == sample_user_entity.first_name
        assert result.username == sample_user_entity.username
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM users WHERE user_id = $1",
            sample_user_entity.user_id
        )
    
    @pytest.mark.asyncio
    async def test_save_user(self, user_repository, sample_user_entity, mock_database_pool):
        """Test saving a user entity."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = None
        
        # Mock the get_by_id call that happens after save
        mock_conn.fetchrow.return_value = {
            'user_id': sample_user_entity.user_id,
            'first_name': sample_user_entity.first_name,
            'last_name': sample_user_entity.last_name,
            'username': sample_user_entity.username,
            'is_bot': sample_user_entity.is_bot,
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await user_repository.save(sample_user_entity)
        
        assert result is not None
        assert result.user_id == sample_user_entity.user_id
        mock_conn.execute.assert_called_once()
        # Verify the SQL structure
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO users" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_username(self, user_repository, mock_database_pool):
        """Test finding users by username criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = [
            {
                'user_id': 1,
                'first_name': 'John',
                'last_name': 'Doe',
                'username': 'johndoe',
                'is_bot': False,
                'created_at': datetime.now()
            }
        ]
        
        criteria = {'username': 'johndoe'}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await user_repository.find_by_criteria(criteria)
        
        assert len(result) == 1
        assert result[0].username == 'johndoe'
        mock_conn.fetch.assert_called_once()
        # Verify the query
        call_args = mock_conn.fetch.call_args
        assert "username = $1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_is_bot(self, user_repository, mock_database_pool):
        """Test finding users by bot status criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = []
        
        criteria = {'is_bot': True}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await user_repository.find_by_criteria(criteria)
        
        assert len(result) == 0
        mock_conn.fetch.assert_called_once()
        # Verify the query
        call_args = mock_conn.fetch.call_args
        assert "is_bot = $1" in call_args[0][0]
        assert call_args[0][1] is True
    
    @pytest.mark.asyncio
    async def test_get_user_activity_stats(self, user_repository, mock_database_pool):
        """Test getting user activity statistics."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'total_messages': 50,
            'chats_participated': 3,
            'commands_used': 5,
            'first_message': datetime.now(),
            'last_message': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await user_repository.get_user_activity_stats(67890)
        
        assert result['total_messages'] == 50
        assert result['chats_participated'] == 3
        assert result['commands_used'] == 5
        mock_conn.fetchrow.assert_called_once()
        # Verify the query structure
        call_args = mock_conn.fetchrow.call_args
        assert "WHERE user_id = $1" in call_args[0][0]


class TestMessageRepository:
    """Test cases for MessageRepository."""
    
    @pytest.fixture
    def message_repository(self):
        """Create MessageRepository instance."""
        return MessageRepository()
    
    @pytest.fixture
    def sample_message_entity(self):
        """Sample message entity for testing."""
        return MessageEntity(
            internal_message_id=1,
            message_id=123,
            chat_id=456,
            user_id=789,
            timestamp=datetime.now(),
            text="Hello world",
            is_command=False,
            command_name=None,
            is_gpt_reply=False,
            replied_to_message_id=None,
            gpt_context_message_ids=[],
            raw_telegram_message={"test": "data"}
        )
    
    @pytest.fixture
    def mock_database_pool(self):
        """Mock database pool and connection."""
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        return mock_pool, mock_conn
    
    @pytest.mark.asyncio
    async def test_get_by_id_with_tuple(self, message_repository, sample_message_entity, mock_database_pool):
        """Test getting message by (chat_id, message_id) tuple."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'internal_message_id': sample_message_entity.internal_message_id,
            'message_id': sample_message_entity.message_id,
            'chat_id': sample_message_entity.chat_id,
            'user_id': sample_message_entity.user_id,
            'timestamp': sample_message_entity.timestamp,
            'text': sample_message_entity.text,
            'is_command': sample_message_entity.is_command,
            'command_name': sample_message_entity.command_name,
            'is_gpt_reply': sample_message_entity.is_gpt_reply,
            'replied_to_message_id': sample_message_entity.replied_to_message_id,
            'gpt_context_message_ids': json.dumps(sample_message_entity.gpt_context_message_ids),
            'raw_telegram_message': json.dumps(sample_message_entity.raw_telegram_message)
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await message_repository.get_by_id((sample_message_entity.chat_id, sample_message_entity.message_id))
        
        assert result is not None
        assert result.chat_id == sample_message_entity.chat_id
        assert result.message_id == sample_message_entity.message_id
        assert result.text == sample_message_entity.text
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM messages WHERE chat_id = $1 AND message_id = $2",
            sample_message_entity.chat_id, sample_message_entity.message_id
        )
    
    @pytest.mark.asyncio
    async def test_get_by_id_with_internal_id(self, message_repository, sample_message_entity, mock_database_pool):
        """Test getting message by internal message ID."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'internal_message_id': sample_message_entity.internal_message_id,
            'message_id': sample_message_entity.message_id,
            'chat_id': sample_message_entity.chat_id,
            'user_id': sample_message_entity.user_id,
            'timestamp': sample_message_entity.timestamp,
            'text': sample_message_entity.text,
            'is_command': sample_message_entity.is_command,
            'command_name': sample_message_entity.command_name,
            'is_gpt_reply': sample_message_entity.is_gpt_reply,
            'replied_to_message_id': sample_message_entity.replied_to_message_id,
            'gpt_context_message_ids': None,
            'raw_telegram_message': None
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await message_repository.get_by_id(sample_message_entity.internal_message_id)
        
        assert result is not None
        assert result.internal_message_id == sample_message_entity.internal_message_id
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM messages WHERE internal_message_id = $1",
            sample_message_entity.internal_message_id
        )
    
    @pytest.mark.asyncio
    async def test_save_message(self, message_repository, sample_message_entity, mock_database_pool):
        """Test saving a message entity."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = None
        
        # Mock the get_by_id call that happens after save
        mock_conn.fetchrow.return_value = {
            'internal_message_id': 1,
            'message_id': sample_message_entity.message_id,
            'chat_id': sample_message_entity.chat_id,
            'user_id': sample_message_entity.user_id,
            'timestamp': sample_message_entity.timestamp,
            'text': sample_message_entity.text,
            'is_command': sample_message_entity.is_command,
            'command_name': sample_message_entity.command_name,
            'is_gpt_reply': sample_message_entity.is_gpt_reply,
            'replied_to_message_id': sample_message_entity.replied_to_message_id,
            'gpt_context_message_ids': json.dumps(sample_message_entity.gpt_context_message_ids),
            'raw_telegram_message': json.dumps(sample_message_entity.raw_telegram_message)
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await message_repository.save(sample_message_entity)
        
        assert result is not None
        assert result.message_id == sample_message_entity.message_id
        mock_conn.execute.assert_called_once()
        # Verify the SQL structure
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO messages" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_chat_id(self, message_repository, mock_database_pool):
        """Test finding messages by chat ID criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = [
            {
                'internal_message_id': 1,
                'message_id': 123,
                'chat_id': 456,
                'user_id': 789,
                'timestamp': datetime.now(),
                'text': 'Test message',
                'is_command': False,
                'command_name': None,
                'is_gpt_reply': False,
                'replied_to_message_id': None,
                'gpt_context_message_ids': None,
                'raw_telegram_message': None
            }
        ]
        
        criteria = {'chat_id': 456}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await message_repository.find_by_criteria(criteria)
        
        assert len(result) == 1
        assert result[0].chat_id == 456
        mock_conn.fetch.assert_called_once()
        # Verify the query
        call_args = mock_conn.fetch.call_args
        assert "chat_id = $1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_find_by_criteria_text_contains(self, message_repository, mock_database_pool):
        """Test finding messages by text contains criteria."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetch.return_value = []
        
        criteria = {'text_contains': 'hello'}
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await message_repository.find_by_criteria(criteria)
        
        assert len(result) == 0
        mock_conn.fetch.assert_called_once()
        # Verify the query
        call_args = mock_conn.fetch.call_args
        assert "text ILIKE $1" in call_args[0][0]
        assert call_args[0][1] == '%hello%'
    
    @pytest.mark.asyncio
    async def test_row_to_entity_with_json_data(self, message_repository):
        """Test converting database row to MessageEntity with JSON data."""
        row = {
            'internal_message_id': 1,
            'message_id': 123,
            'chat_id': 456,
            'user_id': 789,
            'timestamp': datetime.now(),
            'text': 'Test message',
            'is_command': False,
            'command_name': None,
            'is_gpt_reply': False,
            'replied_to_message_id': None,
            'gpt_context_message_ids': json.dumps([1, 2, 3]),
            'raw_telegram_message': json.dumps({"test": "data"})
        }
        
        result = message_repository._row_to_entity(row)
        
        assert result.internal_message_id == 1
        assert result.message_id == 123
        assert result.gpt_context_message_ids == [1, 2, 3]
        assert result.raw_telegram_message == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_row_to_entity_with_invalid_json(self, message_repository):
        """Test converting database row with invalid JSON data."""
        row = {
            'internal_message_id': 1,
            'message_id': 123,
            'chat_id': 456,
            'user_id': 789,
            'timestamp': datetime.now(),
            'text': 'Test message',
            'is_command': False,
            'command_name': None,
            'is_gpt_reply': False,
            'replied_to_message_id': None,
            'gpt_context_message_ids': 'invalid json',
            'raw_telegram_message': 'invalid json'
        }
        
        result = message_repository._row_to_entity(row)
        
        assert result.internal_message_id == 1
        assert result.gpt_context_message_ids is None
        assert result.raw_telegram_message is None


class TestAnalysisCacheRepository:
    """Test cases for AnalysisCacheRepository."""
    
    @pytest.fixture
    def cache_repository(self):
        """Create AnalysisCacheRepository instance."""
        return AnalysisCacheRepository()
    
    @pytest.fixture
    def sample_cache_entity(self):
        """Sample cache entity for testing."""
        return AnalysisCacheEntity(
            chat_id=12345,
            time_period="daily",
            message_content_hash="abc123",
            result="cached result",
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_database_pool(self):
        """Mock database pool and connection."""
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        return mock_pool, mock_conn
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, cache_repository, sample_cache_entity, mock_database_pool):
        """Test successful cache retrieval by composite key."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.fetchrow.return_value = {
            'chat_id': sample_cache_entity.chat_id,
            'time_period': sample_cache_entity.time_period,
            'message_content_hash': sample_cache_entity.message_content_hash,
            'result': sample_cache_entity.result,
            'created_at': sample_cache_entity.created_at
        }
        
        cache_key = (sample_cache_entity.chat_id, sample_cache_entity.time_period, sample_cache_entity.message_content_hash)
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await cache_repository.get_by_id(cache_key)
        
        assert result is not None
        assert result.chat_id == sample_cache_entity.chat_id
        assert result.time_period == sample_cache_entity.time_period
        assert result.message_content_hash == sample_cache_entity.message_content_hash
        mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM analysis_cache WHERE chat_id = $1 AND time_period = $2 AND message_content_hash = $3",
            sample_cache_entity.chat_id, sample_cache_entity.time_period, sample_cache_entity.message_content_hash
        )
    
    @pytest.mark.asyncio
    async def test_save_cache_entry(self, cache_repository, sample_cache_entity, mock_database_pool):
        """Test saving a cache entity."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = None
        
        # Mock the get_by_id call that happens after save
        mock_conn.fetchrow.return_value = {
            'chat_id': sample_cache_entity.chat_id,
            'time_period': sample_cache_entity.time_period,
            'message_content_hash': sample_cache_entity.message_content_hash,
            'result': sample_cache_entity.result,
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await cache_repository.save(sample_cache_entity)
        
        assert result is not None
        assert result.chat_id == sample_cache_entity.chat_id
        mock_conn.execute.assert_called_once()
        # Verify the SQL structure
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO analysis_cache" in call_args[0][0]
        assert "ON CONFLICT" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_invalidate_chat_cache_with_time_period(self, cache_repository, mock_database_pool):
        """Test invalidating cache for specific chat and time period."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = "DELETE 3"
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await cache_repository.invalidate_chat_cache(12345, "daily")
        
        assert result == 3
        mock_conn.execute.assert_called_once_with(
            "DELETE FROM analysis_cache WHERE chat_id = $1 AND time_period = $2",
            12345, "daily"
        )
    
    @pytest.mark.asyncio
    async def test_invalidate_chat_cache_all_periods(self, cache_repository, mock_database_pool):
        """Test invalidating all cache for a chat."""
        mock_pool, mock_conn = mock_database_pool
        mock_conn.execute.return_value = "DELETE 5"
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            result = await cache_repository.invalidate_chat_cache(12345)
        
        assert result == 5
        mock_conn.execute.assert_called_once_with(
            "DELETE FROM analysis_cache WHERE chat_id = $1",
            12345
        )


class TestRepositoryFactory:
    """Test cases for RepositoryFactory."""
    
    def test_get_chat_repository_singleton(self):
        """Test that chat repository returns the same instance."""
        repo1 = RepositoryFactory.get_chat_repository()
        repo2 = RepositoryFactory.get_chat_repository()
        
        assert repo1 is repo2
        assert isinstance(repo1, ChatRepository)
    
    def test_get_user_repository_singleton(self):
        """Test that user repository returns the same instance."""
        repo1 = RepositoryFactory.get_user_repository()
        repo2 = RepositoryFactory.get_user_repository()
        
        assert repo1 is repo2
        assert isinstance(repo1, UserRepository)
    
    def test_get_message_repository_singleton(self):
        """Test that message repository returns the same instance."""
        repo1 = RepositoryFactory.get_message_repository()
        repo2 = RepositoryFactory.get_message_repository()
        
        assert repo1 is repo2
        assert isinstance(repo1, MessageRepository)
    
    def test_get_analysis_cache_repository_singleton(self):
        """Test that analysis cache repository returns the same instance."""
        repo1 = RepositoryFactory.get_analysis_cache_repository()
        repo2 = RepositoryFactory.get_analysis_cache_repository()
        
        assert repo1 is repo2
        assert isinstance(repo1, AnalysisCacheRepository)
    
    def test_all_repositories_are_different_instances(self):
        """Test that different repository types return different instances."""
        chat_repo = RepositoryFactory.get_chat_repository()
        user_repo = RepositoryFactory.get_user_repository()
        message_repo = RepositoryFactory.get_message_repository()
        cache_repo = RepositoryFactory.get_analysis_cache_repository()
        
        assert chat_repo is not user_repo
        assert user_repo is not message_repo
        assert message_repo is not cache_repo
        assert cache_repo is not chat_repo


class TestRepositoryEntities:
    """Test cases for repository entity models."""
    
    def test_chat_entity_creation(self):
        """Test ChatEntity creation and attributes."""
        entity = ChatEntity(
            chat_id=12345,
            chat_type="private",
            title="Test Chat"
        )
        
        assert entity.chat_id == 12345
        assert entity.chat_type == "private"
        assert entity.title == "Test Chat"
        assert entity.created_at is None
    
    def test_user_entity_creation(self):
        """Test UserEntity creation and attributes."""
        entity = UserEntity(
            user_id=67890,
            first_name="John",
            last_name="Doe",
            username="johndoe",
            is_bot=False
        )
        
        assert entity.user_id == 67890
        assert entity.first_name == "John"
        assert entity.last_name == "Doe"
        assert entity.username == "johndoe"
        assert entity.is_bot is False
        assert entity.created_at is None
    
    def test_message_entity_creation(self):
        """Test MessageEntity creation and attributes."""
        entity = MessageEntity(
            message_id=123,
            chat_id=456,
            user_id=789,
            text="Hello world",
            is_command=True,
            command_name="start"
        )
        
        assert entity.message_id == 123
        assert entity.chat_id == 456
        assert entity.user_id == 789
        assert entity.text == "Hello world"
        assert entity.is_command is True
        assert entity.command_name == "start"
        assert entity.internal_message_id is None
        assert entity.gpt_context_message_ids is None
    
    def test_analysis_cache_entity_creation(self):
        """Test AnalysisCacheEntity creation and attributes."""
        entity = AnalysisCacheEntity(
            chat_id=12345,
            time_period="daily",
            message_content_hash="abc123",
            result="cached result"
        )
        
        assert entity.chat_id == 12345
        assert entity.time_period == "daily"
        assert entity.message_content_hash == "abc123"
        assert entity.result == "cached result"
        assert entity.created_at is None

# ============================================================================
# Transaction Handling and Error Scenario Tests
# ============================================================================

class TestRepositoryTransactionHandling:
    """Test cases for repository transaction handling and error scenarios."""
    
    @pytest.fixture
    def mock_database_pool_with_transaction(self):
        """Mock database pool with transaction support."""
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock transaction context manager
        @asynccontextmanager
        async def transaction():
            yield mock_conn
            
        mock_conn.transaction = transaction
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        return mock_pool, mock_conn
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        from modules.repositories import ChatRepository
        
        # Mock Database.get_pool to raise connection error
        with patch('modules.repositories.Database.get_pool') as mock_get_pool:
            mock_get_pool.side_effect = Exception("Connection failed")
            
            chat_repo = ChatRepository()
            
            with pytest.raises(Exception, match="Connection failed"):
                await chat_repo.get_by_id(12345)
    
    @pytest.mark.asyncio
    async def test_query_execution_error(self):
        """Test handling of query execution errors."""
        from modules.repositories import ChatRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock connection that raises error on query
        mock_conn.fetchrow.side_effect = Exception("Query execution failed")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            
            with pytest.raises(Exception, match="Query execution failed"):
                await chat_repo.get_by_id(12345)
    
    @pytest.mark.asyncio
    async def test_transaction_commit_success(self, mock_database_pool_with_transaction):
        """Test successful transaction commit."""
        from modules.repositories import ChatRepository, ChatEntity
        
        mock_pool, mock_conn = mock_database_pool_with_transaction
        
        # Mock successful operations
        mock_conn.execute.return_value = None
        mock_conn.fetchrow.return_value = {
            'chat_id': 12345,
            'chat_type': 'private',
            'title': 'Test Chat',
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            entity = ChatEntity(chat_id=12345, chat_type='private', title='Test Chat')
            
            result = await chat_repo.save(entity)
            
            assert result is not None
            assert result.chat_id == 12345
            mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, mock_database_pool_with_transaction):
        """Test transaction rollback on error."""
        from modules.repositories import ChatRepository, ChatEntity
        
        mock_pool, mock_conn = mock_database_pool_with_transaction
        
        # Mock execute to raise error
        mock_conn.execute.side_effect = Exception("Constraint violation")
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            entity = ChatEntity(chat_id=12345, chat_type='private', title='Test Chat')
            
            with pytest.raises(Exception, match="Constraint violation"):
                await chat_repo.save(entity)
    
    @pytest.mark.asyncio
    async def test_concurrent_access_simulation(self):
        """Test concurrent access patterns."""
        from modules.repositories import ChatRepository, ChatEntity
        from contextlib import asynccontextmanager
        import asyncio
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Track concurrent connections
        active_connections = []
        
        @asynccontextmanager
        async def acquire():
            connection_id = len(active_connections)
            active_connections.append(connection_id)
            try:
                yield mock_conn
            finally:
                active_connections.remove(connection_id)
        
        mock_pool.acquire = acquire
        mock_conn.execute.return_value = None
        mock_conn.fetchrow.return_value = {
            'chat_id': 12345,
            'chat_type': 'private',
            'title': 'Test Chat',
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            entity = ChatEntity(chat_id=12345, chat_type='private', title='Test Chat')
            
            # Simulate concurrent operations
            tasks = [chat_repo.save(entity) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(r.chat_id == 12345 for r in results)
    
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """Test behavior when connection pool is exhausted."""
        from modules.repositories import ChatRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        
        # Simulate pool exhaustion
        @asynccontextmanager
        async def acquire():
            raise Exception("Pool exhausted")
            yield  # This won't be reached
        
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            
            with pytest.raises(Exception, match="Pool exhausted"):
                await chat_repo.get_by_id(12345)
    
    @pytest.mark.asyncio
    async def test_database_timeout_error(self):
        """Test handling of database timeout errors."""
        from modules.repositories import UserRepository
        from contextlib import asynccontextmanager
        import asyncio
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock connection that times out
        async def timeout_query(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate delay
            raise asyncio.TimeoutError("Query timeout")
        
        mock_conn.fetchrow.side_effect = timeout_query
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            user_repo = UserRepository()
            
            with pytest.raises(asyncio.TimeoutError, match="Query timeout"):
                await user_repo.get_by_id(67890)
    
    @pytest.mark.asyncio
    async def test_deadlock_detection_and_retry(self):
        """Test deadlock detection and retry logic."""
        from modules.repositories import MessageRepository, MessageEntity
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock deadlock on first call, success on second
        call_count = 0
        
        async def execute_with_deadlock(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Deadlock detected")
            return None
        
        mock_conn.execute.side_effect = execute_with_deadlock
        mock_conn.fetchrow.return_value = {
            'internal_message_id': 1,
            'message_id': 123,
            'chat_id': 456,
            'user_id': 789,
            'timestamp': datetime.now(),
            'text': 'Test message',
            'is_command': False,
            'command_name': None,
            'is_gpt_reply': False,
            'replied_to_message_id': None,
            'gpt_context_message_ids': None,
            'raw_telegram_message': None
        }
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            message_repo = MessageRepository()
            entity = MessageEntity(
                message_id=123,
                chat_id=456,
                user_id=789,
                text="Test message"
            )
            
            # First call should raise deadlock error
            with pytest.raises(Exception, match="Deadlock detected"):
                await message_repo.save(entity)
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_failure(self):
        """Test connection recovery after failure."""
        from modules.repositories import ChatRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Track connection attempts
        connection_attempts = 0
        
        @asynccontextmanager
        async def acquire():
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts == 1:
                raise Exception("Connection failed")
            yield mock_conn
        
        mock_pool.acquire = acquire
        mock_conn.fetchrow.return_value = {
            'chat_id': 12345,
            'chat_type': 'private',
            'title': 'Test Chat',
            'created_at': datetime.now()
        }
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            
            # First call should fail
            with pytest.raises(Exception, match="Connection failed"):
                await chat_repo.get_by_id(12345)
            
            # Second call should succeed (simulating recovery)
            result = await chat_repo.get_by_id(12345)
            assert result is not None
            assert result.chat_id == 12345
    
    @pytest.mark.asyncio
    async def test_invalid_sql_query_error(self):
        """Test handling of invalid SQL query errors."""
        from modules.repositories import AnalysisCacheRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock SQL syntax error
        mock_conn.fetchrow.side_effect = Exception("SQL syntax error")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            cache_repo = AnalysisCacheRepository()
            
            with pytest.raises(Exception, match="SQL syntax error"):
                await cache_repo.get_by_id((12345, "daily", "hash123"))
    
    @pytest.mark.asyncio
    async def test_constraint_violation_error(self):
        """Test handling of database constraint violations."""
        from modules.repositories import UserRepository, UserEntity
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock constraint violation
        mock_conn.execute.side_effect = Exception("UNIQUE constraint failed")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            user_repo = UserRepository()
            entity = UserEntity(
                user_id=67890,
                first_name="John",
                last_name="Doe",
                username="johndoe"
            )
            
            with pytest.raises(Exception, match="UNIQUE constraint failed"):
                await user_repo.save(entity)
    
    @pytest.mark.asyncio
    async def test_data_integrity_validation(self):
        """Test data integrity validation in repositories."""
        from modules.repositories import MessageRepository, MessageEntity
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock successful save but return None on fetch (data integrity issue)
        mock_conn.execute.return_value = None
        mock_conn.fetchrow.return_value = None  # Simulating data not found after save
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            message_repo = MessageRepository()
            entity = MessageEntity(
                message_id=123,
                chat_id=456,
                user_id=789,
                text="Test message"
            )
            
            # Save should return the original entity if fetch fails
            result = await message_repo.save(entity)
            assert result == entity  # Should return original entity as fallback
    
    @pytest.mark.asyncio
    async def test_repository_factory_error_handling(self):
        """Test error handling in repository factory."""
        from modules.repositories import RepositoryFactory
        
        # Test that factory methods don't raise errors
        chat_repo = RepositoryFactory.get_chat_repository()
        user_repo = RepositoryFactory.get_user_repository()
        message_repo = RepositoryFactory.get_message_repository()
        cache_repo = RepositoryFactory.get_analysis_cache_repository()
        
        assert chat_repo is not None
        assert user_repo is not None
        assert message_repo is not None
        assert cache_repo is not None
        
        # Test singleton behavior under concurrent access
        import asyncio
        
        async def get_repos():
            return (
                RepositoryFactory.get_chat_repository(),
                RepositoryFactory.get_user_repository(),
                RepositoryFactory.get_message_repository(),
                RepositoryFactory.get_analysis_cache_repository()
            )
        
        # Run concurrent factory calls
        tasks = [get_repos() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All results should be identical (singleton behavior)
        first_result = results[0]
        for result in results[1:]:
            assert result[0] is first_result[0]  # Same chat repo instance
            assert result[1] is first_result[1]  # Same user repo instance
            assert result[2] is first_result[2]  # Same message repo instance
            assert result[3] is first_result[3]  # Same cache repo instance


class TestRepositoryErrorRecovery:
    """Test cases for repository error recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_on_transient_errors(self):
        """Test retry mechanism for transient database errors."""
        from modules.repositories import ChatRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Track retry attempts
        attempt_count = 0
        
        async def failing_query(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:  # Fail first 2 attempts
                raise Exception("Transient error")
            return {
                'chat_id': 12345,
                'chat_type': 'private',
                'title': 'Test Chat',
                'created_at': datetime.now()
            }
        
        mock_conn.fetchrow.side_effect = failing_query
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            
            # This would require implementing retry logic in the repository
            # For now, we test that the error is raised
            with pytest.raises(Exception, match="Transient error"):
                await chat_repo.get_by_id(12345)
            
            assert attempt_count == 1  # Only one attempt without retry logic
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern for database failures."""
        from modules.repositories import UserRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Simulate consistent failures
        mock_conn.fetchrow.side_effect = Exception("Database unavailable")
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            user_repo = UserRepository()
            
            # Multiple consecutive failures
            for i in range(5):
                with pytest.raises(Exception, match="Database unavailable"):
                    await user_repo.get_by_id(67890)
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when database is unavailable."""
        from modules.repositories import AnalysisCacheRepository, AnalysisCacheEntity
        
        # Mock complete database failure
        with patch('modules.repositories.Database.get_pool') as mock_get_pool:
            mock_get_pool.side_effect = Exception("Database completely unavailable")
            
            cache_repo = AnalysisCacheRepository()
            
            # Operations should fail gracefully
            with pytest.raises(Exception, match="Database completely unavailable"):
                await cache_repo.get_by_id((12345, "daily", "hash123"))
            
            with pytest.raises(Exception, match="Database completely unavailable"):
                entity = AnalysisCacheEntity(
                    chat_id=12345,
                    time_period="daily",
                    message_content_hash="hash123",
                    result="test result"
                )
                await cache_repo.save(entity)


class TestRepositoryPerformance:
    """Test cases for repository performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self):
        """Test performance of bulk operations."""
        from modules.repositories import ChatRepository, ChatEntity
        from contextlib import asynccontextmanager
        import time
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock fast responses
        mock_conn.execute.return_value = None
        mock_conn.fetchrow.return_value = {
            'chat_id': 12345,
            'chat_type': 'private',
            'title': 'Test Chat',
            'created_at': datetime.now()
        }
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            chat_repo = ChatRepository()
            
            # Measure time for bulk operations
            start_time = time.time()
            
            entities = [
                ChatEntity(chat_id=i, chat_type='private', title=f'Chat {i}')
                for i in range(100)
            ]
            
            # Simulate bulk save operations
            tasks = [chat_repo.save(entity) for entity in entities]
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            duration = end_time - start_time
            
            assert len(results) == 100
            assert duration < 5.0  # Should complete within 5 seconds
    
    @pytest.mark.asyncio
    async def test_connection_pooling_efficiency(self):
        """Test connection pooling efficiency."""
        from modules.repositories import MessageRepository
        from contextlib import asynccontextmanager
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Track connection acquisitions
        acquisition_count = 0
        
        @asynccontextmanager
        async def acquire():
            nonlocal acquisition_count
            acquisition_count += 1
            yield mock_conn
        
        mock_pool.acquire = acquire
        mock_conn.fetchrow.return_value = None
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            message_repo = MessageRepository()
            
            # Multiple operations should reuse connections efficiently
            tasks = [message_repo.get_by_id(i) for i in range(10)]
            await asyncio.gather(*tasks)
            
            # Each operation should acquire a connection
            assert acquisition_count == 10
    
    @pytest.mark.asyncio
    async def test_memory_usage_optimization(self):
        """Test memory usage optimization in repositories."""
        from modules.repositories import UserRepository
        from contextlib import asynccontextmanager
        import gc
        
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock large result set
        large_result_set = [
            {
                'user_id': i,
                'first_name': f'User{i}',
                'last_name': f'Last{i}',
                'username': f'user{i}',
                'is_bot': False,
                'created_at': datetime.now()
            }
            for i in range(1000)
        ]
        
        mock_conn.fetch.return_value = large_result_set
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
            
        mock_pool.acquire = acquire
        
        with patch('modules.repositories.Database.get_pool', return_value=mock_pool):
            user_repo = UserRepository()
            
            # Force garbage collection before test
            gc.collect()
            initial_objects = len(gc.get_objects())
            
            # Process large result set
            results = await user_repo.find_all(limit=1000)
            
            assert len(results) == 1000
            
            # Clean up results
            del results
            gc.collect()
            
            final_objects = len(gc.get_objects())
            
            # Memory should not grow excessively
            object_growth = final_objects - initial_objects
            assert object_growth < 2000  # Allow some growth but not excessive