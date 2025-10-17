"""
Database setup utilities for testing.
"""

import asyncio
import asyncpg
import sqlite3
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from unittest.mock import Mock, AsyncMock

from modules.database import Database


class TestDatabaseManager:
    """Manager for test database setup and teardown."""
    
    def __init__(self, use_sqlite: bool = True):
        self.use_sqlite = use_sqlite
        self.temp_db_path = None
        self.connection = None
        self.pool = None
    
    async def setup(self) -> None:
        """Set up the test database."""
        # Check if PostgreSQL is available via DATABASE_URL
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL if available (CI environment)
            await self._setup_postgresql()
        else:
            # Use SQLite for local testing
            await self._setup_sqlite()
    
    async def teardown(self) -> None:
        """Tear down the test database."""
        # Check if PostgreSQL is available via DATABASE_URL
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL if available (CI environment)
            await self._teardown_postgresql()
        else:
            # Use SQLite for local testing
            await self._teardown_sqlite()
    
    async def _setup_sqlite(self) -> None:
        """Set up SQLite test database."""
        # Create temporary database file
        fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Override the database URL for testing
        original_url = os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db_path}'
        
        # Initialize the database
        await Database.initialize()
        
        # Create test tables
        await self._create_test_tables()
    
    async def _teardown_sqlite(self) -> None:
        """Tear down SQLite test database."""
        if Database._pool:
            await Database.close()
        
        if self.temp_db_path and os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
    
    async def _setup_postgresql(self) -> None:
        """Set up PostgreSQL test database."""
        # Use the existing DATABASE_URL if it's PostgreSQL, otherwise use SQLite
        original_url = os.environ.get('DATABASE_URL')
        
        if not original_url or not original_url.startswith('postgresql://'):
            # Fall back to SQLite if no PostgreSQL URL is provided
            await self._setup_sqlite()
            return
        
        # Initialize the database with PostgreSQL
        await Database.initialize()
        
        # Create test tables
        await self._create_test_tables()
    
    async def _teardown_postgresql(self) -> None:
        """Tear down PostgreSQL test database."""
        if Database._pool:
            await Database.close()
        Database._pool = None
    
    async def _create_test_tables(self) -> None:
        """Create test tables in the database."""
        # This would create the actual tables needed for testing
        # For now, we'll create some basic test tables
        
        tables = [
            """
            CREATE TABLE IF NOT EXISTS test_users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS test_chats (
                id INTEGER PRIMARY KEY,
                type TEXT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS test_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES test_chats (id),
                FOREIGN KEY (user_id) REFERENCES test_users (id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS test_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT,
                message TEXT,
                severity TEXT,
                category TEXT,
                context TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        # Check if we're using PostgreSQL or SQLite
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                for table_sql in tables:
                    # Convert SQLite syntax to PostgreSQL
                    pg_sql = table_sql.replace('AUTOINCREMENT', 'SERIAL')
                    pg_sql = pg_sql.replace('INTEGER PRIMARY KEY', 'BIGSERIAL PRIMARY KEY')
                    await conn.execute(pg_sql)
        else:
            # Use SQLite
            conn = sqlite3.connect(self.temp_db_path)
            try:
                for table_sql in tables:
                    conn.execute(table_sql)
                conn.commit()
            finally:
                conn.close()
    
    async def insert_test_data(self, table: str, data: List[Dict[str, Any]]) -> None:
        """Insert test data into a table."""
        if not data:
            return
        
        # Check if we're using PostgreSQL or SQLite
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                # Build insert statement
                columns = list(data[0].keys())
                placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                
                # Insert data
                for row in data:
                    values = [row[col] for col in columns]
                    await conn.execute(sql, *values)
        else:
            # Use SQLite
            conn = sqlite3.connect(self.temp_db_path)
            try:
                # Build insert statement
                columns = list(data[0].keys())
                placeholders = ', '.join(['?' for _ in columns])
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                
                # Insert data
                for row in data:
                    values = [row[col] for col in columns]
                    conn.execute(sql, values)
                
                conn.commit()
            finally:
                conn.close()
    
    async def query_test_data(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Query test data from the database."""
        # Check if we're using PostgreSQL or SQLite
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *(params or ()))
                return [dict(row) for row in rows]
        else:
            # Use SQLite
            conn = sqlite3.connect(self.temp_db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            try:
                cursor = conn.execute(sql, params or ())
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
    
    async def clear_table(self, table: str) -> None:
        """Clear all data from a table."""
        # Check if we're using PostgreSQL or SQLite
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # Use PostgreSQL
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(f"DELETE FROM {table}")
        else:
            # Use SQLite
            conn = sqlite3.connect(self.temp_db_path)
            try:
                conn.execute(f"DELETE FROM {table}")
                conn.commit()
            finally:
                conn.close()


class TestDataSeeder:
    """Utility for seeding test data."""
    
    def __init__(self, db_manager: TestDatabaseManager):
        self.db_manager = db_manager
    
    async def seed_users(self, count: int = 5) -> List[Dict[str, Any]]:
        """Seed test users."""
        users = []
        for i in range(count):
            user = {
                'id': 12345 + i,
                'username': f'testuser{i + 1}',
                'first_name': f'Test{i + 1}',
                'last_name': 'User'
            }
            users.append(user)
        
        await self.db_manager.insert_test_data('test_users', users)
        return users
    
    async def seed_chats(self, count: int = 3) -> List[Dict[str, Any]]:
        """Seed test chats."""
        chats = []
        for i in range(count):
            chat = {
                'id': -1001234567890 - i if i > 0 else 12345,  # First is private, rest are groups
                'type': 'private' if i == 0 else 'supergroup',
                'title': None if i == 0 else f'Test Group {i}'
            }
            chats.append(chat)
        
        await self.db_manager.insert_test_data('test_chats', chats)
        return chats
    
    async def seed_messages(self, chat_id: int, user_ids: List[int], count: int = 10) -> List[Dict[str, Any]]:
        """Seed test messages for a chat."""
        messages = []
        for i in range(count):
            message = {
                'chat_id': chat_id,
                'user_id': user_ids[i % len(user_ids)],
                'text': f'Test message {i + 1}'
            }
            messages.append(message)
        
        await self.db_manager.insert_test_data('test_messages', messages)
        return messages
    
    
    async def seed_errors(self, count: int = 5) -> List[Dict[str, Any]]:
        """Seed test error records."""
        import json
        
        errors = []
        error_types = ['network', 'database', 'api', 'general', 'input']
        severities = ['low', 'medium', 'high', 'critical']
        
        for i in range(count):
            error = {
                'error_type': error_types[i % len(error_types)],
                'message': f'Test error {i + 1}',
                'severity': severities[i % len(severities)],
                'category': error_types[i % len(error_types)],
                'context': json.dumps({'test_key': f'test_value_{i}'})
            }
            errors.append(error)
        
        await self.db_manager.insert_test_data('test_errors', errors)
        return errors


class DatabaseTestCase:
    """Base class for database test cases."""
    
    def __init__(self) -> None:
        self.db_manager = TestDatabaseManager()
        self.seeder = TestDataSeeder(self.db_manager)
    
    async def setup(self) -> None:
        """Set up the test case."""
        await self.db_manager.setup()
    
    async def teardown(self) -> None:
        """Tear down the test case."""
        await self.db_manager.teardown()
    


# Pytest fixtures for database testing

import pytest

@pytest.fixture
async def test_db() -> TestDatabaseManager:
    """Provide a test database instance."""
    db_manager = TestDatabaseManager()
    await db_manager.setup()
    yield db_manager
    await db_manager.teardown()


@pytest.fixture
async def seeded_db() -> tuple[TestDatabaseManager, dict[str, list[dict[str, Any]]]]:
    """Provide a test database with seeded data."""
    db_manager = TestDatabaseManager()
    await db_manager.setup()
    
    seeder = TestDataSeeder(db_manager)
    users = await seeder.seed_users(3)
    chats = await seeder.seed_chats(2)
    
    # Seed messages for the first chat
    await seeder.seed_messages(chats[0]['id'], [u['id'] for u in users], 5)
    
    
    # Seed some error records
    await seeder.seed_errors(3)
    
    yield db_manager, {'users': users, 'chats': chats}
    await db_manager.teardown()


@pytest.fixture
async def db_test_case() -> DatabaseTestCase:
    """Provide a database test case instance."""
    test_case = DatabaseTestCase()
    await test_case.setup()
    yield test_case
    await test_case.teardown()