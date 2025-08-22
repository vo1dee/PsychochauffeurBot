"""
Script to fix orphaned messages (messages with user_id not in users table).
This creates placeholder user entries for any missing users.
"""
import asyncio
import logging
from pathlib import Path
import sys
from datetime import datetime, timezone

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from modules.database import Database

async def fix_orphaned_messages():
    """Find and fix messages with user_id not in users table."""
    db = Database()
    
    try:
        async with (await db.get_pool()).acquire() as conn:
            # Find messages with user_id not in users table
            orphaned_messages = await conn.fetch("""
                SELECT DISTINCT m.user_id, m.chat_id
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.user_id
                WHERE m.user_id IS NOT NULL
                AND u.user_id IS NULL;
            """)
            
            if not orphaned_messages:
                logger.info("No orphaned messages found")
                return
                
            logger.info(f"Found {len(orphaned_messages)} orphaned messages to fix")
            
            # Create placeholder users for each missing user_id
            for msg in orphaned_messages:
                user_id = msg['user_id']
                logger.info(f"Creating placeholder user for user_id={user_id}")
                
                try:
                    await conn.execute("""
                        INSERT INTO users (user_id, first_name, last_name, username, is_bot, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id) DO NOTHING;
                    """,
                        user_id,  # user_id
                        f"User-{user_id}",  # first_name
                        None,  # last_name
                        None,  # username
                        False,  # is_bot
                        datetime.now(timezone.utc)  # created_at
                    )
                    logger.info(f"Created placeholder user for user_id={user_id}")
                    
                except Exception as e:
                    logger.error(f"Error creating placeholder user for user_id={user_id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error fixing orphaned messages: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(fix_orphaned_messages())
