"""
Integration tests for database operations and data persistence.
"""

import pytest
import asyncio
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from modules.database import Database, DatabaseConnection, QueryBuilder
from modules.async_database_service import AsyncDatabaseService
from modules.repositories import UserRepository, ChatRepository, MessageRepository
from modules.error_handler import StandardError


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    @pytest.fixture
    async def test_database(self):
        """Create a test database instance."""
        # Use in-memory SQLite for testing
        original_db_url = os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        try:
            await Database.initialize()
            yield Database
        finally:
            await Database.close()
            if original_db_url:
                os.environ['DATABASE_URL'] = original_db_url
            elif 'DATABASE_URL' in os.environ:
                del os.environ['DATABASE_URL']
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, test_database):
        """Test database initialization and connection."""
        assert test_database._pool is not None
        
        # Test basic connection
        async with test_database.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
    
    @pytest.mark.asyncio
    async def test_table_creation_and_schema(self, test_database):
        """Test table creation and schema validation."""
        # Create test tables
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        create_chats_table = """
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        async with test_database.acquire() as conn:
            await conn.execute(create_users_table)
            await conn.execute(create_chats_table)
            
            # Verify tables exist
            tables = await conn.fetch("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            
            table_names = [table['name'] for table in tables]
            assert 'users' in table_names
            assert 'chats' in table_names
    
    @pytest.mark.asyncio
    async def test_basic_crud_operations(self, test_database):
        """Test basic CRUD operations."""
        # Setup table
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE test_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # CREATE
            item_id = await conn.fetchval("""
                INSERT INTO test_items (name, value) 
                VALUES (?, ?) RETURNING id
            """, "test_item", 42)
            
            assert item_id is not None
            
            # READ
            item = await conn.fetchrow("""
                SELECT * FROM test_items WHERE id = ?
            """, item_id)
            
            assert item['name'] == "test_item"
            assert item['value'] == 42
            
            # UPDATE
            await conn.execute("""
                UPDATE test_items SET value = ? WHERE id = ?
            """, 84, item_id)
            
            updated_item = await conn.fetchrow("""
                SELECT * FROM test_items WHERE id = ?
            """, item_id)
            
            assert updated_item['value'] == 84
            
            # DELETE
            await conn.execute("""
                DELETE FROM test_items WHERE id = ?
            """, item_id)
            
            deleted_item = await conn.fetchrow("""
                SELECT * FROM test_items WHERE id = ?
            """, item_id)
            
            assert deleted_item is None
    
    @pytest.mark.asyncio
    async def test_transaction_handling(self, test_database):
        """Test database transaction handling."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE transaction_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )
            """)
            
            # Test successful transaction
            async with conn.transaction():
                await conn.execute("INSERT INTO transaction_test (name) VALUES (?)", "item1")
                await conn.execute("INSERT INTO transaction_test (name) VALUES (?)", "item2")
            
            # Verify items were inserted
            count = await conn.fetchval("SELECT COUNT(*) FROM transaction_test")
            assert count == 2
            
            # Test failed transaction (should rollback)
            try:
                async with conn.transaction():
                    await conn.execute("INSERT INTO transaction_test (name) VALUES (?)", "item3")
                    # Simulate error
                    raise ValueError("Transaction error")
            except ValueError:
                pass
            
            # Verify rollback occurred
            count = await conn.fetchval("SELECT COUNT(*) FROM transaction_test")
            assert count == 2  # Should still be 2, not 3
    
    @pytest.mark.asyncio
    async def test_concurrent_database_access(self, test_database):
        """Test concurrent database access."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE concurrent_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT,
                    value INTEGER
                )
            """)
        
        async def insert_data(thread_id: str, count: int):
            async with test_database.acquire() as conn:
                for i in range(count):
                    await conn.execute("""
                        INSERT INTO concurrent_test (thread_id, value) VALUES (?, ?)
                    """, thread_id, i)
        
        # Run concurrent insertions
        tasks = [
            insert_data("thread_1", 10),
            insert_data("thread_2", 10),
            insert_data("thread_3", 10)
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all data was inserted correctly
        async with test_database.acquire() as conn:
            total_count = await conn.fetchval("SELECT COUNT(*) FROM concurrent_test")
            assert total_count == 30
            
            # Verify data integrity
            thread_counts = await conn.fetch("""
                SELECT thread_id, COUNT(*) as count 
                FROM concurrent_test 
                GROUP BY thread_id
            """)
            
            for row in thread_counts:
                assert row['count'] == 10
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, test_database):
        """Test database connection pooling."""
        # Test multiple concurrent connections
        async def use_connection(connection_id: int):
            async with test_database.acquire() as conn:
                # Simulate some work
                await asyncio.sleep(0.1)
                result = await conn.fetchval("SELECT ?", connection_id)
                return result
        
        # Create more tasks than the typical pool size
        tasks = [use_connection(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 20
        assert results == list(range(20))
    
    @pytest.mark.asyncio
    async def test_query_performance_optimization(self, test_database):
        """Test query performance and optimization."""
        async with test_database.acquire() as conn:
            # Create table with index
            await conn.execute("""
                CREATE TABLE performance_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indexed_field TEXT,
                    data TEXT
                )
            """)
            
            await conn.execute("""
                CREATE INDEX idx_indexed_field ON performance_test(indexed_field)
            """)
            
            # Insert test data
            test_data = [(f"key_{i}", f"data_{i}") for i in range(1000)]
            await conn.executemany("""
                INSERT INTO performance_test (indexed_field, data) VALUES (?, ?)
            """, test_data)
            
            # Test indexed query performance
            start_time = asyncio.get_event_loop().time()
            result = await conn.fetchrow("""
                SELECT * FROM performance_test WHERE indexed_field = ?
            """, "key_500")
            end_time = asyncio.get_event_loop().time()
            
            query_time = end_time - start_time
            
            assert result is not None
            assert result['indexed_field'] == "key_500"
            assert query_time < 0.1  # Should be fast with index
    
    @pytest.mark.asyncio
    async def test_data_types_and_serialization(self, test_database):
        """Test handling of different data types and serialization."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE data_types_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_field TEXT,
                    integer_field INTEGER,
                    real_field REAL,
                    blob_field BLOB,
                    json_field TEXT,
                    datetime_field TIMESTAMP
                )
            """)
            
            # Test data
            test_datetime = datetime.now()
            test_json = {"key": "value", "number": 42, "list": [1, 2, 3]}
            test_blob = b"binary data"
            
            # Insert data
            await conn.execute("""
                INSERT INTO data_types_test 
                (text_field, integer_field, real_field, blob_field, json_field, datetime_field)
                VALUES (?, ?, ?, ?, ?, ?)
            """, "test_text", 123, 45.67, test_blob, json.dumps(test_json), test_datetime)
            
            # Retrieve and verify data
            row = await conn.fetchrow("SELECT * FROM data_types_test WHERE id = 1")
            
            assert row['text_field'] == "test_text"
            assert row['integer_field'] == 123
            assert abs(row['real_field'] - 45.67) < 0.001
            assert row['blob_field'] == test_blob
            
            # Verify JSON serialization
            retrieved_json = json.loads(row['json_field'])
            assert retrieved_json == test_json
            
            # Verify datetime handling
            assert isinstance(row['datetime_field'], datetime)


class TestAsyncDatabaseService:
    """Integration tests for AsyncDatabaseService."""
    
    @pytest.fixture
    async def db_service(self):
        """Create an AsyncDatabaseService instance."""
        service = AsyncDatabaseService()
        await service.initialize()
        yield service
        await service.shutdown()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, db_service):
        """Test database service initialization."""
        assert db_service.is_connected()
        
        # Test health check
        health_status = await db_service.health_check()
        assert health_status['status'] == 'healthy'
        assert 'connection_pool' in health_status
    
    @pytest.mark.asyncio
    async def test_query_execution_with_service(self, db_service):
        """Test query execution through database service."""
        # Create test table
        await db_service.execute("""
            CREATE TABLE service_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert data
        result = await db_service.execute("""
            INSERT INTO service_test (name) VALUES (?)
        """, "test_name")
        
        # Query data
        rows = await db_service.fetch("""
            SELECT * FROM service_test WHERE name = ?
        """, "test_name")
        
        assert len(rows) == 1
        assert rows[0]['name'] == "test_name"
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, db_service):
        """Test batch database operations."""
        await db_service.execute("""
            CREATE TABLE batch_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                value INTEGER
            )
        """)
        
        # Batch insert
        batch_data = [
            ("item_1", 10),
            ("item_2", 20),
            ("item_3", 30)
        ]
        
        await db_service.execute_many("""
            INSERT INTO batch_test (name, value) VALUES (?, ?)
        """, batch_data)
        
        # Verify batch insert
        count = await db_service.fetchval("SELECT COUNT(*) FROM batch_test")
        assert count == 3
        
        # Batch update
        update_data = [(100, "item_1"), (200, "item_2")]
        await db_service.execute_many("""
            UPDATE batch_test SET value = ? WHERE name = ?
        """, update_data)
        
        # Verify updates
        updated_items = await db_service.fetch("""
            SELECT name, value FROM batch_test WHERE name IN ('item_1', 'item_2')
            ORDER BY name
        """)
        
        assert updated_items[0]['value'] == 100
        assert updated_items[1]['value'] == 200
    
    @pytest.mark.asyncio
    async def test_connection_retry_mechanism(self, db_service):
        """Test connection retry mechanism."""
        # Simulate connection failure and recovery
        original_execute = db_service.execute
        
        call_count = 0
        async def failing_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Connection failed")
            return await original_execute(*args, **kwargs)
        
        with patch.object(db_service, 'execute', side_effect=failing_execute):
            # This should succeed after retries
            await db_service.execute("SELECT 1")
            
            # Verify retries occurred
            assert call_count == 3


