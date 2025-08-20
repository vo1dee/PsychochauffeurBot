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

async def test_query(chat_id: int, target_date: str):
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
    
    logger.info(f"Testing query for chat_id: {chat_id}")
    logger.info(f"Target date: {target_date}")
    logger.info(f"Local range: {local_start} to {local_end}")
    logger.info(f"UTC range:   {start_utc} to {end_utc}")
    
    # Get database connection
    pool = await Database.get_pool()
    
    async with pool.acquire() as conn:
        # Test 1: Simple count query with timezone conversion
        count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE chat_id = $1
            AND timestamp >= $2
            AND timestamp < $3
        """, chat_id, start_utc, end_utc)
        
        logger.info(f"Test 1 (direct timestamp): Found {count} messages")
        
        # Test 2: Count with explicit timezone conversion
        count_tz = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE chat_id = $1
            AND timestamp AT TIME ZONE 'UTC' >= $2 AT TIME ZONE 'UTC'
            AND timestamp AT TIME ZONE 'UTC' < $3 AT TIME ZONE 'UTC'
        """, chat_id, start_utc, end_utc)
        
        logger.info(f"Test 2 (with AT TIME ZONE): Found {count_tz} messages")
        
        # Test 3: Get actual messages with timestamps
        messages = await conn.fetch("""
            SELECT timestamp, text 
            FROM messages 
            WHERE chat_id = $1
            AND timestamp >= $2
            AND timestamp < $3
            ORDER BY timestamp ASC
        """, chat_id, start_utc, end_utc)
        
        logger.info(f"Found {len(messages)} messages in the date range")
        
        # Print sample messages
        for i, msg in enumerate(messages[:5]):  # Show first 5 messages
            logger.info(f"Message {i+1}: {msg['timestamp']} - {msg['text'][:100]}...")
        
        if len(messages) > 5:
            logger.info(f"... and {len(messages) - 5} more messages")

if __name__ == "__main__":
    # Use the chat ID from the logs
    chat_id = -1002230625669
    target_date = "2025-08-20"
    
    asyncio.run(test_query(chat_id, target_date))
