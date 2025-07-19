"""
Async Database Service

Enhanced database service using improved async patterns, connection pooling,
and resource management.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional
import asyncpg

from modules.async_utils import (
    AsyncConnectionPool, AsyncResourceManager, async_retry, 
    async_timeout, AsyncRateLimiter
)
from modules.service_registry import ServiceInterface
from modules.database import Database, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)


class AsyncDatabaseConnectionManager(AsyncResourceManager):
    """Async resource manager for database connections."""
    
    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None
        self._connection_pool: Optional[AsyncConnectionPool] = None
        self._rate_limiter = AsyncRateLimiter(max_calls=100, time_window=1.0)  # 100 queries/sec
    
    async def acquire(self) -> asyncpg.Connection:
        """Acquire a database connection."""
        if not self.pool:
            await self._initialize_pool()
        
        # Rate limit database connections
        await self._rate_limiter.acquire()
        
        return await self.pool.acquire()
    
    async def release(self, connection: asyncpg.Connection) -> None:
        """Release a database connection."""
        if self.pool and connection:
            await self.pool.release(connection)
    
    async def cleanup(self) -> None:
        """Cleanup database connections."""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def _initialize_pool(self) -> None:
        """Initialize the connection pool."""
        self.pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=30,
            server_settings={
                'application_name': 'psychochauffeur_bot_async',
                'jit': 'off'
            },
            init=self._init_connection
        )
    
    async def _init_connection(self, connection: asyncpg.Connection) -> None:
        """Initialize a new connection."""
        # Set connection-specific settings
        await connection.execute("SET timezone = 'UTC'")
        await connection.execute("SET statement_timeout = '30s'")


class AsyncDatabaseService(ServiceInterface):
    """
    Enhanced async database service with improved patterns.
    
    Features:
    - Connection pooling with resource management
    - Automatic retry with exponential backoff
    - Query timeout handling
    - Rate limiting
    - Transaction management
    - Query batching
    """
    
    def __init__(self) -> None:
        self.connection_manager = AsyncDatabaseConnectionManager()
        self._query_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._batch_size = 100
    
    async def initialize(self) -> None:
        """Initialize the database service."""
        await self.connection_manager._initialize_pool()
        logger.info("Async Database Service initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the database service."""
        await self.connection_manager.cleanup()
        self._query_cache.clear()
        logger.info("Async Database Service shutdown")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection with automatic resource management."""
        connection = await self.connection_manager.acquire()
        try:
            yield connection
        finally:
            await self.connection_manager.release(connection)
    
    @asynccontextmanager
    async def get_transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database transaction with automatic rollback on error."""
        async with self.get_connection() as connection:
            async with connection.transaction():
                yield connection
    
    @async_retry(max_attempts=3, base_delay=1.0, exceptions=(asyncpg.PostgresError,))
    async def execute_query(
        self, 
        query: str, 
        *args, 
        timeout: float = 30.0,
        fetch_mode: str = "none"
    ) -> Any:
        """
        Execute a database query with retry and timeout.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Query timeout in seconds
            fetch_mode: "none", "one", "all", or "val"
        """
        async with async_timeout(timeout):
            async with self.get_connection() as connection:
                if fetch_mode == "one":
                    return await connection.fetchrow(query, *args)
                elif fetch_mode == "all":
                    return await connection.fetch(query, *args)
                elif fetch_mode == "val":
                    return await connection.fetchval(query, *args)
                else:
                    return await connection.execute(query, *args)
    
    async def execute_batch(
        self, 
        query: str, 
        args_list: List[tuple],
        timeout: float = 60.0
    ) -> None:
        """Execute a batch of queries efficiently."""
        async with async_timeout(timeout):
            async with self.get_connection() as connection:
                await connection.executemany(query, args_list)
    
    async def execute_transaction(
        self, 
        queries: List[tuple],
        timeout: float = 60.0
    ) -> List[Any]:
        """
        Execute multiple queries in a transaction.
        
        Args:
            queries: List of (query, args, fetch_mode) tuples
            timeout: Transaction timeout in seconds
        """
        results = []
        
        async with async_timeout(timeout):
            async with self.get_transaction() as connection:
                for query_info in queries:
                    if len(query_info) == 2:
                        query, args = query_info
                        fetch_mode = "none"
                    else:
                        query, args, fetch_mode = query_info
                    
                    if fetch_mode == "one":
                        result = await connection.fetchrow(query, *args)
                    elif fetch_mode == "all":
                        result = await connection.fetch(query, *args)
                    elif fetch_mode == "val":
                        result = await connection.fetchval(query, *args)
                    else:
                        result = await connection.execute(query, *args)
                    
                    results.append(result)
        
        return results
    
    async def get_cached_query(
        self, 
        cache_key: str, 
        query: str, 
        *args,
        ttl: Optional[int] = None
    ) -> Any:
        """Execute query with caching."""
        import time
        
        # Check cache
        if cache_key in self._query_cache:
            cached_data, cached_time = self._query_cache[cache_key]
            cache_ttl = ttl or self._cache_ttl
            
            if time.time() - cached_time < cache_ttl:
                return cached_data
        
        # Execute query
        result = await self.execute_query(query, *args, fetch_mode="all")
        
        # Cache result
        self._query_cache[cache_key] = (result, time.time())
        
        return result
    
    async def clear_cache(self, pattern: Optional[str] = None) -> None:
        """Clear query cache."""
        if pattern:
            keys_to_remove = [k for k in self._query_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._query_cache[key]
        else:
            self._query_cache.clear()
    
    # Enhanced database operations using new patterns
    
    async def save_chat_info_async(self, chat_data: Dict[str, Any]) -> bool:
        """Save chat information with enhanced async patterns."""
        try:
            await self.execute_query(
                """
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = $2, title = $3
                """,
                chat_data['chat_id'],
                chat_data['chat_type'],
                chat_data.get('title')
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save chat info: {e}")
            return False
    
    async def save_user_info_async(self, user_data: Dict[str, Any]) -> bool:
        """Save user information with enhanced async patterns."""
        try:
            await self.execute_query(
                """
                INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE
                SET first_name = $2, last_name = $3, username = $4, is_bot = $5
                """,
                user_data['user_id'],
                user_data['first_name'],
                user_data.get('last_name'),
                user_data.get('username'),
                user_data.get('is_bot', False)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save user info: {e}")
            return False
    
    async def save_message_async(self, message_data: Dict[str, Any]) -> bool:
        """Save message with enhanced async patterns."""
        try:
            # Save in transaction to ensure consistency
            queries = [
                (
                    """
                    INSERT INTO chats (chat_id, chat_type, title)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (chat_id) DO UPDATE
                    SET chat_type = $2, title = $3
                    """,
                    (
                        message_data['chat_id'],
                        message_data['chat_type'],
                        message_data.get('chat_title')
                    )
                ),
                (
                    """
                    INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE
                    SET first_name = $2, last_name = $3, username = $4, is_bot = $5
                    """,
                    (
                        message_data['user_id'],
                        message_data['first_name'],
                        message_data.get('last_name'),
                        message_data.get('username'),
                        message_data.get('is_bot', False)
                    )
                ),
                (
                    """
                    INSERT INTO messages (
                        message_id, chat_id, user_id, timestamp, text,
                        is_command, command_name, is_gpt_reply,
                        replied_to_message_id, gpt_context_message_ids,
                        raw_telegram_message
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (chat_id, message_id) DO NOTHING
                    """,
                    (
                        message_data['message_id'],
                        message_data['chat_id'],
                        message_data['user_id'],
                        message_data['timestamp'],
                        message_data.get('text'),
                        message_data.get('is_command', False),
                        message_data.get('command_name'),
                        message_data.get('is_gpt_reply', False),
                        message_data.get('replied_to_message_id'),
                        message_data.get('gpt_context_message_ids'),
                        message_data.get('raw_telegram_message')
                    )
                )
            ]
            
            await self.execute_transaction(queries)
            return True
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False
    
    async def get_chat_messages_async(
        self, 
        chat_id: int, 
        limit: int = 50, 
        offset: int = 0,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Get chat messages with caching."""
        cache_key = f"chat_messages_{chat_id}_{limit}_{offset}"
        
        if use_cache:
            return await self.get_cached_query(
                cache_key,
                """
                SELECT * FROM messages 
                WHERE chat_id = $1 
                ORDER BY timestamp DESC 
                LIMIT $2 OFFSET $3
                """,
                chat_id, limit, offset
            )
        else:
            return await self.execute_query(
                """
                SELECT * FROM messages 
                WHERE chat_id = $1 
                ORDER BY timestamp DESC 
                LIMIT $2 OFFSET $3
                """,
                chat_id, limit, offset,
                fetch_mode="all"
            )
    
    async def search_messages_async(
        self, 
        chat_id: int, 
        search_text: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search messages with full-text search."""
        return await self.execute_query(
            """
            SELECT * FROM messages 
            WHERE chat_id = $1 AND text ILIKE $2
            ORDER BY timestamp DESC 
            LIMIT $3
            """,
            chat_id, f"%{search_text}%", limit,
            fetch_mode="all"
        )
    
    async def get_user_stats_async(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics with caching."""
        cache_key = f"user_stats_{user_id}"
        
        result = await self.get_cached_query(
            cache_key,
            """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT chat_id) as chats_participated,
                COUNT(*) FILTER (WHERE is_command = true) as commands_used,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM messages 
            WHERE user_id = $1
            """,
            user_id,
            ttl=600  # 10 minutes cache
        )
        
        return dict(result[0]) if result else {}
    
    async def get_chat_stats_async(self, chat_id: int) -> Dict[str, Any]:
        """Get chat statistics with caching."""
        cache_key = f"chat_stats_{chat_id}"
        
        result = await self.get_cached_query(
            cache_key,
            """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(*) FILTER (WHERE is_command = true) as command_count,
                COUNT(*) FILTER (WHERE is_gpt_reply = true) as gpt_replies,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message
            FROM messages 
            WHERE chat_id = $1
            """,
            chat_id,
            ttl=300  # 5 minutes cache
        )
        
        return dict(result[0]) if result else {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Test basic connectivity
            result = await self.execute_query("SELECT 1", fetch_mode="val")
            
            # Test pool status
            pool_info = {
                "size": self.connection_manager.pool.get_size() if self.connection_manager.pool else 0,
                "idle": self.connection_manager.pool.get_idle_size() if self.connection_manager.pool else 0,
            }
            
            response_time = asyncio.get_event_loop().time() - start_time
            
            return {
                "status": "healthy" if result == 1 else "unhealthy",
                "response_time_ms": round(response_time * 1000, 2),
                "pool_info": pool_info,
                "cache_entries": len(self._query_cache)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "pool_info": {"size": 0, "idle": 0},
                "cache_entries": len(self._query_cache)
            }