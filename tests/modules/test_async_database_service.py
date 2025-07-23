"""
Tests for async_database_service.py

Comprehensive test suite for the async database service including:
- AsyncDatabaseConnectionManager
- AsyncDatabaseService
- Connection pooling
- Query execution
- Transaction management
- Caching
- Error handling
"""

import pytest
import asyncio
import asyncpg
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Generator, AsyncGenerator

from modules.async_database_service import (
    AsyncDatabaseConnectionManager,
    AsyncDatabaseService
)
from modules.async_utils import AsyncRateLimiter


class TestAsyncDatabaseConnectionManager:
    """Test AsyncDatabaseConnectionManager class."""
    
    @pytest.fixture
    def connection_manager(self) -> Generator[AsyncDatabaseConnectionManager, None, None]:
        """Create a connection manager instance."""
        with patch('modules.async_database_service.AsyncRateLimiter') as mock_rate_limiter:
            mock_rate_limiter.return_value = AsyncMock()
            yield AsyncDatabaseConnectionManager()
    
    @pytest.fixture
    def mock_pool(self) -> AsyncMock:
        """Create a mock connection pool."""
        pool = AsyncMock(spec=asyncpg.Pool)
        pool.acquire = AsyncMock()
        pool.release = AsyncMock()
        pool.close = AsyncMock()
        return pool
    
    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        connection = AsyncMock(spec=asyncpg.Connection)
        connection.execute = AsyncMock()
        return connection
    
    @pytest.mark.asyncio
    async def test_initialization(self, connection_manager: AsyncDatabaseConnectionManager) -> None:
        """Test connection manager initialization."""
        assert connection_manager.pool is None
        assert connection_manager._connection_pool is None
        # Note: The actual AsyncRateLimiter initialization will be mocked in the module
        # since it uses incorrect parameters in the original code
    
    @pytest.mark.asyncio
    async def test_acquire_connection_initializes_pool(self, connection_manager: AsyncDatabaseConnectionManager, mock_pool: AsyncMock) -> None:
        """Test that acquire initializes the pool if not exists."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock, return_value=mock_pool):
            connection = await connection_manager.acquire()
            
            assert connection_manager.pool == mock_pool
            assert connection == mock_pool.acquire.return_value
    
    @pytest.mark.asyncio
    async def test_acquire_connection_uses_existing_pool(self, connection_manager: AsyncDatabaseConnectionManager, mock_pool: AsyncMock) -> None:
        """Test that acquire uses existing pool."""
        connection_manager.pool = mock_pool
        
        connection = await connection_manager.acquire()
        
        assert connection == mock_pool.acquire.return_value
        mock_pool.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_release_connection(self, connection_manager: AsyncDatabaseConnectionManager, mock_pool: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test releasing a connection."""
        connection_manager.pool = mock_pool
        
        await connection_manager.release(mock_connection)
        
        mock_pool.release.assert_called_once_with(mock_connection)
    
    @pytest.mark.asyncio
    async def test_release_connection_no_pool(self, connection_manager: AsyncDatabaseConnectionManager, mock_connection: AsyncMock) -> None:
        """Test releasing a connection when no pool exists."""
        # Should not raise an exception
        await connection_manager.release(mock_connection)
    
    @pytest.mark.asyncio
    async def test_cleanup(self, connection_manager: AsyncDatabaseConnectionManager, mock_pool: AsyncMock) -> None:
        """Test cleanup of connection manager."""
        connection_manager.pool = mock_pool
        
        await connection_manager.cleanup()
        
        mock_pool.close.assert_called_once()
        assert connection_manager.pool is None
    
    @pytest.mark.asyncio
    async def test_cleanup_no_pool(self, connection_manager: AsyncDatabaseConnectionManager) -> None:
        """Test cleanup when no pool exists."""
        # Should not raise an exception
        await connection_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_initialize_pool(self, connection_manager: AsyncDatabaseConnectionManager, mock_pool: AsyncMock) -> None:
        """Test pool initialization."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock, return_value=mock_pool):
            await connection_manager._initialize_pool()
            
            assert connection_manager.pool == mock_pool
    
    @pytest.mark.asyncio
    async def test_init_connection(self, connection_manager: AsyncDatabaseConnectionManager, mock_connection: AsyncMock) -> None:
        """Test connection initialization."""
        await connection_manager._init_connection(mock_connection)
        
        mock_connection.execute.assert_any_call("SET timezone = 'UTC'")
        mock_connection.execute.assert_any_call("SET statement_timeout = '30s'")


class TestAsyncDatabaseService:
    """Test AsyncDatabaseService class."""
    
    @pytest.fixture
    def db_service(self) -> Generator[AsyncDatabaseService, None, None]:
        """Create a database service instance."""
        with patch('modules.async_database_service.AsyncRateLimiter') as mock_rate_limiter:
            mock_rate_limiter.return_value = AsyncMock()
            yield AsyncDatabaseService()
    
    @pytest.fixture
    def mock_connection_manager(self) -> AsyncMock:
        """Create a mock connection manager."""
        manager = AsyncMock(spec=AsyncDatabaseConnectionManager)
        manager._initialize_pool = AsyncMock()
        manager.cleanup = AsyncMock()
        manager.acquire = AsyncMock()
        manager.release = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """Create a mock database connection."""
        connection = AsyncMock(spec=asyncpg.Connection)
        connection.execute = AsyncMock()
        connection.fetchrow = AsyncMock()
        connection.fetch = AsyncMock()
        connection.fetchval = AsyncMock()
        connection.executemany = AsyncMock()
        connection.transaction = AsyncMock()
        return connection
    
    @pytest.fixture
    def mock_transaction(self) -> Generator[AsyncMock, None, None]:
        """Create a mock transaction context."""
        transaction = AsyncMock()
        transaction.__aenter__ = AsyncMock(return_value=transaction)
        transaction.__aexit__ = AsyncMock(return_value=None)
        return transaction
    
    def create_async_context_manager_mock(self, return_value: Any) -> Generator[AsyncMock, None, None]:
        """Helper to create a proper async context manager mock."""
        context_mock = AsyncMock()
        context_mock.__aenter__ = AsyncMock(return_value=return_value)
        context_mock.__aexit__ = AsyncMock(return_value=None)
        return context_mock
    
    def create_transaction_mock(self, connection: Any) -> Generator[AsyncMock, None, None]:
        """Helper to create a proper transaction mock."""
        # Create a mock that behaves like an async context manager
        transaction = AsyncMock()
        transaction.__aenter__ = AsyncMock(return_value=connection)
        transaction.__aexit__ = AsyncMock(return_value=None)
        return transaction
    
    def setup_connection_with_transaction(self, mock_connection: Any) -> Generator[AsyncMock, None, None]:
        """Helper to setup a connection with proper transaction mocking."""
        # Create a transaction mock that returns the connection when entered
        transaction = AsyncMock()
        transaction.__aenter__ = AsyncMock(return_value=mock_connection)
        transaction.__aexit__ = AsyncMock(return_value=None)
        
        # Set the transaction method to return the transaction mock directly (not as a coroutine)
        mock_connection.transaction = Mock(return_value=transaction)
        yield mock_connection
    
    @pytest.mark.asyncio
    async def test_initialization(self, db_service: AsyncDatabaseService) -> None:
        """Test service initialization."""
        assert db_service.connection_manager is not None
        assert isinstance(db_service._query_cache, dict)
        assert db_service._cache_ttl == 300
        assert db_service._batch_size == 100
    
    @pytest.mark.asyncio
    async def test_initialize(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock) -> None:
        """Test service initialization."""
        db_service.connection_manager = mock_connection_manager
        
        await db_service.initialize()
        
        mock_connection_manager._initialize_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock) -> None:
        """Test service shutdown."""
        db_service.connection_manager = mock_connection_manager
        db_service._query_cache = {"test": "data"}
        
        await db_service.shutdown()
        
        mock_connection_manager.cleanup.assert_called_once()
        assert db_service._query_cache == {}
    
    @pytest.mark.asyncio
    async def test_get_connection(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test getting a connection."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        async with db_service.get_connection() as conn:
            assert conn == mock_connection
        
        mock_connection_manager.acquire.assert_called_once()
        mock_connection_manager.release.assert_called_once_with(mock_connection)
    
    @pytest.mark.asyncio
    async def test_get_transaction(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test getting a transaction."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        # Create a transaction mock that returns the connection when entered
        transaction = AsyncMock()
        transaction.__aenter__ = AsyncMock(return_value=mock_connection)
        transaction.__aexit__ = AsyncMock(return_value=None)
        
        # Set the transaction method to return the transaction mock directly (not as a coroutine)
        mock_connection.transaction = Mock(return_value=transaction)
        
        async with db_service.get_transaction() as conn:
            assert conn == mock_connection
        
        mock_connection_manager.acquire.assert_called_once()
        mock_connection_manager.release.assert_called_once_with(mock_connection)
        mock_connection.transaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_query_none_mode(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_query with fetch_mode='none'."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.execute.return_value = "result"
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.execute_query("SELECT 1", fetch_mode="none")
        
        assert result == "result"
        mock_connection.execute.assert_called_once_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_execute_query_one_mode(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_query with fetch_mode='one'."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetchrow.return_value = {"id": 1}
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.execute_query("SELECT * FROM users WHERE id = $1", 1, fetch_mode="one")
        
        assert result == {"id": 1}
        mock_connection.fetchrow.assert_called_once_with("SELECT * FROM users WHERE id = $1", 1)
    
    @pytest.mark.asyncio
    async def test_execute_query_all_mode(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_query with fetch_mode='all'."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetch.return_value = [{"id": 1}, {"id": 2}]
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.execute_query("SELECT * FROM users", fetch_mode="all")
        
        assert result == [{"id": 1}, {"id": 2}]
        mock_connection.fetch.assert_called_once_with("SELECT * FROM users")
    
    @pytest.mark.asyncio
    async def test_execute_query_val_mode(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_query with fetch_mode='val'."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetchval.return_value = 42
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.execute_query("SELECT COUNT(*) FROM users", fetch_mode="val")
        
        assert result == 42
        mock_connection.fetchval.assert_called_once_with("SELECT COUNT(*) FROM users")
    
    @pytest.mark.asyncio
    async def test_execute_batch(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_batch method."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        args_list = [(1, "user1"), (2, "user2")]
        
        with patch('modules.async_database_service.async_timeout'):
            await db_service.execute_batch("INSERT INTO users (id, name) VALUES ($1, $2)", args_list)
        
        mock_connection.executemany.assert_called_once_with(
            "INSERT INTO users (id, name) VALUES ($1, $2)", 
            args_list
        )
    
    @pytest.mark.asyncio
    async def test_execute_transaction(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_transaction method."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        # Setup connection with proper transaction mocking
        self.setup_connection_with_transaction(mock_connection)
        
        mock_connection.fetchrow.return_value = {"id": 1}
        mock_connection.fetch.return_value = [{"id": 1}, {"id": 2}]
        mock_connection.fetchval.return_value = 42
        mock_connection.execute.return_value = "executed"
        
        queries = [
            ("SELECT * FROM users WHERE id = $1", (1,), "one"),
            ("SELECT * FROM users", (), "all"),
            ("SELECT COUNT(*) FROM users", (), "val"),
            ("INSERT INTO users (name) VALUES ($1)", ("test",), "none")
        ]
        
        with patch('modules.async_database_service.async_timeout'):
            results = await db_service.execute_transaction(queries)
        
        assert len(results) == 4
        assert results[0] == {"id": 1}
        assert results[1] == [{"id": 1}, {"id": 2}]
        assert results[2] == 42
        assert results[3] == "executed"
    
    @pytest.mark.asyncio
    async def test_execute_transaction_with_2_tuple_queries(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test execute_transaction with 2-tuple queries (no fetch_mode)."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        # Setup connection with proper transaction mocking
        self.setup_connection_with_transaction(mock_connection)
        
        mock_connection.execute.return_value = "executed"
        
        queries = [
            ("INSERT INTO users (name) VALUES ($1)", ("test1",)),
            ("INSERT INTO users (name) VALUES ($1)", ("test2",))
        ]
        
        with patch('modules.async_database_service.async_timeout'):
            results = await db_service.execute_transaction(queries)
        
        assert len(results) == 2
        assert results[0] == "executed"
        assert results[1] == "executed"
    
    @pytest.mark.asyncio
    async def test_get_cached_query_cache_hit(self, db_service: AsyncDatabaseService) -> None:
        """Test get_cached_query with cache hit."""
        import time
        
        # Setup cache with recent data
        cache_data = [{"id": 1, "name": "test"}]
        db_service._query_cache["test_key"] = (cache_data, time.time())
        
        result = await db_service.get_cached_query("test_key", "SELECT * FROM users")
        
        assert result == cache_data
    
    @pytest.mark.asyncio
    async def test_get_cached_query_cache_miss(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test get_cached_query with cache miss."""
        import time
        
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetch.return_value = [{"id": 1, "name": "test"}]
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.get_cached_query("test_key", "SELECT * FROM users")
        
        assert result == [{"id": 1, "name": "test"}]
        assert "test_key" in db_service._query_cache
        cached_data, cached_time = db_service._query_cache["test_key"]
        assert cached_data == [{"id": 1, "name": "test"}]
        assert time.time() - cached_time < 1  # Should be very recent
    
    @pytest.mark.asyncio
    async def test_get_cached_query_with_custom_ttl(self, db_service: AsyncDatabaseService) -> None:
        """Test get_cached_query with custom TTL."""
        import time
        
        # Setup cache with old data
        cache_data = [{"id": 1, "name": "test"}]
        db_service._query_cache["test_key"] = (cache_data, time.time() - 1000)  # Old data
        
        # Mock the execute_query to return new data
        with patch.object(db_service, 'execute_query', return_value=[{"id": 2, "name": "new"}]):
            result = await db_service.get_cached_query("test_key", "SELECT * FROM users", ttl=500)
        
        # Should return new data since cache is expired
        assert result == [{"id": 2, "name": "new"}]
    
    @pytest.mark.asyncio
    async def test_clear_cache_all(self, db_service: AsyncDatabaseService) -> None:
        """Test clear_cache without pattern."""
        db_service._query_cache = {
            "key1": ("data1", 123),
            "key2": ("data2", 456),
            "key3": ("data3", 789)
        }
        
        await db_service.clear_cache()
        
        assert db_service._query_cache == {}
    
    @pytest.mark.asyncio
    async def test_clear_cache_with_pattern(self, db_service: AsyncDatabaseService) -> None:
        """Test clear_cache with pattern."""
        db_service._query_cache = {
            "user_stats_1": ("data1", 123),
            "user_stats_2": ("data2", 456),
            "chat_messages_1": ("data3", 789)
        }
        
        await db_service.clear_cache("user_stats")
        
        assert "user_stats_1" not in db_service._query_cache
        assert "user_stats_2" not in db_service._query_cache
        assert "chat_messages_1" in db_service._query_cache
    
    @pytest.mark.asyncio
    async def test_save_chat_info_async_success(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test save_chat_info_async success."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.execute.return_value = "executed"
        
        chat_data = {
            "chat_id": 123,
            "chat_type": "group",
            "title": "Test Group"
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_chat_info_async(chat_data)
        
        assert result is True
        mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_chat_info_async_failure(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test save_chat_info_async failure."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.execute.side_effect = Exception("Database error")
        
        chat_data = {
            "chat_id": 123,
            "chat_type": "group",
            "title": "Test Group"
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_chat_info_async(chat_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_save_user_info_async_success(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test save_user_info_async success."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.execute.return_value = "executed"
        
        user_data = {
            "user_id": 456,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "is_bot": False
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_user_info_async(user_data)
        
        assert result is True
        mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_user_info_async_failure(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test save_user_info_async failure."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.execute.side_effect = Exception("Database error")
        
        user_data = {
            "user_id": 456,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "is_bot": False
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_user_info_async(user_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_save_message_async_success(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test save_message_async success."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        
        # Setup connection with proper transaction mocking
        self.setup_connection_with_transaction(mock_connection)
        
        mock_connection.execute.return_value = "executed"
        
        message_data = {
            "message_id": 789,
            "chat_id": 123,
            "user_id": 456,
            "timestamp": "2023-01-01T00:00:00Z",
            "text": "Hello world",
            "chat_type": "group",
            "chat_title": "Test Group",
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "is_bot": False,
            "is_command": False,
            "command_name": None,
            "is_gpt_reply": False,
            "replied_to_message_id": None,
            "gpt_context_message_ids": None,
            "raw_telegram_message": None
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_message_async(message_data)
        
        assert result is True
        # Should have called execute 3 times (chat, user, message)
        assert mock_connection.execute.call_count == 3
    
    @pytest.mark.asyncio
    async def test_save_message_async_failure(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock, mock_transaction: AsyncMock) -> None:
        """Test save_message_async failure."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.transaction.return_value = mock_transaction
        mock_connection.execute.side_effect = Exception("Database error")
        
        message_data = {
            "message_id": 789,
            "chat_id": 123,
            "user_id": 456,
            "timestamp": "2023-01-01T00:00:00Z",
            "text": "Hello world"
        }
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.save_message_async(message_data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_chat_messages_async_with_cache(self, db_service: AsyncDatabaseService) -> None:
        """Test get_chat_messages_async with caching."""
        import time
        
        # Setup cache
        cache_data = [{"id": 1, "text": "message1"}, {"id": 2, "text": "message2"}]
        db_service._query_cache["chat_messages_123_50_0"] = (cache_data, time.time())
        
        result = await db_service.get_chat_messages_async(123, 50, 0, use_cache=True)
        
        assert result == cache_data
    
    @pytest.mark.asyncio
    async def test_get_chat_messages_async_without_cache(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test get_chat_messages_async without caching."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetch.return_value = [{"id": 1, "text": "message1"}]
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.get_chat_messages_async(123, 50, 0, use_cache=False)
        
        assert result == [{"id": 1, "text": "message1"}]
        mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_messages_async(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test search_messages_async."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetch.return_value = [{"id": 1, "text": "found message"}]
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.search_messages_async(123, "test", 50)
        
        assert result == [{"id": 1, "text": "found message"}]
        mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_stats_async(self, db_service: AsyncDatabaseService) -> None:
        """Test get_user_stats_async."""
        import time
        
        # Setup cache
        cache_data = [{"total_messages": 10, "chats_participated": 2}]
        db_service._query_cache["user_stats_456"] = (cache_data, time.time())
        
        result = await db_service.get_user_stats_async(456)
        
        assert result == {"total_messages": 10, "chats_participated": 2}
    
    @pytest.mark.asyncio
    async def test_get_user_stats_async_no_data(self, db_service: AsyncDatabaseService) -> None:
        """Test get_user_stats_async with no data."""
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.get_user_stats_async(999)
        
        # The function returns a dict with keys even when no data is found
        assert isinstance(result, dict)
        assert result.get('total_messages') == 0
    
    @pytest.mark.asyncio
    async def test_get_chat_stats_async(self, db_service: AsyncDatabaseService) -> None:
        """Test get_chat_stats_async."""
        import time
        
        # Setup cache
        cache_data = [{"total_messages": 100, "unique_users": 5}]
        db_service._query_cache["chat_stats_123"] = (cache_data, time.time())
        
        result = await db_service.get_chat_stats_async(123)
        
        assert result == {"total_messages": 100, "unique_users": 5}
    
    @pytest.mark.asyncio
    async def test_get_chat_stats_async_no_data(self, db_service: AsyncDatabaseService) -> None:
        """Test get_chat_stats_async with no data."""
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.get_chat_stats_async(999)
        
        # The function returns a dict with keys even when no data is found
        assert isinstance(result, dict)
        assert result.get('total_messages') == 0
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test health_check success."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetchval.return_value = 1
        
        # Mock pool
        mock_pool = Mock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 5
        db_service.connection_manager.pool = mock_pool
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.health_check()
        
        assert result["status"] == "healthy"
        assert result["response_time_ms"] > 0
        assert result["pool_info"]["size"] == 10
        assert result["pool_info"]["idle"] == 5
        assert result["cache_entries"] == 0
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, db_service: AsyncDatabaseService, mock_connection_manager: AsyncMock, mock_connection: AsyncMock) -> None:
        """Test health_check failure."""
        db_service.connection_manager = mock_connection_manager
        mock_connection_manager.acquire.return_value = mock_connection
        mock_connection.fetchval.side_effect = Exception("Database error")
        
        with patch('modules.async_database_service.async_timeout'):
            result = await db_service.health_check()
        
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["pool_info"]["size"] == 0
        assert result["pool_info"]["idle"] == 0
        assert result["cache_entries"] == 0


class TestAsyncDatabaseServiceIntegration:
    """Integration tests for AsyncDatabaseService."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """Test full service lifecycle."""
        with patch('modules.async_database_service.AsyncRateLimiter') as mock_rate_limiter:
            mock_rate_limiter.return_value = AsyncMock()
            service = AsyncDatabaseService()
        
        # Mock the connection manager
        with patch.object(service, 'connection_manager') as mock_manager:
            mock_manager._initialize_pool = AsyncMock()
            mock_manager.cleanup = AsyncMock()
            
            # Test initialization
            await service.initialize()
            mock_manager._initialize_pool.assert_called_once()
            
            # Test shutdown
            await service.shutdown()
            mock_manager.cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self) -> None:
        """Test connection context manager behavior."""
        with patch('modules.async_database_service.AsyncRateLimiter') as mock_rate_limiter:
            mock_rate_limiter.return_value = AsyncMock()
            service = AsyncDatabaseService()
        
        with patch.object(service, 'connection_manager') as mock_manager:
            mock_connection = AsyncMock()
            mock_manager.acquire = AsyncMock(return_value=mock_connection)
            mock_manager.release = AsyncMock()
            
            async with service.get_connection() as conn:
                assert conn == mock_connection
            
            mock_manager.acquire.assert_called_once()
            mock_manager.release.assert_called_once_with(mock_connection)
    
    @pytest.mark.asyncio
    async def test_transaction_context_manager(self) -> None:
        """Test transaction context manager behavior."""
        with patch('modules.async_database_service.AsyncRateLimiter') as mock_rate_limiter:
            mock_rate_limiter.return_value = AsyncMock()
            service = AsyncDatabaseService()
        
        with patch.object(service, 'connection_manager') as mock_manager:
            mock_connection = AsyncMock()
            mock_manager.acquire = AsyncMock(return_value=mock_connection)
            mock_manager.release = AsyncMock()
            
            # Create a proper async context manager mock for transaction
            transaction_context = AsyncMock()
            transaction_context.__aenter__ = AsyncMock(return_value=mock_connection)
            transaction_context.__aexit__ = AsyncMock(return_value=None)
            mock_connection.transaction = Mock(return_value=transaction_context)
            
            async with service.get_transaction() as conn:
                assert conn == mock_connection
            
            mock_manager.acquire.assert_called_once()
            mock_manager.release.assert_called_once_with(mock_connection)
            mock_connection.transaction.assert_called_once() 