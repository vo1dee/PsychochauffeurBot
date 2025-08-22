#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, time, timedelta
import pytz
from modules.database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_messages(chat_id: int, target_date: str):
    """Check messages in the database for a specific date."""
    try:
        # Parse the target date
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        # Set up timezone
        local_tz = pytz.timezone('Europe/Kyiv')
        
        # Create date range in local timezone
        local_start = local_tz.localize(datetime.combine(target_date, time.min))
        local_end = local_tz.localize(datetime.combine(target_date + timedelta(days=1), time.min))
        
        # Convert to UTC for database query
        start_utc = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        end_utc = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Checking messages for chat ID: {chat_id}")
        logger.info(f"Target date: {target_date}")
        logger.info(f"Local time range: {local_start} to {local_end}")
        logger.info(f"UTC time range:   {start_utc} to {end_utc}")
        
        # Get database connection
        pool = await Database.get_pool()
        
        async with pool.acquire() as conn:
            # Check total messages in the chat
            total_messages = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE chat_id = $1", 
                chat_id
            )
            logger.info(f"Total messages in chat: {total_messages}")
            
            # Get message date range
            date_range = await conn.fetchrow(
                "SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date FROM messages WHERE chat_id = $1",
                chat_id
            )
            
            if date_range and date_range['min_date']:
                min_date = date_range['min_date']
                max_date = date_range['max_date']
                
                # Convert to local timezone for display
                if min_date.tzinfo is None:
                    min_date = pytz.UTC.localize(min_date)
                if max_date.tzinfo is None:
                    max_date = pytz.UTC.localize(max_date)
                
                min_local = min_date.astimezone(local_tz)
                max_local = max_date.astimezone(local_tz)
                
                logger.info(f"Message date range in database:")
                logger.info(f"  Earliest: {min_local} (UTC: {min_date})")
                logger.info(f"  Latest:   {max_local} (UTC: {max_date})")
            
            # Check for messages in the target date range
            messages = await conn.fetch(
                """
                SELECT timestamp, text 
                FROM messages 
                WHERE chat_id = $1
                AND timestamp >= $2 
                AND timestamp < $3
                ORDER BY timestamp ASC
                """,
                chat_id, start_utc, end_utc
            )
            
            logger.info(f"\nFound {len(messages)} messages in the date range")
            
            if not messages:
                # If no messages found, check for any messages in the database
                all_messages = await conn.fetch(
                    "SELECT timestamp, text FROM messages WHERE chat_id = $1 ORDER BY timestamp DESC LIMIT 5",
                    chat_id
                )
                
                if all_messages:
                    logger.info("\nSample of recent messages in the database:")
                    for msg in all_messages:
                        msg_time = msg['timestamp']
                        if msg_time.tzinfo is None:
                            msg_time = pytz.UTC.localize(msg_time)
                        local_time = msg_time.astimezone(local_tz)
                        logger.info(f"- {local_time} (UTC: {msg_time}): {msg['text'][:100]}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error checking messages: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Use the chat ID from the logs
    chat_id = -1002230625669
    target_date = "2025-08-20"
    
    asyncio.run(check_messages(chat_id, target_date))
