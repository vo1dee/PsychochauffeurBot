"""
Repository Pattern Implementation

This module provides data access abstraction using the Repository pattern
for clean separation between business logic and data persistence.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic, Union, Tuple
import json

from telegram import Chat, User, Message
from modules.database import Database

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Repository(ABC, Generic[T]):
    """Abstract base repository interface."""
    
    @abstractmethod
    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save entity."""
        pass
    
    @abstractmethod
    async def delete(self, id: Any) -> bool:
        """Delete entity by ID."""
        pass
    
    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Find all entities with pagination."""
        pass
    
    @abstractmethod
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Find entities by criteria."""
        pass


@dataclass
class ChatEntity:
    """Chat entity model."""
    chat_id: int
    chat_type: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class UserEntity:
    """User entity model."""
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_bot: bool = False
    created_at: Optional[datetime] = None


@dataclass
class MessageEntity:
    """Message entity model."""
    internal_message_id: Optional[int] = None
    message_id: int = 0
    chat_id: int = 0
    user_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    text: Optional[str] = None
    is_command: bool = False
    command_name: Optional[str] = None
    is_gpt_reply: bool = False
    replied_to_message_id: Optional[int] = None
    gpt_context_message_ids: Optional[List[int]] = None
    raw_telegram_message: Optional[Dict[str, Any]] = None


@dataclass
class AnalysisCacheEntity:
    """Analysis cache entity model."""
    chat_id: int
    time_period: str
    message_content_hash: str
    result: str
    created_at: Optional[datetime] = None


