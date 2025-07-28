import asyncio
import re
from datetime import datetime
import glob
import os
from modules.database import Database

async def migrate_logs() -> None:
    """
    Migrate chat logs from log files to PostgreSQL database.
    """
    try:
        # Initialize the database
        await Database.initialize()
        print("Database initialized successfully!")

        # Get all chat log files recursively
        log_files = []
        for root, dirs, files in os.walk('logs'):
            for file in files:
                if file.endswith('.log'):
                    log_files.append(os.path.join(root, file))
        
        print(f"Found {len(log_files)} log files")
        
        # Track statistics
        total_messages = 0
        skipped_messages = 0
        error_messages = 0
        
        for log_file in log_files:
            print(f"Processing {log_file}...")
            file_messages = 0
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Skip initialization messages
                    if "Chat logging system initialized" in line:
                        continue
                        
                    # Try old format first
                    # Format: timestamp - chat_logger - INFO - chat_id - chat_type - username - User message: text
                    old_match = re.match(r'(.+?) - chat_logger - INFO - (.+?) - (.+?) - (.+?) - User message: (.+)', line)
                    
                    # Try new format if old format doesn't match
                    # Format: timestamp +0300 - chat - INFO - Ctx:[chat_id][chat_type][username] - text
                    new_match = re.match(r'(.+?) \+0300 - chat - INFO - Ctx:\[(.+?)\]\[(.+?)\]\[(.+?)\] - (.+)', line)
                    
                    if old_match:
                        timestamp_str, chat_id, chat_type, username, text = old_match.groups()
                    elif new_match:
                        timestamp_str, chat_id, chat_type, username, text = new_match.groups()
                    else:
                        skipped_messages += 1
                        continue
                    
                    # Convert timestamp
                    try:
                        # Try parsing with milliseconds first
                        timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S,%f')
                    except ValueError:
                        try:
                            # Try parsing with timezone offset
                            timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S +%f')
                        except ValueError:
                            try:
                                # Try parsing without milliseconds
                                timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                print(f"Could not parse timestamp: {timestamp_str}")
                                error_messages += 1
                                continue
                    
                    # Clean up values
                    chat_id = chat_id.strip()
                    if chat_id == 'N/A':
                        skipped_messages += 1
                        continue
                        
                    chat_type = chat_type.strip()
                    if chat_type == 'Unknown':
                        skipped_messages += 1
                        continue
                        
                    username = username.strip()
                    if username == 'Unknown':
                        skipped_messages += 1
                        continue
                    
                    try:
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
                            
                            # Save user with a unique user_id based on username
                            user_id = abs(hash(username)) % (2**63)  # Generate a unique user_id from username
                            await conn.execute("""
                                INSERT INTO users (user_id, first_name, username)
                                VALUES ($1, $2, $3)
                                ON CONFLICT (user_id) DO UPDATE
                                SET first_name = $2, username = $3
                            """, user_id, username, username)
                            
                            # Save message
                            await conn.execute("""
                                INSERT INTO messages (
                                    message_id, chat_id, user_id, timestamp, text,
                                    is_command, command_name, is_gpt_reply
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                ON CONFLICT (chat_id, message_id) DO NOTHING
                            """,
                                int(timestamp.timestamp() * 1000),  # Use actual message timestamp for message_id
                                int(chat_id),
                                user_id,  # Use the generated user_id
                                timestamp,
                                text.strip(),
                                False,
                                None,
                                False
                            )
                            file_messages += 1
                            total_messages += 1
                            
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        error_messages += 1
                        continue
            
            print(f"Finished processing {log_file} - {file_messages} messages")
            
        print(f"\nMigration Summary:")
        print(f"Total messages processed: {total_messages}")
        print(f"Skipped messages: {skipped_messages}")
        print(f"Error messages: {error_messages}")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(migrate_logs()) 