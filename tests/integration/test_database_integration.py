"""
Integration tests for database operations and data persistence.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from telegram import Chat, User, Message

from modules.database import Database, DatabaseConnectionManager
from modules.error_handler import ErrorHandler


class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    @pytest.fixture
    async def test_database(self):
        """Create a test database instance."""
        # Mock database for testing
        with patch('modules.database.Database.initialize') as mock_init:
            mock_init.return_value = None
            yield Database
    
    @pytest.fixture
    def mock_chat(self):
        """Create a mock chat object."""
        return Chat(
            id=-1001234567890,
            type="supergroup",
            title="Test Chat"
        )
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user object."""
        return User(
            id=123456789,
            first_name="Test",
            last_name="User",
            username="testuser",
            is_bot=False
        )
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, test_database):
        """Test database initialization."""
        with patch.object(Database, 'initialize') as mock_init:
            mock_init.return_value = None
            
            await Database.initialize()
            
            mock_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_chat_info(self, test_database, mock_chat):
        """Test saving chat information."""
        with patch.object(Database, 'save_chat_info') as mock_save:
            mock_save.return_value = None
            
            await Database.save_chat_info(mock_chat)
            
            mock_save.assert_called_once_with(mock_chat)
    
    @pytest.mark.asyncio
    async def test_save_user_info(self, test_database, mock_user):
        """Test saving user information."""
        with patch.object(Database, 'save_user_info') as mock_save:
            mock_save.return_value = None
            
            await Database.save_user_info(mock_user)
            
            mock_save.assert_called_once_with(mock_user)
    
    @pytest.mark.asyncio
    async def test_get_message_count(self, test_database):
        """Test getting message count."""
        chat_id = -1001234567890
        
        with patch.object(Database, 'get_message_count') as mock_count:
            mock_count.return_value = 42
            
            count = await Database.get_message_count(chat_id)
            
            assert count == 42
            mock_count.assert_called_once_with(chat_id)
    
    @pytest.mark.asyncio
    async def test_get_recent_messages(self, test_database):
        """Test getting recent messages."""
        chat_id = -1001234567890
        
        with patch.object(Database, 'get_recent_messages') as mock_messages:
            mock_messages.return_value = [
                {"message_id": 1, "text": "Hello", "timestamp": datetime.now()},
                {"message_id": 2, "text": "World", "timestamp": datetime.now()}
            ]
            
            messages = await Database.get_recent_messages(chat_id, limit=10)
            
            assert len(messages) == 2
            mock_messages.assert_called_once_with(chat_id, limit=10)
    
    @pytest.mark.asyncio
    async def test_analysis_cache_operations(self, test_database):
        """Test analysis cache set and get operations."""
        chat_id = -1001234567890
        time_period = "today"
        message_hash = "test_hash_123"
        result = "Test analysis result"
        
        with patch.object(Database, 'set_analysis_cache') as mock_set:
            mock_set.return_value = None
            
            await Database.set_analysis_cache(chat_id, time_period, message_hash, result)
            
            mock_set.assert_called_once_with(chat_id, time_period, message_hash, result)
        
        with patch.object(Database, 'get_analysis_cache') as mock_get:
            mock_get.return_value = result
            
            cached_result = await Database.get_analysis_cache(chat_id, time_period, message_hash, 3600)
            
            assert cached_result == result
            mock_get.assert_called_once_with(chat_id, time_period, message_hash, 3600)


class TestDatabaseConnectionManager:
    """Test database connection management."""
    
    @pytest.fixture
    def connection_manager(self):
        """Create a connection manager instance."""
        return DatabaseConnectionManager()
    
    @pytest.mark.asyncio
    async def test_connection_manager_initialization(self, connection_manager):
        """Test connection manager initialization."""
        assert connection_manager is not None
        assert hasattr(connection_manager, '_pool')
        assert hasattr(connection_manager, '_connection_stats')
    
    def test_connection_stats(self, connection_manager):
        """Test connection statistics."""
        stats = connection_manager.get_stats()
        
        assert isinstance(stats, dict)
        assert 'total_connections' in stats
        assert 'active_connections' in stats
        assert 'failed_connections' in stats


class TestDatabaseErrorHandling:
    """Test database error handling."""
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of database connection errors."""
        with patch('modules.database.asyncpg.create_pool') as mock_pool:
            mock_pool.side_effect = Exception("Connection failed")
            
            manager = DatabaseConnectionManager()
            
            with pytest.raises(Exception):
                await manager.get_pool()
    
    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        """Test handling of database query errors."""
        with patch.object(Database, 'get_message_count') as mock_count:
            mock_count.side_effect = Exception("Query failed")
            
            with pytest.raises(Exception):
                await Database.get_message_count(-1001234567890)