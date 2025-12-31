from datetime import datetime, date, timedelta, time
from typing import List, Tuple, Optional, Union, Dict, Any
import pytz
import logging
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
    # Get current date in local timezone
    today = datetime.now(KYIV_TZ).date()
    local_start = datetime.combine(today, datetime.min.time(), tzinfo=KYIV_TZ)
    local_end = datetime.combine(today, datetime.max.time(), tzinfo=KYIV_TZ)
    
    # Convert to UTC for database query
    start_time_utc = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
    end_time_utc = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
    
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
        """, chat_id, start_time_utc, end_time_utc)
        
        # Convert timestamps back to local timezone for display
        return [
            (
                row['timestamp'].replace(tzinfo=pytz.UTC).astimezone(KYIV_TZ),
                row['username'] or 'Unknown',
                row['text']
            )
            for row in rows
        ]

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
    logger = logging.getLogger(__name__)
    
    # Get current time in local timezone
    end_time = datetime.now(KYIV_TZ)
    start_time = end_time - timedelta(days=days)
    
    # Convert to UTC for database query
    start_time_utc = start_time.astimezone(pytz.UTC)
    end_time_utc = end_time.astimezone(pytz.UTC)
    
    # For PostgreSQL TIMESTAMP WITH TIME ZONE, we can pass timezone-aware datetimes
    # PostgreSQL will handle the conversion correctly
    logger.info(f"Querying messages for chat {chat_id} from last {days} days")
    logger.info(f"Time range (Kyiv): {start_time} to {end_time}")
    logger.info(f"Time range (UTC): {start_time_utc} to {end_time_utc}")
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # First check total messages in DB for debugging
        total_count = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE chat_id = $1
        """, chat_id)
        logger.info(f"Total messages in DB for chat {chat_id}: {total_count}")
        
        # Check date range of messages in the database
        date_range = await conn.fetchrow("""
            SELECT 
                MIN(timestamp) as min_date, 
                MAX(timestamp) as max_date,
                COUNT(*) as total_count
            FROM messages 
            WHERE chat_id = $1
        """, chat_id)
        if date_range:
            logger.info(f"Date range of messages in DB: {date_range['min_date']} to {date_range['max_date']} ({date_range['total_count']} total messages)")
        
        # Query with timezone-aware datetimes - PostgreSQL will handle conversion
        rows = await conn.fetch("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp <= $3
            ORDER BY m.timestamp ASC
        """, chat_id, start_time_utc, end_time_utc)
        
        logger.info(f"Query returned {len(rows)} messages")
        
        # Convert timestamps back to local timezone for display
        result = []
        for row in rows:
            timestamp = row['timestamp']
            # Handle timezone-aware or naive timestamps from database
            if timestamp.tzinfo is None:
                # If naive, assume UTC
                timestamp = pytz.UTC.localize(timestamp)
            # Convert to local timezone
            local_timestamp = timestamp.astimezone(KYIV_TZ)
            result.append((
                local_timestamp,
                row['username'] or 'Unknown',
                row['text'] or ''
            ))
        
        return result

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
    
    # Create datetime objects in local timezone
    local_start = datetime.combine(start_date, datetime.min.time(), tzinfo=KYIV_TZ)
    local_end = datetime.combine(end_date, datetime.max.time(), tzinfo=KYIV_TZ)
    
    # Convert to UTC for database query
    start_time_utc = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
    end_time_utc = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
    
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
        """, chat_id, start_time_utc, end_time_utc)
        
        # Convert timestamps back to local timezone for display
        return [
            (
                row['timestamp'].replace(tzinfo=pytz.UTC).astimezone(KYIV_TZ),
                row['username'] or 'Unknown',
                row['text']
            )
            for row in rows
        ]

