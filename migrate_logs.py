import asyncio
import re
from datetime import datetime
import glob
import os
from modules.database import Database

async def migrate_logs():
    """
    Migrate chat logs from log files to PostgreSQL database.
    """
    try:
        # Initialize the database
        await Database.initialize()
        print("Database initialized successfully!")

        # Get all chat log files
        log_files = glob.glob('logs/chat*.log') + glob.glob('logs/chat_*/*.log')
        
        for log_file in log_files:
            print(f"Processing {log_file}...")
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Skip initialization messages
                    if "Chat logging system initialized" in line:
                        continue
                        
                    # Parse the log line
                    # Format: timestamp - chat_logger - INFO - chat_id - chat_type - username - User message: text
                    match = re.match(r'(.+?) - chat_logger - INFO - (.+?) - (.+?) - (.+?) - User message: (.+)', line)
                    if not match:
                        continue
                        
                    timestamp_str, chat_id, chat_type, username, text = match.groups()
                    
                    # Convert timestamp
                    try:
                        timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S,%f')
                    except ValueError:
                        try:
                            timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S +%f')
                        except ValueError:
                            print(f"Could not parse timestamp: {timestamp_str}")
                            continue
                    
                    # Clean up values
                    chat_id = chat_id.strip()
                    if chat_id == 'N/A':
                        continue
                        
                    chat_type = chat_type.strip()
                    if chat_type == 'Unknown':
                        continue
                        
                    username = username.strip()
                    if username == 'Unknown':
                        continue
                    
                    # Save chat info
                    pool = await Database.get_pool()
                    async with pool.acquire() as conn:
                        # Save chat
                        await conn.execute("""
                            INSERT INTO chats (chat_id, chat_type, title)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (chat_id) DO UPDATE
                            SET chat_type = $2, title = $3
                        """, int(chat_id), chat_type, f"Chat {chat_id}")
                        
                        # Save user
                        await conn.execute("""
                            INSERT INTO users (user_id, first_name, username)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (user_id) DO UPDATE
                            SET first_name = $2, username = $3
                        """, int(chat_id), username, username)
                        
                        # Save message
                        await conn.execute("""
                            INSERT INTO messages (
                                message_id, chat_id, user_id, timestamp, text,
                                is_command, command_name, is_gpt_reply
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (chat_id, message_id) DO NOTHING
                        """,
                            int(datetime.now().timestamp() * 1000),  # Generate a unique message ID
                            int(chat_id),
                            int(chat_id),
                            timestamp,
                            text.strip(),
                            False,
                            None,
                            False
                        )
            
            print(f"Finished processing {log_file}")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(migrate_logs()) 