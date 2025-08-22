#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, timedelta
from modules.database import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_db_connection(chat_id: int):
    try:
        # Get database pool
        pool = await Database.get_pool()
        logger.info("Successfully connected to the database")
        
        # Get current date in UTC
        now_utc = datetime.utcnow()
        today = now_utc.date()
        
        # Get messages from the last 7 days
        start_date = today - timedelta(days=7)
        
        async with pool.acquire() as conn:
            # Get message count by date
            messages_by_date = await conn.fetch("""
                SELECT 
                    DATE(timestamp) as message_date,
                    COUNT(*) as message_count
                FROM messages 
                WHERE chat_id = $1
                AND timestamp >= $2
                GROUP BY DATE(timestamp)
                ORDER BY message_date DESC
            """, chat_id, start_date)
            
            logger.info("\nMessage count by date (last 7 days):")
            for row in messages_by_date:
                logger.info(f"{row['message_date']}: {row['message_count']} messages")
            
            # Get recent messages
            recent_messages = await conn.fetch("""
                SELECT timestamp, text 
                FROM messages 
                WHERE chat_id = $1 
                ORDER BY timestamp DESC 
                LIMIT 5
            """, chat_id)
            
            logger.info("\nMost recent messages:")
            for msg in recent_messages:
                logger.info(f"{msg['timestamp']} - {msg['text']}")
            
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}", exc_info=True)

if __name__ == "__main__":
    chat_id = -1002096701815  # The chat ID with messages
    asyncio.run(check_db_connection(chat_id))