async def get_messages_for_chat_single_date(chat_id: int, target_date: Union[date, str]) -> List[Tuple[datetime, str, str]]:
    """
    Fetch all messages from the specified chat_id for a specific date.
    
    Args:
        chat_id: The chat ID to fetch messages from
        target_date: The target date (as date object or 'YYYY-MM-DD' string)
        
    Returns:
        List of tuples containing (timestamp, sender_name, text)
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Convert string date to date object if needed
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        # Create date range in local timezone (Kyiv)
        local_tz = pytz.timezone('Europe/Kyiv')
        
        # Log the input parameters
        logger.info(f"Getting messages for chat_id: {chat_id}, date: {target_date}")
        
        # Create start of day and start of next day in local timezone
        local_start = local_tz.localize(datetime.combine(target_date, time.min))
        local_end = local_tz.localize(datetime.combine(target_date + timedelta(days=1), time.min))
        
        # Convert to UTC for database query
        start_utc = local_start.astimezone(pytz.UTC)
        end_utc = local_end.astimezone(pytz.UTC)
        
        # For database query, we need naive datetime
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        
        logger.info(f"Converted date range:")
        logger.info(f"  Local: {local_start} to {local_end}")
        logger.info(f"  UTC:   {start_utc} to {end_utc}")
        logger.info(f"  Types: {type(start_utc)}, {type(end_utc)}")
        logger.info(f"  Using chat_id: {chat_id}")
        
        logger.info(f"Querying messages for date: {target_date}")
        logger.info(f"Local time range: {local_start} to {local_end}")
        logger.info(f"UTC time range: {start_utc} to {end_utc}")
        
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # First check if we have any messages in this date range
            # Using half-open interval [start, end) to avoid missing messages at the end of the day
            count_query = """
                SELECT COUNT(*)
                FROM messages
                WHERE chat_id = $1
                AND timestamp >= $2
                AND timestamp < $3
            """
            logger.info(f"Executing count query:\n{count_query}\nWith params: chat_id={chat_id}, start_utc={start_naive}, end_utc={end_naive}")
            
            # Execute with naive datetime objects
            count = await conn.fetchval(count_query, chat_id, start_naive, end_naive)
            
            logger.info(f"Found {count} messages in the date range")
            
            # Debug: Check if there are any messages in the database at all for this chat
            total_count = await conn.fetchval("""
                SELECT COUNT(*) FROM messages WHERE chat_id = $1
            """, chat_id)
            logger.info(f"Total messages in DB for chat {chat_id}: {total_count}")
            
            # Debug: Check the date range of messages in the database
            date_range = await conn.fetchrow("""
                SELECT 
                    MIN(timestamp) as min_date, 
                    MAX(timestamp) as max_date,
                    COUNT(*) as total_count
                FROM messages 
                WHERE chat_id = $1
            """, chat_id)
            if date_range:
                logger.info(f"Date range of messages in DB: {date_range['min_date']} to {date_range['max_date']} ({date_range['total_count']} total messages)")
            
            if count == 0:
                # If no messages found, check the date range of available messages
                date_range = await conn.fetchrow("""
                    SELECT 
                        MIN(timestamp) as min_date, 
                        MAX(timestamp) as max_date,
                        COUNT(*) as total_messages
                    FROM messages 
                    WHERE chat_id = $1
                """, chat_id)
                
                if date_range and date_range['min_date']:
                    # Convert database timestamps to local timezone for display
                    min_local = date_range['min_date'].replace(tzinfo=pytz.UTC).astimezone(local_tz)
                    max_local = date_range['max_date'].replace(tzinfo=pytz.UTC).astimezone(local_tz)
                    
                    logger.warning(f"No messages found for {target_date}.")
                    logger.warning(f"Database date range: {min_local} to {max_local}")
                    logger.warning(f"Total messages in database: {date_range['total_messages']}")
                    
                    # Get some sample messages to see what dates we have
                    sample_messages = await conn.fetch("""
                        SELECT timestamp, text 
                        FROM messages 
                        WHERE chat_id = $1 
                        ORDER BY timestamp DESC 
                        LIMIT 5
                    """, chat_id)
                    
                    if sample_messages:
                        logger.warning("Sample messages from database:")
                        for msg in sample_messages:
                            msg_time = msg['timestamp']
                            if msg_time.tzinfo is None:
                                msg_time = pytz.UTC.localize(msg_time)
                            local_time = msg_time.astimezone(local_tz)
                            logger.warning(f"- {local_time} (UTC: {msg_time}): {msg['text'][:100]}...")
                else:
                    logger.warning("No messages found in the database for this chat")
                
                return []
            
            # Log the exact query being executed
            query = """
                SELECT m.timestamp, u.username, m.text
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.user_id
                WHERE m.chat_id = $1
                AND m.timestamp >= $2
                AND m.timestamp < $3
                ORDER BY m.timestamp ASC
            """
            logger.info(f"Executing query with params: chat_id={chat_id}, start_utc={start_naive}, end_utc={end_naive}")
            logger.info(f"Query: {query}")
            
            # Execute the query with naive datetime objects
            rows = await conn.fetch(query, chat_id, start_naive, end_naive)
            
            # Log the EXPLAIN ANALYZE output for debugging
            try:
                explain = await conn.fetch("""
                    EXPLAIN ANALYZE 
                    SELECT m.timestamp, u.username, m.text
                    FROM messages m
                    LEFT JOIN users u ON m.user_id = u.user_id
                    WHERE m.chat_id = $1
                    AND m.timestamp >= $2
                    AND m.timestamp < $3
                    ORDER BY m.timestamp ASC
                """, chat_id, start_utc, end_utc)
                logger.info("Query plan:")
                for row in explain:
                    logger.info(f"  {row['QUERY PLAN']}")
            except Exception as e:
                logger.warning(f"Failed to get query plan: {e}")
            
            # Fetch the messages
            rows = await conn.fetch(query, chat_id, start_utc, end_utc)
            
            # Log the raw results
            logger.info(f"Raw query returned {len(rows)} rows")
            
            # If no rows found, try to find any messages in the database
            if not rows:
                logger.warning("No rows returned. Checking for any messages in the database...")
                any_messages = await conn.fetch("""
                    SELECT timestamp, text 
                    FROM messages 
                    WHERE chat_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                """, chat_id)
                
                if any_messages:
                    logger.warning(f"Found {len(any_messages)} recent messages in the database:")
                    for i, msg in enumerate(any_messages):
                        logger.warning(f"  {i+1}. {msg['timestamp']} - {msg['text'][:100]}")
                else:
                    logger.warning("No messages found in the database for this chat")
            
            # Convert timestamps back to local timezone for display
            messages = []
            processed_count = 0
            error_count = 0
            
            for row in rows:
                try:
                    timestamp = row['timestamp']
                    
                    # Log raw timestamp info for debugging
                    logger.debug(f"Processing message - raw timestamp: {timestamp}, type: {type(timestamp)}")
                    
                    # Handle timezone
                    if timestamp is None:
                        logger.warning(f"Skipping message with null timestamp: {row}")
                        error_count += 1
                        continue
                        
                    if timestamp.tzinfo is None:
                        logger.debug("Localizing naive timestamp to UTC")
                        timestamp = pytz.UTC.localize(timestamp)
                    
                    # Convert to local timezone
                    local_time = timestamp.astimezone(local_tz)
                    
                    messages.append((
                        local_time,
                        row['username'] or 'Unknown',
                        row['text'] or ''  # Ensure text is never None
                    ))
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing message row: {e}", exc_info=True)
                    error_count += 1
            
            # Log summary
            logger.info(f"Processed {processed_count} messages successfully")
            if error_count > 0:
                logger.warning(f"Encountered {error_count} errors while processing messages")
            
            if not messages and rows:
                logger.error("No messages were processed successfully despite having rows. Check logs for errors.")
            
            return messages
            
    except Exception as e:
        logger.error(f"Error in get_messages_for_chat_single_date: {str(e)}", exc_info=True)
        raise

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
            SELECT split_part(command_name, '@', 1) AS base_command, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = $2 AND is_command = true
            GROUP BY base_command
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
            'command_stats': [(row['base_command'], row['count']) for row in command_stats],
            'most_active_hour': int(active_hour) if active_hour is not None else None,
            'first_message': first_message,
            'last_message': last_message
        }

async def get_user_chat_stats_with_fallback(chat_id: int, user_id: int, username: str) -> Dict[str, Any]:
    from modules.logger import general_logger
    
    general_logger.info(f"get_user_chat_stats_with_fallback: chat_id={chat_id}, user_id={user_id}, username={username}")
    
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
        
        general_logger.info(f"get_user_chat_stats_with_fallback: user_ids={user_ids}")

        # Aggregate stats for all user_ids
        total_messages = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE chat_id = $1 AND user_id = ANY($2::bigint[])
        """, chat_id, user_ids)
        
        general_logger.info(f"get_user_chat_stats_with_fallback: total_messages={total_messages}")

        week_ago = datetime.now(KYIV_TZ) - timedelta(days=7)
        messages_last_week = await conn.fetchval("""
            SELECT COUNT(*) FROM messages WHERE chat_id = $1 AND user_id = ANY($2::bigint[]) AND timestamp >= $3
        """, chat_id, user_ids, week_ago)

        command_stats = await conn.fetch("""
            SELECT split_part(command_name, '@', 1) AS base_command, COUNT(*) as count
            FROM messages
            WHERE chat_id = $1 AND user_id = ANY($2::bigint[]) AND is_command = true
            GROUP BY base_command
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
            'command_stats': [(row['base_command'], row['count']) for row in command_stats],
            'most_active_hour': int(active_hour) if active_hour is not None else None,
            'first_message': first_message,
            'last_message': last_message
        } 

async def get_last_message_for_user_in_chat(chat_id: int, user_id: Optional[int] = None, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get the last message (timestamp, username, text) for a user in a chat.
    If username is provided, will aggregate all user_ids with that username (for username changes).
    Returns None if not found.
    """
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        user_ids = set()
        if username:
            rows = await conn.fetch("""
                SELECT user_id FROM users WHERE username = $1
            """, username)
            for row in rows:
                user_ids.add(row['user_id'])
        if user_id is not None:
            user_ids.add(user_id)
        if not user_ids:
            return None
        # Debug log
        try:
            from modules.logger import general_logger
            general_logger.info(f"[missing] get_last_message_for_user_in_chat user_ids: {list(user_ids)} for chat_id={chat_id}")
        except Exception:
            pass
        row = await conn.fetchrow("""
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1 AND m.user_id = ANY($2::bigint[])
            ORDER BY m.timestamp DESC
            LIMIT 1
        """, chat_id, list(user_ids))
        if row:
            return {
                'timestamp': row['timestamp'],
                'username': row['username'] or 'Unknown',
                'text': row['text']
            }
        return None 