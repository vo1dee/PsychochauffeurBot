from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional, Union, Dict, Any
import pytz
from modules.database import Database
from modules.const import KYIV_TZ

async def get_messages_for_chat_today(chat_id: int) -> List[Tuple[datetime, str, str]]:
    """
    Fetch all messages from the specified chat_id for the current calendar day.
    
    Args:
        chat_id: The chat ID to fetch messages from
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    today = datetime.now(KYIV_TZ).date()
    start_time = datetime.combine(today, datetime.min.time(), tzinfo=KYIV_TZ)
    end_time = datetime.combine(today, datetime.max.time(), tzinfo=KYIV_TZ)
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp <= $3
            ORDER BY m.timestamp ASC
        """, chat_id, start_time, end_time)
        
        return [(row['timestamp'], row['username'] or 'Unknown', row['text']) for row in rows]

async def get_last_n_messages_in_chat(chat_id: int, count: int) -> List[Tuple[datetime, str, str]]:
    """
    Fetch the last n messages from the specified chat_id.
    
    Args:
        chat_id: The chat ID to fetch messages from
        count: Number of messages to fetch
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            ORDER BY m.timestamp DESC
            LIMIT $2
        """, chat_id, count)
        
        # Return in chronological order
        return [(row['timestamp'], row['username'] or 'Unknown', row['text']) for row in reversed(rows)]

async def get_messages_for_chat_last_n_days(chat_id: int, days: int) -> List[Tuple[datetime, str, str]]:
    """
    Fetch all messages from the specified chat_id for the last n calendar days.
    
    Args:
        chat_id: The chat ID to fetch messages from
        days: Number of days to look back (0 = today only)
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    end_time = datetime.now(KYIV_TZ)
    start_time = end_time - timedelta(days=days)
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp <= $3
            ORDER BY m.timestamp ASC
        """, chat_id, start_time, end_time)
        
        return [(row['timestamp'], row['username'] or 'Unknown', row['text']) for row in rows]

async def get_messages_for_chat_date_period(
    chat_id: int,
    start_date: Union[str, date],
    end_date: Union[str, date]
) -> List[Tuple[datetime, str, str]]:
    """
    Fetch all messages from chat_id between start_date and end_date (inclusive).
    
    Args:
        chat_id: The chat ID to fetch messages from
        start_date: Start date (YYYY-MM-DD string or date object)
        end_date: End date (YYYY-MM-DD string or date object)
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    # Convert string dates to date objects if needed
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    start_time = datetime.combine(start_date, datetime.min.time(), tzinfo=KYIV_TZ)
    end_time = datetime.combine(end_date, datetime.max.time(), tzinfo=KYIV_TZ)
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp <= $3
            ORDER BY m.timestamp ASC
        """, chat_id, start_time, end_time)
        
        return [(row['timestamp'], row['username'] or 'Unknown', row['text']) for row in rows]

async def get_messages_for_chat_single_date(
    chat_id: int,
    target_date: Union[str, date]
) -> List[Tuple[datetime, str, str]]:
    """
    Fetch all messages from chat_id for a specific date.
    
    Args:
        chat_id: The chat ID to fetch messages from
        target_date: Target date (YYYY-MM-DD string or date object)
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    # Convert string date to date object if needed
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=KYIV_TZ)
    end_time = datetime.combine(target_date, datetime.max.time(), tzinfo=KYIV_TZ)
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp <= $3
            ORDER BY m.timestamp ASC
        """, chat_id, start_time, end_time)
        
        return [(row['timestamp'], row['username'] or 'Unknown', row['text']) for row in rows]

async def get_user_chat_stats(chat_id: int, user_id: int) -> Dict[str, Any]:
    """
    Get message statistics for a specific user in a chat.
    
    Args:
        chat_id: The chat ID
        user_id: The user ID
        
    Returns:
        Dictionary containing message statistics
    """
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # Get total messages
        total_messages = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE chat_id = $1 AND user_id = $2
        """, chat_id, user_id)
        
        # Get messages in last 7 days
        week_ago = datetime.now(KYIV_TZ) - timedelta(days=7)
        messages_last_week = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE chat_id = $1 AND user_id = $2 AND timestamp >= $3
        """, chat_id, user_id, week_ago)
        
        # Get command usage
        command_stats = await conn.fetch("""
            SELECT command_name, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = $2 AND is_command = true
            GROUP BY command_name
            ORDER BY count DESC
        """, chat_id, user_id)
        
        # Get most active hour
        active_hour = await conn.fetchval("""
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = $2
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, chat_id, user_id)
        
        # Get first and last message timestamps
        first_message = await conn.fetchval("""
            SELECT timestamp
            FROM messages
            WHERE chat_id = $1 AND user_id = $2
            ORDER BY timestamp ASC
            LIMIT 1
        """, chat_id, user_id)
        
        last_message = await conn.fetchval("""
            SELECT timestamp
            FROM messages
            WHERE chat_id = $1 AND user_id = $2
            ORDER BY timestamp DESC
            LIMIT 1
        """, chat_id, user_id)
        
        return {
            'total_messages': total_messages,
            'messages_last_week': messages_last_week,
            'command_stats': [(row['command_name'], row['count']) for row in command_stats],
            'most_active_hour': int(active_hour) if active_hour is not None else None,
            'first_message': first_message,
            'last_message': last_message
        }

async def get_user_chat_stats_with_fallback(chat_id: int, user_id: int, username: str) -> dict:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # Get all user_ids for this username
        user_ids = [user_id]
        rows = await conn.fetch("""
            SELECT user_id FROM users WHERE username = $1
        """, username)
        for row in rows:
            if row['user_id'] not in user_ids:
                user_ids.append(row['user_id'])

        # Aggregate stats for all user_ids
        total_messages = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE chat_id = $1 AND user_id = ANY($2::bigint[])
        """, chat_id, user_ids)

        week_ago = datetime.now(KYIV_TZ) - timedelta(days=7)
        messages_last_week = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE chat_id = $1 AND user_id = ANY($2::bigint[]) AND timestamp >= $3
        """, chat_id, user_ids, week_ago)

        command_stats = await conn.fetch("""
            SELECT command_name, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = ANY($2::bigint[]) AND is_command = true
            GROUP BY command_name
            ORDER BY count DESC
        """, chat_id, user_ids)

        active_hour = await conn.fetchval("""
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = ANY($2::bigint[])
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """, chat_id, user_ids)

        first_message = await conn.fetchval("""
            SELECT timestamp
            FROM messages
            WHERE chat_id = $1 AND user_id = ANY($2::bigint[])
            ORDER BY timestamp ASC
            LIMIT 1
        """, chat_id, user_ids)

        last_message = await conn.fetchval("""
            SELECT timestamp
            FROM messages
            WHERE chat_id = $1 AND user_id = ANY($2::bigint[])
            ORDER BY timestamp DESC
            LIMIT 1
        """, chat_id, user_ids)

        return {
            'total_messages': total_messages,
            'messages_last_week': messages_last_week,
            'command_stats': [(row['command_name'], row['count']) for row in command_stats],
            'most_active_hour': int(active_hour) if active_hour is not None else None,
            'first_message': first_message,
            'last_message': last_message
        } 