class ChatRepository(Repository[ChatEntity]):
    """Repository for chat entities."""
    
    async def get_by_id(self, chat_id: int) -> Optional[ChatEntity]:
        """Get chat by ID."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chats WHERE chat_id = $1",
                chat_id
            )
            if row:
                return ChatEntity(
                    chat_id=row['chat_id'],
                    chat_type=row['chat_type'],
                    title=row['title'],
                    created_at=row['created_at']
                )
        return None
    
    async def save(self, entity: ChatEntity) -> ChatEntity:
        """Save chat entity."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = $2, title = $3
            """, entity.chat_id, entity.chat_type, entity.title)
        
        # Return the saved entity (fetch to get created_at if it was inserted)
        return await self.get_by_id(entity.chat_id) or entity
    
    async def delete(self, chat_id: int) -> bool:
        """Delete chat by ID."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chats WHERE chat_id = $1",
                chat_id
            )
            return result != "DELETE 0"  # type: ignore
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[ChatEntity]:
        """Find all chats with pagination."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM chats ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [
                ChatEntity(
                    chat_id=row['chat_id'],
                    chat_type=row['chat_type'],
                    title=row['title'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[ChatEntity]:
        """Find chats by criteria."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            where_clauses = []
            params = []
            param_count = 0
            
            for key, value in criteria.items():
                param_count += 1
                if key == 'chat_type':
                    where_clauses.append(f"chat_type = ${param_count}")
                    params.append(value)
                elif key == 'title_contains':
                    where_clauses.append(f"title ILIKE ${param_count}")
                    params.append(f"%{value}%")
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = f"SELECT * FROM chats WHERE {where_clause} ORDER BY created_at DESC"
            
            rows = await conn.fetch(query, *params)
            return [
                ChatEntity(
                    chat_id=row['chat_id'],
                    chat_type=row['chat_type'],
                    title=row['title'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def get_chat_statistics(self, chat_id: int) -> Dict[str, Any]:
        """Get statistics for a specific chat."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) FILTER (WHERE is_command = true) as command_count,
                    COUNT(*) FILTER (WHERE is_gpt_reply = true) as gpt_replies,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages 
                WHERE chat_id = $1
            """, chat_id)
            
            return dict(stats) if stats else {}


class UserRepository(Repository[UserEntity]):
    """Repository for user entities."""
    
    async def get_by_id(self, user_id: int) -> Optional[UserEntity]:
        """Get user by ID."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1",
                user_id
            )
            if row:
                return UserEntity(
                    user_id=row['user_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    is_bot=row['is_bot'],
                    created_at=row['created_at']
                )
        return None
    
    async def save(self, entity: UserEntity) -> UserEntity:
        """Save user entity."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, is_bot)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE
                SET first_name = $2, last_name = $3, username = $4, is_bot = $5
            """, entity.user_id, entity.first_name, entity.last_name, 
                entity.username, entity.is_bot)
        
        return await self.get_by_id(entity.user_id) or entity
    
    async def delete(self, user_id: int) -> bool:
        """Delete user by ID."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM users WHERE user_id = $1",
                user_id
            )
            return result != "DELETE 0"  # type: ignore
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[UserEntity]:
        """Find all users with pagination."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [
                UserEntity(
                    user_id=row['user_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    is_bot=row['is_bot'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[UserEntity]:
        """Find users by criteria."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            where_clauses = []
            params = []
            param_count = 0
            
            for key, value in criteria.items():
                param_count += 1
                if key == 'username':
                    where_clauses.append(f"username = ${param_count}")
                    params.append(value)
                elif key == 'is_bot':
                    where_clauses.append(f"is_bot = ${param_count}")
                    params.append(value)
                elif key == 'name_contains':
                    where_clauses.append(f"(first_name ILIKE ${param_count} OR last_name ILIKE ${param_count})")
                    params.append(f"%{value}%")
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = f"SELECT * FROM users WHERE {where_clause} ORDER BY created_at DESC"
            
            rows = await conn.fetch(query, *params)
            return [
                UserEntity(
                    user_id=row['user_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    is_bot=row['is_bot'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def get_user_activity_stats(self, user_id: int) -> Dict[str, Any]:
        """Get activity statistics for a user."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT chat_id) as chats_participated,
                    COUNT(*) FILTER (WHERE is_command = true) as commands_used,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages 
                WHERE user_id = $1
            """, user_id)
            
            return dict(stats) if stats else {}


class MessageRepository(Repository[MessageEntity]):
    """Repository for message entities."""
    
    async def get_by_id(self, message_id: Union[int, Tuple[int, int]]) -> Optional[MessageEntity]:
        """Get message by ID (can be internal_id or (chat_id, message_id) tuple)."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            if isinstance(message_id, tuple):
                chat_id, msg_id = message_id
                row = await conn.fetchrow(
                    "SELECT * FROM messages WHERE chat_id = $1 AND message_id = $2",
                    chat_id, msg_id
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM messages WHERE internal_message_id = $1",
                    message_id
                )
            
            if row:
                return self._row_to_entity(row)
        return None
    
    async def save(self, entity: MessageEntity) -> MessageEntity:
        """Save message entity."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO messages (
                    message_id, chat_id, user_id, timestamp, text,
                    is_command, command_name, is_gpt_reply,
                    replied_to_message_id, gpt_context_message_ids,
                    raw_telegram_message
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (chat_id, message_id) DO UPDATE SET
                text = EXCLUDED.text,
                user_id = EXCLUDED.user_id,
                timestamp = EXCLUDED.timestamp,
                is_command = EXCLUDED.is_command,
                command_name = EXCLUDED.command_name,
                is_gpt_reply = EXCLUDED.is_gpt_reply,
                replied_to_message_id = EXCLUDED.replied_to_message_id,
                gpt_context_message_ids = EXCLUDED.gpt_context_message_ids,
                raw_telegram_message = EXCLUDED.raw_telegram_message
            """,
                entity.message_id,
                entity.chat_id,
                entity.user_id,
                entity.timestamp,
                entity.text,
                entity.is_command,
                entity.command_name,
                entity.is_gpt_reply,
                entity.replied_to_message_id,
                json.dumps(entity.gpt_context_message_ids) if entity.gpt_context_message_ids else None,
                json.dumps(entity.raw_telegram_message) if entity.raw_telegram_message else None
            )
        
        return await self.get_by_id((entity.chat_id, entity.message_id)) or entity
    
    async def delete(self, message_id: Union[int, Tuple[int, int]]) -> bool:
        """Delete message by ID."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            if isinstance(message_id, tuple):
                chat_id, msg_id = message_id
                result = await conn.execute(
                    "DELETE FROM messages WHERE chat_id = $1 AND message_id = $2",
                    chat_id, msg_id
                )
            else:
                result = await conn.execute(
                    "DELETE FROM messages WHERE internal_message_id = $1",
                    message_id
                )
            return result != "DELETE 0"  # type: ignore
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[MessageEntity]:
        """Find all messages with pagination."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM messages ORDER BY timestamp DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [self._row_to_entity(row) for row in rows]
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[MessageEntity]:
        """Find messages by criteria."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            where_clauses = []
            params = []
            param_count = 0
            
            for key, value in criteria.items():
                param_count += 1
                if key == 'chat_id':
                    where_clauses.append(f"chat_id = ${param_count}")
                    params.append(value)
                elif key == 'user_id':
                    where_clauses.append(f"user_id = ${param_count}")
                    params.append(value)
                elif key == 'is_command':
                    where_clauses.append(f"is_command = ${param_count}")
                    params.append(value)
                elif key == 'is_gpt_reply':
                    where_clauses.append(f"is_gpt_reply = ${param_count}")
                    params.append(value)
                elif key == 'text_contains':
                    where_clauses.append(f"text ILIKE ${param_count}")
                    params.append(f"%{value}%")
                elif key == 'command_name':
                    where_clauses.append(f"command_name = ${param_count}")
                    params.append(value)
                elif key == 'date_from':
                    where_clauses.append(f"timestamp >= ${param_count}")
                    params.append(value)
                elif key == 'date_to':
                    where_clauses.append(f"timestamp <= ${param_count}")
                    params.append(value)
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = f"SELECT * FROM messages WHERE {where_clause} ORDER BY timestamp DESC"
            
            rows = await conn.fetch(query, *params)
            return [self._row_to_entity(row) for row in rows]
    
    async def get_chat_messages(self, chat_id: int, limit: int = 50, offset: int = 0) -> List[MessageEntity]:
        """Get messages for a specific chat."""
        return await self.find_by_criteria({'chat_id': chat_id})
    
    async def get_user_messages(self, user_id: int, limit: int = 50, offset: int = 0) -> List[MessageEntity]:
        """Get messages from a specific user."""
        return await self.find_by_criteria({'user_id': user_id})
    
    async def search_messages(self, chat_id: int, search_text: str, limit: int = 50) -> List[MessageEntity]:
        """Search messages by text content."""
        return await self.find_by_criteria({
            'chat_id': chat_id,
            'text_contains': search_text
        })
    
    def _row_to_entity(self, row: Any) -> MessageEntity:
        """Convert database row to MessageEntity."""
        gpt_context_ids = None
        if row['gpt_context_message_ids']:
            try:
                gpt_context_ids = json.loads(row['gpt_context_message_ids'])
            except json.JSONDecodeError:
                pass
        
        raw_message = None
        if row['raw_telegram_message']:
            try:
                raw_message = json.loads(row['raw_telegram_message'])
            except json.JSONDecodeError:
                pass
        
        return MessageEntity(
            internal_message_id=row['internal_message_id'],
            message_id=row['message_id'],
            chat_id=row['chat_id'],
            user_id=row['user_id'],
            timestamp=row['timestamp'],
            text=row['text'],
            is_command=row['is_command'],
            command_name=row['command_name'],
            is_gpt_reply=row['is_gpt_reply'],
            replied_to_message_id=row['replied_to_message_id'],
            gpt_context_message_ids=gpt_context_ids,
            raw_telegram_message=raw_message
        )


class AnalysisCacheRepository(Repository[AnalysisCacheEntity]):
    """Repository for analysis cache entities."""
    
    async def get_by_id(self, cache_key: Tuple[int, str, str]) -> Optional[AnalysisCacheEntity]:
        """Get cache entry by composite key (chat_id, time_period, hash)."""
        chat_id, time_period, message_hash = cache_key
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM analysis_cache WHERE chat_id = $1 AND time_period = $2 AND message_content_hash = $3",
                chat_id, time_period, message_hash
            )
            if row:
                return AnalysisCacheEntity(
                    chat_id=row['chat_id'],
                    time_period=row['time_period'],
                    message_content_hash=row['message_content_hash'],
                    result=row['result'],
                    created_at=row['created_at']
                )
        return None
    
    async def save(self, entity: AnalysisCacheEntity) -> AnalysisCacheEntity:
        """Save cache entity."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO analysis_cache (chat_id, time_period, message_content_hash, result, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (chat_id, time_period, message_content_hash)
                DO UPDATE SET result = EXCLUDED.result, created_at = EXCLUDED.created_at
            """, entity.chat_id, entity.time_period, entity.message_content_hash, entity.result)
        
        return await self.get_by_id((entity.chat_id, entity.time_period, entity.message_content_hash)) or entity
    
    async def delete(self, cache_key: Tuple[int, str, str]) -> bool:
        """Delete cache entry by key."""
        chat_id, time_period, message_hash = cache_key
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM analysis_cache WHERE chat_id = $1 AND time_period = $2 AND message_content_hash = $3",
                chat_id, time_period, message_hash
            )
            return result != "DELETE 0"  # type: ignore
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[AnalysisCacheEntity]:
        """Find all cache entries with pagination."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM analysis_cache ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [
                AnalysisCacheEntity(
                    chat_id=row['chat_id'],
                    time_period=row['time_period'],
                    message_content_hash=row['message_content_hash'],
                    result=row['result'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[AnalysisCacheEntity]:
        """Find cache entries by criteria."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            where_clauses = []
            params = []
            param_count = 0
            
            for key, value in criteria.items():
                param_count += 1
                if key == 'chat_id':
                    where_clauses.append(f"chat_id = ${param_count}")
                    params.append(value)
                elif key == 'time_period':
                    where_clauses.append(f"time_period = ${param_count}")
                    params.append(value)
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = f"SELECT * FROM analysis_cache WHERE {where_clause} ORDER BY created_at DESC"
            
            rows = await conn.fetch(query, *params)
            return [
                AnalysisCacheEntity(
                    chat_id=row['chat_id'],
                    time_period=row['time_period'],
                    message_content_hash=row['message_content_hash'],
                    result=row['result'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    async def invalidate_chat_cache(self, chat_id: int, time_period: Optional[str] = None) -> int:
        """Invalidate cache entries for a chat."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            if time_period:
                result = await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1 AND time_period = $2",
                    chat_id, time_period
                )
            else:
                result = await conn.execute(
                    "DELETE FROM analysis_cache WHERE chat_id = $1",
                    chat_id
                )
            # Extract number of deleted rows from result string like "DELETE 5"
            return int(result.split()[-1]) if result.split()[-1].isdigit() else 0


# Repository factory for easy access
class RepositoryFactory:
    """Factory for creating repository instances."""
    
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def get_chat_repository(cls) -> ChatRepository:
        """Get chat repository instance."""
        if 'chat' not in cls._instances:
            cls._instances['chat'] = ChatRepository()
        return cls._instances['chat']  # type: ignore
    
    @classmethod
    def get_user_repository(cls) -> UserRepository:
        """Get user repository instance."""
        if 'user' not in cls._instances:
            cls._instances['user'] = UserRepository()
        return cls._instances['user']  # type: ignore
    
    @classmethod
    def get_message_repository(cls) -> MessageRepository:
        """Get message repository instance."""
        if 'message' not in cls._instances:
            cls._instances['message'] = MessageRepository()
        return cls._instances['message']  # type: ignore
    
    @classmethod
    def get_analysis_cache_repository(cls) -> AnalysisCacheRepository:
        """Get analysis cache repository instance."""
        if 'analysis_cache' not in cls._instances:
            cls._instances['analysis_cache'] = AnalysisCacheRepository()
        return cls._instances['analysis_cache']  # type: ignore