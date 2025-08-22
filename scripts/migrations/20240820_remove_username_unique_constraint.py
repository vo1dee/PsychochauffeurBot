"""
Migration script to remove the unique constraint from the username field in the users table.
This allows multiple users to have the same username, which can happen when usernames change.
"""
import asyncio
import asyncpg
import logging
from pathlib import Path
import sys

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from modules.database import Database

async def migrate():
    """Run the migration to remove the unique constraint on the username field."""
    db = Database()
    
    try:
        async with (await db.get_pool()).acquire() as conn:
            # Check if the constraint exists
            constraint_exists = await conn.fetchval("""
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'unique_username' AND conrelid = 'users'::regclass
            """)
            
            if constraint_exists:
                logger.info("Dropping unique_username constraint...")
                await conn.execute("""
                    ALTER TABLE users DROP CONSTRAINT IF EXISTS unique_username;
                """)
                logger.info("Successfully dropped unique_username constraint")
            else:
                logger.info("unique_username constraint does not exist, nothing to do")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
