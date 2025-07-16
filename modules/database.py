import os
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import asyncpg
from telegram import Chat, User, Message
from dotenv import load_dotenv
import pytz

from modules.types import (
    UserId, ChatId, MessageId, Timestamp, JSONDict, QueryResult,
    DatabaseOperation, CacheEntry
)
from modules.shared_constants import (
    DEFAULT_DATABASE_URL, DATABASE_POOL_SIZE, DATABASE_TIMEOUT, 
    DATABASE_RETRY_ATTEMPTS, DEFAULT_CACHE_TTL
)
from modules.shared_utilities import (
    CacheManager, PerformanceMonitor, RetryManager, AsyncContextManager
)
from modules.error_decorators import handle_database_errors, database_operation

load_dotenv()

logger = logging.getLogger(__name__)

# Database connection configuration with type hints
DB_HOST: str = os.getenv('DB_HOST', 'localhost')
DB_PORT: str = os.getenv('DB_PORT', '5432')
DB_NAME: str = os.getenv('DB_NAME', 'telegram_bot')
DB_USER: str = os.getenv('DB_USER', 'postgres')
DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')

# Connection pool configuration
POOL_MIN_SIZE: int = int(os.getenv('DB_POOL_MIN_SIZE', '5'))
POOL_MAX_SIZE: int = int(os.getenv('DB_POOL_MAX_SIZE', '20'))
CONNECTION_TIMEOUT: int = int(os.getenv('DB_CONNECTION_TIMEOUT', '30'))
QUERY_TIMEOUT: int = int(os.getenv('DB_QUERY_TIMEOUT', '30'))

# SQL for creating tables
CREATE_TABLES_SQL = """
-- Create extensions (required for text search)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create chats table
CREATE TABLE IF NOT EXISTS chats (
    chat_id BIGINT PRIMARY KEY,
    chat_type VARCHAR(50) NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    username TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    internal_message_id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL REFERENCES chats(chat_id),
    user_id BIGINT REFERENCES users(user_id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    text TEXT,
    is_command BOOLEAN DEFAULT FALSE,
    command_name VARCHAR(255),
    is_gpt_reply BOOLEAN DEFAULT FALSE,
    replied_to_message_id BIGINT,
    gpt_context_message_ids JSONB,
    raw_telegram_message JSONB,
    UNIQUE(chat_id, message_id)
);

-- Create analysis_cache table
CREATE TABLE IF NOT EXISTS analysis_cache (
    chat_id BIGINT NOT NULL,
    time_period TEXT NOT NULL,
    message_content_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (chat_id, time_period, message_content_hash)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_is_command ON messages(is_command);
CREATE INDEX IF NOT EXISTS idx_messages_is_gpt_reply ON messages(is_gpt_reply);

-- Text search indexes for /count command optimization
CREATE INDEX IF NOT EXISTS idx_messages_text_gin ON messages USING GIN(text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_messages_text_search ON messages USING GIN(to_tsvector('english', text));

-- Composite index for faster chat-specific text searches
CREATE INDEX IF NOT EXISTS idx_messages_chat_text ON messages(chat_id) WHERE text IS NOT NULL;
"""

