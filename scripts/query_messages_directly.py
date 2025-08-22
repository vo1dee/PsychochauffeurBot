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

async def query_messages():
    chat_id = -1002230625669
    target_date = "2025-08-20"
    
    # Parse the target date
    target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    # Set up timezone
    local_tz = pytz.timezone('Europe/Kyiv')
    
    # Create date range in local timezone
    local_start = local_tz.localize(datetime.combine(target_date, time.min))
    local_end = local_tz.localize(datetime.combine(target_date + timedelta(days=1), time.min))
    
    # Convert to UTC
    start_utc = local_start.astimezone(pytz.UTC)
    end_utc = local_end.astimezone(pytz.UTC)
    
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"Target date: {target_date}")
    logger.info(f"Local range: {local_start} to {local_end}")
    logger.info(f"UTC range:   {start_utc} to {end_utc}")
    
    # Get database connection
    pool = await Database.get_pool()
    
    async with pool.acquire() as conn:
        # Get the exact query being executed
        query = """
            SELECT m.timestamp, u.username, m.text
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1
            AND m.timestamp >= $2
            AND m.timestamp < $3
            ORDER BY m.timestamp ASC
        """
        
        logger.info("\nExecuting query:")
        logger.info(query)
        logger.info(f"With params: {chat_id}, {start_utc}, {end_utc}")
        
        # Execute the query
        rows = await conn.fetch(query, chat_id, start_utc, end_utc)
        
        logger.info(f"\nFound {len(rows)} messages")
        
        # Print the first 5 messages
        for i, row in enumerate(rows[:5]):
            logger.info(f"Message {i+1}:")
            logger.info(f"  Timestamp: {row['timestamp']}")
            logger.info(f"  Username: {row['username']}")
            logger.info(f"  Text: {row['text'][:100]}...")
        
        if len(rows) > 5:
            logger.info(f"... and {len(rows) - 5} more messages")

if __name__ == "__main__":
    asyncio.run(query_messages())
