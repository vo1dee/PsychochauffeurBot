#!/usr/bin/env python3
import asyncio
import logging
from modules.database import Database

async def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Get database pool
        pool = await Database.get_pool()
        
        async with pool.acquire() as conn:
            # Get all unique chat IDs with message counts
            logger.info("Fetching chat IDs from database...")
            chat_stats = await conn.fetch("""
                SELECT 
                    chat_id, 
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages 
                GROUP BY chat_id 
                ORDER BY message_count DESC
            """)
            
            if not chat_stats:
                logger.warning("No messages found in the database")
                return
                
            logger.info("\nChat IDs in the database:")
            logger.info("-" * 80)
            
            for row in chat_stats:
                logger.info(f"Chat ID: {row['chat_id']}")
                logger.info(f"  Messages: {row['message_count']}")
                logger.info(f"  First message: {row['first_message']}")
                logger.info(f"  Last message:  {row['last_message']}")
                logger.info("-" * 80)
                
    except Exception as e:
        logger.error(f"Error checking chat IDs: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