class DatabaseConnectionManager:
    """Enhanced database connection manager with optimized pooling."""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._pool_lock: asyncio.Lock = asyncio.Lock()
        self._cache_manager: CacheManager[Any] = CacheManager(default_ttl=DEFAULT_CACHE_TTL)
        self._performance_monitor: PerformanceMonitor = PerformanceMonitor()
        self._retry_manager: RetryManager = RetryManager(max_retries=DATABASE_RETRY_ATTEMPTS)
        self._connection_stats: Dict[str, int] = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    async def get_pool(self) -> asyncpg.Pool:
        """Get database connection pool with enhanced configuration."""
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    try:
                        self._pool = await asyncpg.create_pool(
                            host=DB_HOST,
                            port=int(DB_PORT),
                            database=DB_NAME,
                            user=DB_USER,
                            password=DB_PASSWORD,
                            min_size=POOL_MIN_SIZE,
                            max_size=POOL_MAX_SIZE,
                            command_timeout=QUERY_TIMEOUT,
                            server_settings={
                                'application_name': 'psychochauffeur_bot_v2',
                                'jit': 'off',
                                'shared_preload_libraries': 'pg_stat_statements',
                                'log_statement': 'none',
                                'log_min_duration_statement': '1000'  # Log slow queries
                            },
                            init=self._init_connection
                        )
                        self._connection_stats['total_connections'] += 1
                        logger.info(f"Database pool created with {POOL_MIN_SIZE}-{POOL_MAX_SIZE} connections")
                    except Exception as e:
                        self._connection_stats['failed_connections'] += 1
                        logger.error(f"Failed to create database pool: {e}")
                        raise
        return self._pool
    
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize connection with optimizations."""
        # Set connection-level optimizations
        await conn.execute("SET synchronous_commit = off")  # Faster writes for non-critical data
        await conn.execute("SET wal_buffers = '16MB'")
        await conn.execute("SET checkpoint_completion_target = 0.9")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for database connections with monitoring."""
        pool = await self.get_pool()
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with pool.acquire() as conn:
                self._connection_stats['active_connections'] += 1
                yield conn
        finally:
            self._connection_stats['active_connections'] -= 1
            duration = asyncio.get_event_loop().time() - start_time
            self._performance_monitor.record_metric(
                name="database_connection_duration",
                value=duration,
                unit="seconds"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            **self._connection_stats,
            'pool_size': self._pool.get_size() if self._pool else 0,
            'pool_free_size': self._pool.get_idle_size() if self._pool else 0,
            'cache_size': len(self._cache_manager._cache)
        }
    
    async def close(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")


class Database:
    """Enhanced database class with optimizations and caching."""
    
    _connection_manager: Optional[DatabaseConnectionManager] = None
    
    @classmethod
    def get_connection_manager(cls) -> DatabaseConnectionManager:
        """Get the database connection manager singleton."""
        if cls._connection_manager is None:
            cls._connection_manager = DatabaseConnectionManager()
        return cls._connection_manager
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get database connection pool."""
        manager = cls.get_connection_manager()
        return await manager.get_pool()

    @classmethod
    @database_operation("initialize_database")
    async def initialize(cls) -> None:
        """Initialize the database by creating tables if they don't exist."""
        manager = cls.get_connection_manager()
        async with manager.get_connection() as conn:
            await conn.execute(CREATE_TABLES_SQL)
            logger.info("Database tables initialized successfully")

    @classmethod
    @database_operation("save_chat_info")
    async def save_chat_info(cls, chat: Chat) -> None:
        """Save or update chat information with caching."""
        manager = cls.get_connection_manager()
        cache_key = f"chat:{chat.id}"
        
        # Check cache first
        cached_chat = manager._cache_manager.get(cache_key)
        if cached_chat and cached_chat.get('title') == chat.title:
            manager._connection_stats['cache_hits'] += 1
            return
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = $2, title = $3
            """, chat.id, chat.type, chat.title)
            
            # Cache the chat info
            manager._cache_manager.set(cache_key, {
                'id': chat.id,
                'type': chat.type,
                'title': chat.title
            }, ttl=3600)  # Cache for 1 hour
            
            manager._connection_stats['queries_executed'] += 1

    @classmethod
    @database_operation("save_user_info")
    async def save_user_info(cls, user: User) -> None:
        """Save or update user information with caching."""
        manager = cls.get_connection_manager()
        cache_key = f"user:{user.id}"
        
        # Check cache first
        cached_user = manager._cache_manager.get(cache_key)
        if (cached_user and 
            cached_user.get('username') == user.username and
            cached_user.get('first_name') == user.first_name):
            manager._connection_stats['cache_hits'] += 1
            return
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE
                SET first_name = $2, last_name = $3, username = $4, is_bot = $5
            """, user.id, user.first_name, user.last_name, user.username, user.is_bot)
            
            # Cache the user info
            manager._cache_manager.set(cache_key, {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'is_bot': user.is_bot
            }, ttl=3600)  # Cache for 1 hour
            
            manager._connection_stats['queries_executed'] += 1

    @classmethod
    @database_operation("save_message")
    async def save_message(
        cls,
        message: Message,
        is_gpt_reply: bool = False,
        gpt_context_message_ids: Optional[List[int]] = None
    ) -> None:
        """Save a message and its associated chat and user information with optimizations."""
        manager = cls.get_connection_manager()
        
        # First save chat and user info (these methods now have caching)
        await cls.save_chat_info(message.chat)
        if message.from_user:
            await cls.save_user_info(message.from_user)

        # Extract command information
        is_command: bool = bool(message.text and message.text.startswith('/'))
        command_name: Optional[str] = message.text.split()[0][1:] if is_command else None

        # Get reply information
        replied_to_message_id: Optional[MessageId] = (
            message.reply_to_message.message_id if message.reply_to_message else None
        )

        # Convert the entire message object to JSON
        raw_message: JSONDict = message.to_dict()

        async with manager.get_connection() as conn:
            await conn.execute("""
                INSERT INTO messages (
                    message_id, chat_id, user_id, timestamp, text,
                    is_command, command_name, is_gpt_reply,
                    replied_to_message_id, gpt_context_message_ids,
                    raw_telegram_message
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (chat_id, message_id) DO NOTHING
            """,
                message.message_id,
                message.chat.id,
                message.from_user.id if message.from_user else None,
                message.date,
                message.text,
                is_command,
                command_name,
                is_gpt_reply,
                replied_to_message_id,
                json.dumps(gpt_context_message_ids) if gpt_context_message_ids else None,
                json.dumps(raw_message)
            )
            manager._connection_stats['queries_executed'] += 1

    @classmethod
    @database_operation("save_image_analysis")
    async def save_image_analysis_as_message(
        cls,
        original_message: Message,
        description: str,
    ) -> None:
        """Saves an image description as a new message entry in the database."""
        manager = cls.get_connection_manager()

        # Get the bot's own User object via get_me() and save it to the users table.
        ext_bot = original_message.get_bot()
        bot_user = await ext_bot.get_me()
        await cls.save_user_info(bot_user)
        
        bot_user_id: UserId = bot_user.id
        chat_id: ChatId = original_message.chat.id
        
        async with manager.get_connection() as conn:
            # We use ON CONFLICT...DO UPDATE because the original message from the user
            # already exists. We are overwriting it with the bot's analysis.
            # This is a simplification. A better approach might be a separate table
            # for metadata or using a new message_id.
            await conn.execute("""
                INSERT INTO messages (
                    message_id, chat_id, user_id, timestamp, text,
                    is_command, command_name, is_gpt_reply,
                    replied_to_message_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (chat_id, message_id) DO UPDATE SET
                text = EXCLUDED.text,
                user_id = EXCLUDED.user_id,
                is_gpt_reply = TRUE,
                timestamp = EXCLUDED.timestamp
            """,
                original_message.message_id,
                chat_id,
                bot_user_id,
                datetime.now(pytz.utc), # Use timezone-aware datetime
                f"[IMAGE ANALYSIS]: {description}",
                False, # is_command
                None,  # command_name
                True,  # is_gpt_reply
                original_message.message_id
            )
            manager._connection_stats['queries_executed'] += 1

    @classmethod
    @database_operation("get_analysis_cache")
    async def get_analysis_cache(
        cls, 
        chat_id: ChatId, 
        time_period: str, 
        message_content_hash: str, 
        ttl_seconds: int
    ) -> Optional[str]:
        """Fetch cached analysis result if not expired with enhanced caching."""
        manager = cls.get_connection_manager()
        
        # Check in-memory cache first
        cache_key = f"analysis:{chat_id}:{time_period}:{message_content_hash}"
        cached_result = manager._cache_manager.get(cache_key)
        if cached_result:
            manager._connection_stats['cache_hits'] += 1
            return cached_result
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT result, created_at FROM analysis_cache
                WHERE chat_id = $1 AND time_period = $2 AND message_content_hash = $3
                """,
                chat_id, time_period, message_content_hash
            )
            if row:
                now = datetime.now(pytz.utc)
                if (now - row["created_at"]).total_seconds() < ttl_seconds:
                    # Cache in memory for faster subsequent access
                    remaining_ttl = ttl_seconds - int((now - row["created_at"]).total_seconds())
                    manager._cache_manager.set(cache_key, row["result"], ttl=remaining_ttl)
                    manager._connection_stats['queries_executed'] += 1
                    return row["result"]
        return None

    @classmethod
    @database_operation("set_analysis_cache")
    async def set_analysis_cache(
        cls, 
        chat_id: ChatId, 
        time_period: str, 
        message_content_hash: str, 
        result: str
    ) -> None:
        """Store analysis result in cache with dual-layer caching."""
        manager = cls.get_connection_manager()
        
        async with manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO analysis_cache (chat_id, time_period, message_content_hash, result, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (chat_id, time_period, message_content_hash)
                DO UPDATE SET result = EXCLUDED.result, created_at = EXCLUDED.created_at
                """,
                chat_id, time_period, message_content_hash, result
            )
            
            # Also cache in memory
            cache_key = f"analysis:{chat_id}:{time_period}:{message_content_hash}"
            manager._cache_manager.set(cache_key, result, ttl=DEFAULT_CACHE_TTL)
            manager._connection_stats['queries_executed'] += 1

    @classmethod
    @database_operation("invalidate_analysis_cache")
    async def invalidate_analysis_cache(
        cls, 
        chat_id: ChatId, 
        time_period: Optional[str] = None
    ) -> None:
        """Invalidate cache for a chat (optionally for a specific period)."""
        manager = cls.get_connection_manager()
        
        async with manager.get_connection() as conn:
            if time_period:
                await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1 AND time_period = $2",
                    chat_id, time_period
                )
                # Clear specific in-memory cache entries
                cache_pattern = f"analysis:{chat_id}:{time_period}:"
                keys_to_delete = [k for k in manager._cache_manager._cache.keys() 
                                if k.startswith(cache_pattern)]
                for key in keys_to_delete:
                    manager._cache_manager.delete(key)
            else:
                await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1",
                    chat_id
                )
                # Clear all analysis cache entries for this chat
                cache_pattern = f"analysis:{chat_id}:"
                keys_to_delete = [k for k in manager._cache_manager._cache.keys() 
                                if k.startswith(cache_pattern)]
                for key in keys_to_delete:
                    manager._cache_manager.delete(key)
            
            manager._connection_stats['queries_executed'] += 1

    # New optimized query methods
    @classmethod
    @database_operation("get_recent_messages")
    async def get_recent_messages(
        cls,
        chat_id: ChatId,
        limit: int = 50,
        include_commands: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a chat with optimized query."""
        manager = cls.get_connection_manager()
        
        cache_key = f"recent_messages:{chat_id}:{limit}:{include_commands}"
        cached_messages = manager._cache_manager.get(cache_key)
        if cached_messages:
            manager._connection_stats['cache_hits'] += 1
            return cached_messages
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            query = """
                SELECT message_id, user_id, timestamp, text, is_command, command_name, is_gpt_reply
                FROM messages 
                WHERE chat_id = $1
            """
            params = [chat_id]
            
            if not include_commands:
                query += " AND is_command = FALSE"
            
            query += " ORDER BY timestamp DESC LIMIT $2"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            messages = [dict(row) for row in rows]
            
            # Cache for 5 minutes
            manager._cache_manager.set(cache_key, messages, ttl=300)
            manager._connection_stats['queries_executed'] += 1
            
            return messages

    @classmethod
    @database_operation("get_message_count")
    async def get_message_count(
        cls,
        chat_id: ChatId,
        user_id: Optional[UserId] = None,
        since: Optional[datetime] = None,
        text_filter: Optional[str] = None
    ) -> int:
        """Get message count with various filters and caching."""
        manager = cls.get_connection_manager()
        
        cache_key = f"msg_count:{chat_id}:{user_id}:{since}:{text_filter}"
        cached_count = manager._cache_manager.get(cache_key)
        if cached_count is not None:
            manager._connection_stats['cache_hits'] += 1
            return cached_count
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            query = "SELECT COUNT(*) FROM messages WHERE chat_id = $1"
            params = [chat_id]
            param_count = 1
            
            if user_id:
                param_count += 1
                query += f" AND user_id = ${param_count}"
                params.append(user_id)
            
            if since:
                param_count += 1
                query += f" AND timestamp >= ${param_count}"
                params.append(since)
            
            if text_filter:
                param_count += 1
                # Use GIN index for text search
                query += f" AND text ILIKE ${param_count}"
                params.append(f"%{text_filter}%")
            
            count = await conn.fetchval(query, *params)
            
            # Cache for 2 minutes
            manager._cache_manager.set(cache_key, count, ttl=120)
            manager._connection_stats['queries_executed'] += 1
            
            return count

    @classmethod
    @database_operation("cleanup_old_cache")
    async def cleanup_old_cache(cls, days_old: int = 7) -> int:
        """Clean up old cache entries and return count of deleted rows."""
        manager = cls.get_connection_manager()
        
        async with manager.get_connection() as conn:
            cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_old)
            
            deleted_count = await conn.fetchval(
                "DELETE FROM analysis_cache WHERE created_at < $1 RETURNING COUNT(*)",
                cutoff_date
            )
            
            # Also cleanup in-memory cache
            manager._cache_manager.cleanup_expired()
            
            manager._connection_stats['queries_executed'] += 1
            logger.info(f"Cleaned up {deleted_count} old cache entries")
            
            return deleted_count

    @classmethod
    async def get_database_stats(cls) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        manager = cls.get_connection_manager()
        
        async with manager.get_connection() as conn:
            # Get table sizes
            table_stats = await conn.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats 
                WHERE schemaname = 'public' 
                AND tablename IN ('messages', 'chats', 'users', 'analysis_cache')
            """)
            
            # Get connection pool stats
            connection_stats = manager.get_stats()
            
            return {
                'connection_stats': connection_stats,
                'table_stats': [dict(row) for row in table_stats],
                'performance_metrics': manager._performance_monitor.get_metrics()
            }

    @classmethod
    async def close(cls) -> None:
        """Close the database connection pool."""
        if cls._connection_manager:
            await cls._connection_manager.close()
            cls._connection_manager = None