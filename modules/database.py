import os
import json
from typing import Optional, List, Dict, Any
import asyncpg
from datetime import datetime
from telegram import Chat, User, Message
from dotenv import load_dotenv
import pytz

load_dotenv()

# Database connection configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

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

class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=5,
                max_size=20
            )
        return cls._pool

    @classmethod
    async def initialize(cls):
        """Initialize the database by creating tables if they don't exist."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)

    @classmethod
    async def save_chat_info(cls, chat: Chat) -> None:
        """Save or update chat information."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = $2, title = $3
            """, chat.id, chat.type, chat.title)

    @classmethod
    async def save_user_info(cls, user: User) -> None:
        """Save or update user information."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE
                SET first_name = $2, last_name = $3, username = $4, is_bot = $5
            """, user.id, user.first_name, user.last_name, user.username, user.is_bot)

    @classmethod
    async def save_message(
        cls,
        message: Message,
        is_gpt_reply: bool = False,
        gpt_context_message_ids: Optional[List[int]] = None
    ) -> None:
        """Save a message and its associated chat and user information."""
        pool = await cls.get_pool()
        
        # First save chat and user info
        await cls.save_chat_info(message.chat)
        if message.from_user:
            await cls.save_user_info(message.from_user)

        # Extract command information
        is_command = bool(message.text and message.text.startswith('/'))
        command_name = message.text.split()[0][1:] if is_command else None

        # Get reply information
        replied_to_message_id = message.reply_to_message.message_id if message.reply_to_message else None

        # Convert the entire message object to JSON
        raw_message = message.to_dict()

        async with pool.acquire() as conn:
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

    @classmethod
    async def save_image_analysis_as_message(
        cls,
        original_message: Message,
        description: str,
    ) -> None:
        """Saves an image description as a new message entry in the database."""
        pool = await cls.get_pool()

        # Get the bot's own User object via get_me() and save it to the users table.
        ext_bot = original_message.get_bot()
        bot_user = await ext_bot.get_me()
        await cls.save_user_info(bot_user)
        
        bot_user_id = bot_user.id
        chat_id = original_message.chat.id
        
        async with pool.acquire() as conn:
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

    @classmethod
    async def get_analysis_cache(cls, chat_id: int, time_period: str, message_content_hash: str, ttl_seconds: int) -> Optional[str]:
        """Fetch cached analysis result if not expired."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT result, created_at FROM analysis_cache
                WHERE chat_id = $1 AND time_period = $2 AND message_content_hash = $3
                """,
                chat_id, time_period, message_content_hash
            )
            if row:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if (now - row["created_at"]).total_seconds() < ttl_seconds:
                    return row["result"]
        return None

    @classmethod
    async def set_analysis_cache(cls, chat_id: int, time_period: str, message_content_hash: str, result: str):
        """Store analysis result in cache."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis_cache (chat_id, time_period, message_content_hash, result, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (chat_id, time_period, message_content_hash)
                DO UPDATE SET result = EXCLUDED.result, created_at = EXCLUDED.created_at
                """,
                chat_id, time_period, message_content_hash, result
            )

    @classmethod
    async def invalidate_analysis_cache(cls, chat_id: int, time_period: Optional[str] = None):
        """Invalidate cache for a chat (optionally for a specific period)."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            if time_period:
                await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1 AND time_period = $2",
                    chat_id, time_period
                )
            else:
                await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1",
                    chat_id
                )

    @classmethod
    async def close(cls):
        """Close the database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None