"""
Script to diagnose and fix date analysis issues.
This helps identify why messages aren't being found for specific dates.
"""
import asyncio
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from modules.database import Database

async def analyze_date(chat_id: int, target_date: str):
    """Analyze messages for a specific date."""
    db = Database()
    
    try:
        # Parse the input date
        try:
            # Try different date formats
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    parsed_date = datetime.strptime(target_date, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Could not parse date: {target_date}")
                
            # Create date range for the target day
            start_date = datetime.combine(parsed_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_date = start_date + timedelta(days=1)
            
            logger.info(f"Analyzing messages for date: {start_date.date()} (UTC)")
            
            async with (await db.get_pool()).acquire() as conn:
                # Check if there are any messages in the date range
                count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM messages 
                    WHERE chat_id = $1 
                    AND timestamp >= $2 
                    AND timestamp < $3
                """, chat_id, start_date, end_date)
                
                logger.info(f"Found {count} messages in the date range")
                
                # If no messages found, check the date range of available messages
                if count == 0:
                    # Get the date range of messages in the database
                    date_range = await conn.fetchrow("""
                        SELECT 
                            MIN(timestamp) as min_date, 
                            MAX(timestamp) as max_date,
                            COUNT(*) as total_messages
                        FROM messages 
                        WHERE chat_id = $1
                    """, chat_id)
                    
                    if date_range['min_date']:
                        logger.info(f"Database messages date range: {date_range['min_date']} to {date_range['max_date']}")
                        logger.info(f"Total messages in database: {date_range['total_messages']}")
                    else:
                        logger.info("No messages found in the database for this chat")
                
                # Show sample messages from the target date
                if count > 0:
                    logger.info("Sample messages from the target date:")
                    messages = await conn.fetch("""
                        SELECT message_id, user_id, text, timestamp 
                        FROM messages 
                        WHERE chat_id = $1 
                        AND timestamp >= $2 
                        AND timestamp < $3
                        ORDER BY timestamp
                        LIMIT 5
                    """, chat_id, start_date, end_date)
                    
                    for msg in messages:
                        logger.info(f"- [{msg['timestamp']}] User {msg['user_id']}: {msg['text']}")
                        
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            logger.info("Supported formats: YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, DD/MM/YYYY")
            
    except Exception as e:
        logger.error(f"Error analyzing date: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze messages for a specific date")
    parser.add_argument("chat_id", type=int, help="Chat ID to analyze")
    parser.add_argument("date", help="Date to analyze (format: YYYY-MM-DD)")
    args = parser.parse_args()
    
    asyncio.run(analyze_date(args.chat_id, args.date))