class TestRepositoryPattern:
    """Integration tests for repository pattern implementation."""
    
    @pytest.fixture
    async def repositories(self):
        """Create repository instances."""
        # Initialize database
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        await Database.initialize()
        
        # Create repositories
        user_repo = UserRepository()
        chat_repo = ChatRepository()
        message_repo = MessageRepository()
        
        # Setup tables
        await self._setup_tables()
        
        yield {
            'user': user_repo,
            'chat': chat_repo,
            'message': message_repo
        }
        
        await Database.close()
    
    async def _setup_tables(self):
        """Setup test tables."""
        async with Database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE chats (
                    id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    user_id INTEGER,
                    text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
    
    @pytest.mark.asyncio
    async def test_user_repository_operations(self, repositories):
        """Test user repository operations."""
        user_repo = repositories['user']
        
        # Create user
        user_data = {
            'id': 12345,
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        created_user = await user_repo.create(user_data)
        assert created_user['id'] == 12345
        assert created_user['username'] == 'testuser'
        
        # Get user by ID
        retrieved_user = await user_repo.get_by_id(12345)
        assert retrieved_user is not None
        assert retrieved_user['username'] == 'testuser'
        
        # Update user
        await user_repo.update(12345, {'first_name': 'Updated'})
        updated_user = await user_repo.get_by_id(12345)
        assert updated_user['first_name'] == 'Updated'
        
        # Find users by criteria
        users = await user_repo.find_by_criteria({'first_name': 'Updated'})
        assert len(users) == 1
        assert users[0]['id'] == 12345
        
        # Delete user
        await user_repo.delete(12345)
        deleted_user = await user_repo.get_by_id(12345)
        assert deleted_user is None
    
    @pytest.mark.asyncio
    async def test_chat_repository_operations(self, repositories):
        """Test chat repository operations."""
        chat_repo = repositories['chat']
        
        # Create chat
        chat_data = {
            'id': -1001234567890,
            'type': 'supergroup',
            'title': 'Test Group'
        }
        
        created_chat = await chat_repo.create(chat_data)
        assert created_chat['id'] == -1001234567890
        assert created_chat['type'] == 'supergroup'
        
        # Get chat by ID
        retrieved_chat = await chat_repo.get_by_id(-1001234567890)
        assert retrieved_chat is not None
        assert retrieved_chat['title'] == 'Test Group'
        
        # Find chats by type
        group_chats = await chat_repo.find_by_criteria({'type': 'supergroup'})
        assert len(group_chats) == 1
        assert group_chats[0]['id'] == -1001234567890
    
    @pytest.mark.asyncio
    async def test_message_repository_operations(self, repositories):
        """Test message repository operations."""
        user_repo = repositories['user']
        chat_repo = repositories['chat']
        message_repo = repositories['message']
        
        # Setup user and chat
        await user_repo.create({
            'id': 12345,
            'username': 'testuser',
            'first_name': 'Test'
        })
        
        await chat_repo.create({
            'id': -1001234567890,
            'type': 'supergroup',
            'title': 'Test Group'
        })
        
        # Create message
        message_data = {
            'chat_id': -1001234567890,
            'user_id': 12345,
            'text': 'Test message'
        }
        
        created_message = await message_repo.create(message_data)
        assert created_message['text'] == 'Test message'
        assert created_message['chat_id'] == -1001234567890
        
        # Get messages for chat
        chat_messages = await message_repo.get_messages_for_chat(-1001234567890)
        assert len(chat_messages) == 1
        assert chat_messages[0]['text'] == 'Test message'
        
        # Get messages by user
        user_messages = await message_repo.get_messages_by_user(12345)
        assert len(user_messages) == 1
        assert user_messages[0]['user_id'] == 12345
    
    @pytest.mark.asyncio
    async def test_repository_relationships(self, repositories):
        """Test relationships between repositories."""
        user_repo = repositories['user']
        chat_repo = repositories['chat']
        message_repo = repositories['message']
        
        # Create test data
        user = await user_repo.create({
            'id': 12345,
            'username': 'testuser',
            'first_name': 'Test'
        })
        
        chat = await chat_repo.create({
            'id': -1001234567890,
            'type': 'supergroup',
            'title': 'Test Group'
        })
        
        # Create multiple messages
        messages = []
        for i in range(5):
            message = await message_repo.create({
                'chat_id': chat['id'],
                'user_id': user['id'],
                'text': f'Message {i + 1}'
            })
            messages.append(message)
        
        # Test relationship queries
        chat_with_messages = await chat_repo.get_chat_with_messages(chat['id'])
        assert len(chat_with_messages['messages']) == 5
        
        user_with_message_count = await user_repo.get_user_with_stats(user['id'])
        assert user_with_message_count['message_count'] == 5


class TestDatabaseErrorHandling:
    """Test database error handling and recovery."""
    
    @pytest.fixture
    async def test_database(self):
        """Create a test database instance."""
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        await Database.initialize()
        yield Database
        await Database.close()
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, test_database):
        """Test handling of connection errors."""
        # Simulate connection failure
        with patch.object(test_database, 'acquire') as mock_acquire:
            mock_acquire.side_effect = ConnectionError("Database connection failed")
            
            with pytest.raises(StandardError, match="Database connection failed"):
                async with test_database.acquire() as conn:
                    await conn.fetchval("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_query_error_handling(self, test_database):
        """Test handling of SQL query errors."""
        async with test_database.acquire() as conn:
            # Test syntax error
            with pytest.raises(Exception):  # SQLite syntax error
                await conn.execute("INVALID SQL SYNTAX")
            
            # Test constraint violation
            await conn.execute("""
                CREATE TABLE constraint_test (
                    id INTEGER PRIMARY KEY,
                    unique_field TEXT UNIQUE
                )
            """)
            
            await conn.execute("""
                INSERT INTO constraint_test (id, unique_field) VALUES (1, 'unique_value')
            """)
            
            # This should raise a constraint violation
            with pytest.raises(Exception):  # SQLite constraint error
                await conn.execute("""
                    INSERT INTO constraint_test (id, unique_field) VALUES (2, 'unique_value')
                """)
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, test_database):
        """Test transaction rollback on error."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE rollback_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)
            
            # Insert initial data
            await conn.execute("INSERT INTO rollback_test (id, name) VALUES (1, 'initial')")
            
            # Test transaction rollback
            try:
                async with conn.transaction():
                    await conn.execute("INSERT INTO rollback_test (id, name) VALUES (2, 'temp')")
                    # Force an error
                    await conn.execute("INSERT INTO rollback_test (id, name) VALUES (1, 'duplicate')")  # Duplicate ID
            except Exception:
                pass
            
            # Verify rollback occurred
            count = await conn.fetchval("SELECT COUNT(*) FROM rollback_test")
            assert count == 1  # Only initial record should remain
            
            record = await conn.fetchrow("SELECT * FROM rollback_test WHERE id = 2")
            assert record is None  # Temp record should be rolled back


class TestDatabasePerformance:
    """Performance tests for database operations."""
    
    @pytest.fixture
    async def test_database(self):
        """Create a test database instance."""
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        await Database.initialize()
        yield Database
        await Database.close()
    
    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self, test_database):
        """Test bulk insert performance."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE performance_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    value INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Prepare bulk data
            bulk_data = [(f"item_{i}", i) for i in range(1000)]
            
            # Test bulk insert performance
            start_time = asyncio.get_event_loop().time()
            await conn.executemany("""
                INSERT INTO performance_test (name, value) VALUES (?, ?)
            """, bulk_data)
            end_time = asyncio.get_event_loop().time()
            
            insert_time = end_time - start_time
            
            # Verify all data was inserted
            count = await conn.fetchval("SELECT COUNT(*) FROM performance_test")
            assert count == 1000
            
            # Performance should be reasonable (less than 1 second for 1000 records)
            assert insert_time < 1.0
    
    @pytest.mark.asyncio
    async def test_query_performance_with_indexes(self, test_database):
        """Test query performance with and without indexes."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE index_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    searchable_field TEXT,
                    data TEXT
                )
            """)
            
            # Insert test data
            test_data = [(f"search_{i}", f"data_{i}") for i in range(10000)]
            await conn.executemany("""
                INSERT INTO index_test (searchable_field, data) VALUES (?, ?)
            """, test_data)
            
            # Test query without index
            start_time = asyncio.get_event_loop().time()
            result = await conn.fetchrow("""
                SELECT * FROM index_test WHERE searchable_field = ?
            """, "search_5000")
            end_time = asyncio.get_event_loop().time()
            
            query_time_without_index = end_time - start_time
            
            # Create index
            await conn.execute("""
                CREATE INDEX idx_searchable_field ON index_test(searchable_field)
            """)
            
            # Test query with index
            start_time = asyncio.get_event_loop().time()
            result_with_index = await conn.fetchrow("""
                SELECT * FROM index_test WHERE searchable_field = ?
            """, "search_5000")
            end_time = asyncio.get_event_loop().time()
            
            query_time_with_index = end_time - start_time
            
            # Verify results are the same
            assert result['searchable_field'] == result_with_index['searchable_field']
            
            # Index should improve performance (though difference might be small with SQLite in memory)
            assert query_time_with_index <= query_time_without_index
    
    @pytest.mark.asyncio
    async def test_concurrent_read_write_performance(self, test_database):
        """Test concurrent read/write performance."""
        async with test_database.acquire() as conn:
            await conn.execute("""
                CREATE TABLE concurrent_perf_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT,
                    operation_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        async def write_operations(thread_id: str, count: int):
            async with test_database.acquire() as conn:
                for i in range(count):
                    await conn.execute("""
                        INSERT INTO concurrent_perf_test (thread_id, operation_type) 
                        VALUES (?, ?)
                    """, thread_id, "write")
        
        async def read_operations(thread_id: str, count: int):
            async with test_database.acquire() as conn:
                for i in range(count):
                    await conn.fetchval("""
                        SELECT COUNT(*) FROM concurrent_perf_test 
                        WHERE thread_id = ?
                    """, thread_id)
                    
                    # Log read operation
                    await conn.execute("""
                        INSERT INTO concurrent_perf_test (thread_id, operation_type) 
                        VALUES (?, ?)
                    """, thread_id, "read")
        
        # Run concurrent read/write operations
        start_time = asyncio.get_event_loop().time()
        
        tasks = [
            write_operations("writer_1", 100),
            write_operations("writer_2", 100),
            read_operations("reader_1", 50),
            read_operations("reader_2", 50)
        ]
        
        await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        # Verify operations completed
        async with test_database.acquire() as conn:
            total_operations = await conn.fetchval("""
                SELECT COUNT(*) FROM concurrent_perf_test
            """)
            
            # Should have 200 writes + 100 reads = 300 operations
            assert total_operations == 300
            
            # Performance should be reasonable
            assert total_time < 5.0  # Should complete within 5 seconds