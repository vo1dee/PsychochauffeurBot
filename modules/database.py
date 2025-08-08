import os
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
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
# Support both DATABASE_URL and individual environment variables
DATABASE_URL = os.getenv('DATABASE_URL')

# Database connection parameters
if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    # Parse DATABASE_URL for PostgreSQL
    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)
    DB_HOST = parsed.hostname or 'localhost'
    DB_PORT = str(parsed.port or 5432)
    DB_NAME = parsed.path.lstrip('/') or 'telegram_bot'
    DB_USER = parsed.username or 'postgres'
    DB_PASSWORD = parsed.password or ''
else:
    # Use individual environment variables
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

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

# Note: Using the imported database_operation decorator from modules.error_decorators
# The duplicate definition has been removed

class DatabaseConnectionManager:
    """Enhanced database connection manager with optimized pooling."""
    
    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        self._pool_lock: asyncio.Lock = asyncio.Lock()
        self._cache_manager: CacheManager[Any] = CacheManager(default_ttl=DEFAULT_CACHE_TTL)
        # Import PerformanceMonitor from shared_utilities to avoid untyped call
        from modules.shared_utilities import PerformanceMonitor
        self._performance_monitor: PerformanceMonitor = PerformanceMonitor()
        self._retry_manager: RetryManager = RetryManager(max_retries=DATABASE_RETRY_ATTEMPTS)
        self._connection_stats: Dict[str, int] = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'connection_retries': 0,
            'health_checks': 0,
            'health_check_failures': 0
        }
        self._last_health_check: Optional[datetime] = None
        self._health_check_result: bool = False
    
    async def get_pool(self) -> asyncpg.Pool:
        """Get database connection pool with enhanced configuration and retry logic."""
        if self._pool is None:
            async with self._pool_lock:
                if self._pool is None:
                    await self._create_pool_with_retry()
        return self._pool
    
    async def _create_pool_with_retry(self) -> None:
        """Create database pool with retry logic and exponential backoff."""
        async def _create_pool() -> None:
            try:
                # Default server settings for the connection pool
                server_settings = {
                    'application_name': 'PsychochauffeurBot',
                    'search_path': 'public',
                }
                
                logger.info(f"Attempting to create database pool (host={DB_HOST}, port={DB_PORT}, db={DB_NAME})")
                
                self._pool = await asyncpg.create_pool(
                    host=DB_HOST,
                    port=int(DB_PORT),
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    min_size=POOL_MIN_SIZE,
                    max_size=POOL_MAX_SIZE,
                    command_timeout=QUERY_TIMEOUT,
                    server_settings=server_settings,
                    init=self._init_connection
                )
                
                self._connection_stats['total_connections'] += 1
                logger.info(f"Database pool created successfully with {POOL_MIN_SIZE}-{POOL_MAX_SIZE} connections")
                
                # Perform initial health check
                await self._perform_health_check()
                
            except Exception as e:
                self._connection_stats['failed_connections'] += 1
                logger.error(f"Failed to create database pool: {e}")
                logger.error(f"Connection details - Host: {DB_HOST}, Port: {DB_PORT}, Database: {DB_NAME}, User: {DB_USER}")
                raise
        
        try:
            await self._retry_manager.execute(_create_pool)
        except Exception as e:
            logger.critical(f"Failed to create database pool after {DATABASE_RETRY_ATTEMPTS} attempts: {e}")
            raise
    
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize connection with optimizations."""
        # Set connection-level optimizations
        await conn.execute("SET synchronous_commit = off")  # Faster writes for non-critical data
        # Remove invalid runtime parameter change for wal_buffers
        # await conn.execute("SET wal_buffers = '16MB'")
        # await conn.execute("SET checkpoint_completion_target = 0.9")
    
    @asynccontextmanager
    async def get_connection(self) -> Any:
        """Context manager for database connections with enhanced monitoring and error handling."""
        start_time = asyncio.get_event_loop().time()
        connection_acquired = False
        
        try:
            # Get pool with retry logic
            pool = await self.get_pool_with_retry()
            
            async with pool.acquire() as conn:
                connection_acquired = True
                self._connection_stats['active_connections'] += 1
                logger.debug(f"Database connection acquired (active: {self._connection_stats['active_connections']})")
                yield conn
                
        except asyncpg.PostgresError as e:
            self._connection_stats['failed_connections'] += 1
            logger.error(f"PostgreSQL error in connection context: {e}")
            logger.error(f"Error code: {e.sqlstate}, Severity: {getattr(e, 'severity', 'unknown')}")
            raise
        except asyncio.TimeoutError as e:
            self._connection_stats['failed_connections'] += 1
            logger.error(f"Database connection timeout: {e}")
            raise
        except Exception as e:
            self._connection_stats['failed_connections'] += 1
            logger.error(f"Unexpected error in database connection context: {e}")
            raise
        finally:
            if connection_acquired:
                self._connection_stats['active_connections'] -= 1
                logger.debug(f"Database connection released (active: {self._connection_stats['active_connections']})")
            
            duration = asyncio.get_event_loop().time() - start_time
            self._performance_monitor.record_metric(
                name="database_connection_duration",
                value=duration,
                unit="seconds"
            )
            
            # Log slow connections
            if duration > 1.0:
                logger.warning(f"Slow database connection: {duration:.3f}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            **self._connection_stats,
            'pool_size': self._pool.get_size() if self._pool else 0,
            'pool_free_size': self._pool.get_idle_size() if self._pool else 0,
            'cache_size': len(self._cache_manager._cache)
        }
    
    async def _perform_health_check(self) -> bool:
        """Perform database health check."""
        if not self._pool:
            return False
        
        try:
            async with self._pool.acquire() as conn:
                # Simple query to test connection
                await conn.fetchval("SELECT 1")
                self._health_check_result = True
                self._last_health_check = datetime.now(pytz.utc)
                self._connection_stats['health_checks'] += 1
                logger.debug("Database health check passed")
                return True
        except Exception as e:
            self._health_check_result = False
            self._connection_stats['health_check_failures'] += 1
            logger.warning(f"Database health check failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check database connectivity with caching."""
        # Return cached result if recent (within 30 seconds)
        if (self._last_health_check and 
            (datetime.now(pytz.utc) - self._last_health_check).total_seconds() < 30):
            return self._health_check_result
        
        return await self._perform_health_check()
    
    async def get_pool_with_retry(self, max_retries: int = 3) -> asyncpg.Pool:
        """Get database pool with retry logic for connection failures."""
        retry_manager = RetryManager(max_retries=max_retries, base_delay=1.0, max_delay=10.0)
        
        async def _get_pool_attempt() -> asyncpg.Pool:
            pool = await self.get_pool()
            
            # Verify pool health
            if not await self.health_check():
                self._connection_stats['connection_retries'] += 1
                logger.warning("Database pool health check failed, attempting recovery")
                
                # Try to recreate pool if health check fails
                if self._pool:
                    try:
                        await self._pool.close()
                    except Exception as e:
                        logger.warning(f"Error closing unhealthy pool: {e}")
                    finally:
                        self._pool = None
                
                # Recreate pool
                await self._create_pool_with_retry()
                pool = self._pool
                
                if not pool:
                    raise Exception("Failed to recreate database pool")
            
            return pool
        
        try:
            return await retry_manager.execute(_get_pool_attempt)
        except Exception as e:
            logger.error(f"Failed to get healthy database pool after {max_retries} retries: {e}")
            raise
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed connection statistics and diagnostics."""
        pool_stats = {}
        if self._pool:
            pool_stats = {
                'pool_size': self._pool.get_size(),
                'pool_free_size': self._pool.get_idle_size(),
                'pool_max_size': POOL_MAX_SIZE,
                'pool_min_size': POOL_MIN_SIZE,
            }
        
        return {
            **self._connection_stats,
            **pool_stats,
            'cache_size': len(self._cache_manager._cache),
            'last_health_check': self._last_health_check.isoformat() if self._last_health_check else None,
            'health_check_result': self._health_check_result,
            'connection_config': {
                'host': DB_HOST,
                'port': DB_PORT,
                'database': DB_NAME,
                'user': DB_USER,
                'connection_timeout': CONNECTION_TIMEOUT,
                'query_timeout': QUERY_TIMEOUT,
            },
            'performance_metrics': self._performance_monitor.get_metrics()
        }
    
    async def close(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            try:
                await self._pool.close()
                logger.info("Database pool closed successfully")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}")
            finally:
                self._pool = None
                self._health_check_result = False
                self._last_health_check = None


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
    async def health_check(cls) -> bool:
        """Check database connectivity."""
        try:
            manager = cls.get_connection_manager()
            return await manager.health_check()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @classmethod
    async def get_pool_with_retry(cls, max_retries: int = 3) -> asyncpg.Pool:
        """Get database pool with retry logic for connection failures."""
        manager = cls.get_connection_manager()
        return await manager.get_pool_with_retry(max_retries)

    @classmethod
    @database_operation("initialize_database")
    async def initialize(cls) -> None:
        """Initialize the database by creating tables if they don't exist."""
        manager = cls.get_connection_manager()
        async with manager.get_connection() as conn:
            await conn.execute(CREATE_TABLES_SQL)
            logger.info("Database tables initialized successfully")

    @classmethod
    @database_operation("save_chat_info", raise_exception=True)
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
        
        try:
            # First save chat and user info (these methods now have caching)
            await cls.save_chat_info(message.chat)
            if message.from_user:
                await cls.save_user_info(message.from_user)

            # Extract command information
            is_command: bool = bool(message.text and message.text.startswith('/'))
            command_name: Optional[str] = message.text.split()[0][1:] if (message.text and message.text.startswith('/')) else None

            # Get reply information
            replied_to_message_id: Optional[MessageId] = (
                message.reply_to_message.message_id if (message.reply_to_message is not None) else None
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
                logger.debug(f"Message saved successfully: chat_id={message.chat.id}, message_id={message.message_id}")
                
        except Exception as e:
            logger.error(f"Failed to save message: chat_id={message.chat.id}, message_id={message.message_id}, error={e}")
            raise

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
        if cached_result is not None:
            manager._connection_stats['cache_hits'] += 1
            return str(cached_result)
        
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
                    remaining_ttl = ttl_seconds - int((now - row["created_at"]).total_seconds())
                    manager._cache_manager.set(cache_key, row["result"], ttl=remaining_ttl)
                    manager._connection_stats['queries_executed'] += 1
                    return str(row["result"])
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
        if cached_messages is not None:
            manager._connection_stats['cache_hits'] += 1
            return list(cached_messages)
        
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
            return int(cached_count)
        
        manager._connection_stats['cache_misses'] += 1
        async with manager.get_connection() as conn:
            query = "SELECT COUNT(*) FROM messages WHERE chat_id = $1"
            params: List[Any] = [chat_id]
            param_count = 1
            
            if user_id:
                param_count += 1
                query += f" AND user_id = ${param_count}"
                params.append(user_id)
            
            if since:
                param_count += 1
                query += f" AND timestamp >= ${param_count}"
                params.append(since)  # datetime is acceptable for asyncpg
            
            if text_filter:
                param_count += 1
                # Use GIN index for text search
                query += f" AND text ILIKE ${param_count}"
                params.append(f"%{text_filter}%")  # string is acceptable for asyncpg
            
            count = await conn.fetchval(query, *params)
            
            # Cache for 2 minutes
            manager._cache_manager.set(cache_key, count, ttl=120)
            manager._connection_stats['queries_executed'] += 1
            
            return int(count)

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
            
            return int(deleted_count)

    @classmethod
    async def get_database_stats(cls) -> Dict[str, Any]:
        """Get comprehensive database statistics with enhanced diagnostics."""
        manager = cls.get_connection_manager()
        
        try:
            # Get detailed connection stats first
            detailed_stats = manager.get_detailed_stats()
            
            # Try to get database-specific stats
            database_stats = {}
            try:
                async with manager.get_connection() as conn:
                    # Get table sizes and statistics
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
                    
                    # Get database size information
                    db_size_info = await conn.fetchrow("""
                        SELECT 
                            pg_database_size(current_database()) as database_size,
                            current_database() as database_name
                    """)
                    
                    # Get active connections count
                    active_connections = await conn.fetchval("""
                        SELECT count(*) 
                        FROM pg_stat_activity 
                        WHERE datname = current_database()
                    """)
                    
                    database_stats = {
                        'table_stats': [dict(row) for row in table_stats],
                        'database_size': dict(db_size_info) if db_size_info else {},
                        'active_db_connections': active_connections
                    }
                    
            except Exception as e:
                logger.warning(f"Could not retrieve database-specific stats: {e}")
                database_stats = {'error': str(e)}
            
            return {
                'connection_diagnostics': detailed_stats,
                'database_stats': database_stats,
                'health_status': await cls.health_check()
            }
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {
                'error': str(e),
                'health_status': False,
                'connection_diagnostics': manager.get_detailed_stats() if manager else {}
            }

    @classmethod
    async def diagnose_connection_issues(cls) -> Dict[str, Any]:
        """Diagnose database connection issues and provide troubleshooting information."""
        diagnostics: Dict[str, Any] = {
            'timestamp': datetime.now(pytz.utc).isoformat(),
            'connection_config': {
                'host': DB_HOST,
                'port': DB_PORT,
                'database': DB_NAME,
                'user': DB_USER,
                'pool_min_size': POOL_MIN_SIZE,
                'pool_max_size': POOL_MAX_SIZE,
                'connection_timeout': CONNECTION_TIMEOUT,
                'query_timeout': QUERY_TIMEOUT,
            },
            'tests': {}
        }
        
        # Test 1: Basic connectivity
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((DB_HOST, int(DB_PORT)))
            sock.close()
            diagnostics['tests']['network_connectivity'] = {
                'status': 'success' if result == 0 else 'failed',
                'details': f"Connection to {DB_HOST}:{DB_PORT} {'successful' if result == 0 else 'failed'}"
            }
        except Exception as e:
            diagnostics['tests']['network_connectivity'] = {
                'status': 'error',
                'details': f"Network test error: {e}"
            }
        
        # Test 2: Database pool health
        try:
            health_status = await cls.health_check()
            diagnostics['tests']['database_health'] = {
                'status': 'success' if health_status else 'failed',
                'details': f"Database health check {'passed' if health_status else 'failed'}"
            }
        except Exception as e:
            diagnostics['tests']['database_health'] = {
                'status': 'error',
                'details': f"Health check error: {e}"
            }
        
        # Test 3: Connection statistics
        try:
            manager = cls.get_connection_manager()
            stats = manager.get_detailed_stats()
            diagnostics['tests']['connection_stats'] = {
                'status': 'success',
                'details': stats
            }
        except Exception as e:
            diagnostics['tests']['connection_stats'] = {
                'status': 'error',
                'details': f"Stats collection error: {e}"
            }
        
        # Test 4: Simple query test
        try:
            async with cls.get_connection_manager().get_connection() as conn:
                result = await conn.fetchval("SELECT version()")
                diagnostics['tests']['query_test'] = {
                    'status': 'success',
                    'details': f"PostgreSQL version: {result}"
                }
        except Exception as e:
            diagnostics['tests']['query_test'] = {
                'status': 'error',
                'details': f"Query test error: {e}"
            }
        
        return diagnostics
    
    @classmethod
    async def close(cls) -> None:
        """Close the database connection pool."""
        if cls._connection_manager:
            await cls._connection_manager.close()
            cls._connection_manager = None