import os
import json
from typing import Optional, List, Dict, Any
import asyncpg
from datetime import datetime
from telegram import Chat, User, Message
from dotenv import load_dotenv

load_dotenv()

# Database connection configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# SQL for creating tables
CREATE_TABLES_SQL = """
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_is_command ON messages(is_command);
CREATE INDEX IF NOT EXISTS idx_messages_is_gpt_reply ON messages(is_gpt_reply);
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
    async def close(cls):
        """Close the database connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None 