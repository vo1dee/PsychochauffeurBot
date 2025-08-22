#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, timedelta
from modules.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_messages(chat_id: int):
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Get message count and date range
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_messages,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages 
                WHERE chat_id = $1
            """, chat_id)
            
            logger.info(f"Total messages in chat {chat_id}: {stats['total_messages']}")
            logger.info(f"First message: {stats['first_message']}")
            logger.info(f"Last message: {stats['last_message']}")
            
            # Get sample messages
            messages = await conn.fetch("""
                SELECT m.timestamp, u.username, m.text
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.user_id
                WHERE m.chat_id = $1
                ORDER BY m.timestamp DESC
                LIMIT 5
            """, chat_id)
            
            logger.info("\nSample messages (newest first):")
            for msg in messages:
                logger.info(f"{msg['timestamp']} - {msg['username'] or 'Unknown'}: {msg['text']}")
            
    except Exception as e:
        logger.error(f"Error checking messages: {str(e)}", exc_info=True)

if __name__ == "__main__":
    chat_id = -1002096701815  # Updated to match the chat ID with messages
    asyncio.run(check_messages(chat_id))
