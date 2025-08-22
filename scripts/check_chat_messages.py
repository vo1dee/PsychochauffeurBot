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

async def check_chat_messages(chat_id: int, days_ago: int = 7):
    try:
        # Get database pool
        pool = await Database.get_pool()
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_ago)
        
        async with pool.acquire() as conn:
            # Get message count and date range
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_messages,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages 
                WHERE chat_id = $1
                AND timestamp BETWEEN $2 AND $3
            """, chat_id, start_date, end_date)
            
            logger.info(f"\n{'='*50}")
            logger.info(f"Chat ID: {chat_id}")
            logger.info(f"Date range: {start_date} to {end_date}")
            logger.info(f"Total messages: {stats['total_messages']}")
            logger.info(f"First message: {stats['first_message']}")
            logger.info(f"Last message: {stats['last_message']}")
            
            # Get recent messages
            messages = await conn.fetch("""
                SELECT m.timestamp, u.username, m.text
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.user_id
                WHERE m.chat_id = $1
                AND m.timestamp BETWEEN $2 AND $3
                ORDER BY m.timestamp DESC
                LIMIT 10
            """, chat_id, start_date, end_date)
            
            logger.info("\nRecent messages (newest first):")
            for msg in messages:
                logger.info(f"{msg['timestamp']} - {msg['username'] or 'Unknown'}: {msg['text']}")
            
            logger.info(f"{'='*50}\n")
            
    except Exception as e:
        logger.error(f"Error checking messages: {str(e)}", exc_info=True)

if __name__ == "__main__":
    chat_id = -1002096701815  # The chat ID with messages
    asyncio.run(check_chat_messages(chat_id))
