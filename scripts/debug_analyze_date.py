#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, time
import pytz
from modules.database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_analyze_date(chat_id: int, date_str: str):
    """Debug the analyze date command with detailed logging."""
    try:
        # Convert string date to date object
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Create date range in local timezone (Kyiv)
        local_tz = pytz.timezone('Europe/Kyiv')
        
        # Create start and end of day in local timezone
        local_start = local_tz.localize(datetime.combine(target_date, time.min))
        local_end = local_tz.localize(datetime.combine(target_date, time.max))
        
        # Convert to UTC for database query (naive datetime)
        start_utc = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        end_utc = local_end.astimezone(pytz.UTC).replace(tzinfo=None)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Debugging analyze date: {date_str}")
        logger.info(f"Local time range: {local_start} to {local_end}")
        logger.info(f"UTC time range:   {start_utc} to {end_utc}")
        
        # Initialize database
        pool = await Database.get_pool()
        
        async with pool.acquire() as conn:
            # Check message count in the date range
            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM messages
                WHERE chat_id = $1
                AND timestamp >= $2
                AND timestamp <= $3
            """, chat_id, start_utc, end_utc)
            
            logger.info(f"Found {count} messages in the date range")
            
            # Get date range of all messages
            date_range = await conn.fetchrow("""
                SELECT 
                    MIN(timestamp) as min_date, 
                    MAX(timestamp) as max_date,
                    COUNT(*) as total_messages
                FROM messages 
                WHERE chat_id = $1
            """, chat_id)
            
            if date_range and date_range['min_date']:
                min_local = date_range['min_date'].replace(tzinfo=pytz.UTC).astimezone(local_tz)
                max_local = date_range['max_date'].replace(tzinfo=pytz.UTC).astimezone(local_tz)
                
                logger.info(f"Database date range: {min_local} to {max_local}")
                logger.info(f"Total messages in database: {date_range['total_messages']}")
                
                # Check if there are any messages on the target date using a wider range
                messages = await conn.fetch("""
                    SELECT timestamp, text 
                    FROM messages 
                    WHERE chat_id = $1 
                    AND timestamp >= $2
                    AND timestamp <= $3
                    ORDER BY timestamp DESC 
                    LIMIT 5
                """, chat_id, start_utc, end_utc)
                
                if messages:
                    logger.info("\nSample messages found in the date range:")
                    for msg in messages:
                        msg_time = msg['timestamp']
                        if msg_time.tzinfo is None:
                            msg_time = pytz.UTC.localize(msg_time)
                        local_time = msg_time.astimezone(local_tz)
                        logger.info(f"- {local_time} (UTC: {msg_time}): {msg['text'][:100]}")
                else:
                    logger.warning("No messages found in the specified date range")
                    
                    # Check messages from the same day in the database
                    same_day_messages = await conn.fetch("""
                        SELECT timestamp, text 
                        FROM messages 
                        WHERE chat_id = $1 
                        AND DATE(timestamp) = $2
                        ORDER BY timestamp DESC 
                        LIMIT 5
                    """, chat_id, target_date)
                    
                    if same_day_messages:
                        logger.info("\nFound messages using direct DATE() comparison:")
                        for msg in same_day_messages:
                            msg_time = msg['timestamp']
                            if msg_time.tzinfo is None:
                                msg_time = pytz.UTC.localize(msg_time)
                            local_time = msg_time.astimezone(local_tz)
                            logger.info(f"- {local_time} (UTC: {msg_time}): {msg['text'][:100]}")
                    else:
                        logger.warning("No messages found using direct DATE() comparison")
            
            logger.info(f"{'='*80}\n")
            
    except Exception as e:
        logger.error(f"Error in debug_analyze_date: {str(e)}", exc_info=True)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.debug_analyze_date <chat_id> <YYYY-MM-DD>")
        sys.exit(1)
    
    chat_id = int(sys.argv[1])
    date_str = sys.argv[2]
    
    asyncio.run(debug_analyze_date(chat_id, date_str))
