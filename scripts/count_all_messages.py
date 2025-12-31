#!/usr/bin/env python3
"""
Script to count all messages in the database.

This script connects to the database and counts all messages,
providing statistics about the message distribution.
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def count_all_messages() -> None:
    """Count all messages in the database and display statistics."""
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # First, check database info
            db_info = await conn.fetchrow("SELECT current_database() as db_name, current_schema() as schema_name")
            logger.info("=" * 60)
            logger.info("DATABASE CONNECTION INFO")
            logger.info("=" * 60)
            logger.info(f"Database: {db_info['db_name']}")
            logger.info(f"Schema: {db_info['schema_name']}")
            
            # Check all tables in the database
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            logger.info(f"\nTables in database: {', '.join([t['table_name'] for t in tables])}")
            
            # Check if messages table exists and get its size
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'messages'
                )
            """)
            
            if not table_exists:
                logger.error("ERROR: 'messages' table does not exist in the database!")
                return
            
            # Get table size information
            table_size = await conn.fetchrow("""
                SELECT 
                    pg_size_pretty(pg_total_relation_size('messages')) as total_size,
                    pg_size_pretty(pg_relation_size('messages')) as table_size,
                    pg_size_pretty(pg_total_relation_size('messages') - pg_relation_size('messages')) as indexes_size
            """)
            logger.info(f"\nTable size: {table_size['total_size']} (table: {table_size['table_size']}, indexes: {table_size['indexes_size']})")
            
            # Get total message count
            total_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
            
            logger.info("\n" + "=" * 60)
            logger.info("MESSAGE COUNT STATISTICS")
            logger.info("=" * 60)
            logger.info(f"Total messages in database: {total_count:,}")
            
            # Get message count by chat
            chat_counts = await conn.fetch("""
                SELECT 
                    c.chat_id,
                    c.title,
                    c.chat_type,
                    COUNT(*) as message_count
                FROM messages m
                JOIN chats c ON m.chat_id = c.chat_id
                GROUP BY c.chat_id, c.title, c.chat_type
                ORDER BY message_count DESC
            """)
            
            logger.info("\nMessages by chat:")
            logger.info("-" * 60)
            for row in chat_counts:
                chat_title = row['title'] or f"Chat {row['chat_id']}"
                logger.info(
                    f"  {chat_title} ({row['chat_type']}): "
                    f"{row['message_count']:,} messages"
                )
            
            # Get date range
            date_range = await conn.fetchrow("""
                SELECT 
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM messages
            """)
            
            if date_range and date_range['first_message']:
                logger.info("\nDate range:")
                logger.info("-" * 60)
                logger.info(f"  First message: {date_range['first_message']}")
                logger.info(f"  Last message: {date_range['last_message']}")
            
            # Get message count by type
            type_counts = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_command THEN 1 END) as commands,
                    COUNT(CASE WHEN is_gpt_reply THEN 1 END) as gpt_replies,
                    COUNT(CASE WHEN text IS NOT NULL THEN 1 END) as with_text
                FROM messages
            """)
            
            if type_counts:
                logger.info("\nMessage types:")
                logger.info("-" * 60)
                logger.info(f"  Total messages: {type_counts['total']:,}")
                logger.info(f"  Commands: {type_counts['commands']:,}")
                logger.info(f"  GPT replies: {type_counts['gpt_replies']:,}")
                logger.info(f"  Messages with text: {type_counts['with_text']:,}")
            
            logger.info("=" * 60)
            
            # Warning if count seems low
            if total_count < 100:
                logger.warning("\n⚠️  WARNING: Low message count detected!")
                logger.warning("If you expected more messages, you may need to:")
                logger.warning("  1. Check if data is in a different database")
                logger.warning("  2. Run migration script: python scripts/migrate_to_docker_db.py")
                logger.warning("  3. Update .env to point to the correct database")
                logger.warning(f"   Current database: {db_info['db_name']} on {os.getenv('DB_HOST', 'localhost')}")
                logger.warning("=" * 60)
            
    except Exception as e:
        logger.error(f"Error counting messages: {str(e)}", exc_info=True)
        raise
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(count_all_messages())
