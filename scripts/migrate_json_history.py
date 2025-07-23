import asyncio
import json
from datetime import datetime
from typing import Any, Optional
import pytz
import re
from modules.database import Database
from modules.const import KYIV_TZ

def extract_numeric_user_id(user_id_field: Any) -> Optional[int]:
    # Handles 'user15671125' -> 15671125, or returns int if already numeric
    if isinstance(user_id_field, int):
        return user_id_field
    match = re.search(r'(\d+)$', str(user_id_field))
    return int(match.group(1)) if match else None

async def migrate_json_history(json_file_path: str, json_chat_id: int, db_chat_id: int) -> None:
    """
    Migrate chat history from JSON file to PostgreSQL database.
    Only migrates text messages for the specific target chat.
    Uses real Telegram user_id extracted from 'from_id' and 'actor_id'.
    
    Args:
        json_file_path: Path to the JSON file containing chat history
        json_chat_id: Chat ID as it appears in the JSON file
        db_chat_id: Chat ID as it should appear in the database
    """
    try:
        # Initialize the database
        await Database.initialize()
        print("Database initialized successfully!")

        # Load JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Verify we're processing the correct chat
        if data['id'] != json_chat_id:
            raise ValueError(f"JSON file contains data for chat {data['id']}, but we expect chat {json_chat_id}")

        # Track statistics
        total_messages = 0
        skipped_messages = 0
        error_messages = 0

        # Get database pool
        pool = await Database.get_pool()
        
        # First, save chat info
        chat_type = data['type']
        chat_title = data['name']
        
        async with pool.acquire() as conn:
            # Save chat with the correct database chat ID
            await conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = $2, title = $3
            """, db_chat_id, chat_type, chat_title)
            
            # Process messages
            for msg in data['messages']:
                try:
                    # Get text content from text_entities
                    text = ""
                    if msg.get('text_entities'):
                        text = ''.join(entity.get('text', '') for entity in msg['text_entities'])
                    
                    # Skip if no text content
                    if not text:
                        skipped_messages += 1
                        continue

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(msg['date'].replace('Z', '+00:00'))
                    if timestamp.tzinfo is None:
                        timestamp = KYIV_TZ.localize(timestamp)

                    # Handle user info using real Telegram user_id
                    if msg['type'] == 'service':
                        user_id = extract_numeric_user_id(msg['actor_id'])
                        username = msg['actor']
                    else:
                        user_id = extract_numeric_user_id(msg['from_id'])
                        username = msg['from']

                    if user_id is None:
                        skipped_messages += 1
                        continue

                    # Save user
                    await conn.execute("""
                        INSERT INTO users (user_id, first_name, username)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id) DO UPDATE
                        SET first_name = $2, username = $3
                    """, user_id, username, username)

                    # Check if it's a command
                    is_command = text.startswith('/') if text else False
                    command_name = text.split()[0][1:] if is_command else None

                    # Save message with the correct database chat ID
                    await conn.execute("""
                        INSERT INTO messages (
                            message_id, chat_id, user_id, timestamp, text,
                            is_command, command_name, is_gpt_reply,
                            replied_to_message_id
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (chat_id, message_id) DO NOTHING
                    """,
                        msg['id'],
                        db_chat_id,  # Use the database chat ID
                        user_id,
                        timestamp,
                        text,
                        is_command,
                        command_name,
                        False,  # is_gpt_reply
                        msg.get('reply_to_message_id')
                    )
                    
                    total_messages += 1

                except Exception as e:
                    print(f"Error processing message: {e}")
                    error_messages += 1
                    continue

        print(f"\nMigration Summary:")
        print(f"Total text messages processed: {total_messages}")
        print(f"Skipped messages: {skipped_messages}")
        print(f"Error messages: {error_messages}")

    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python migrate_json_history.py <path_to_json_file> <json_chat_id> <db_chat_id>")
        print("Example: python migrate_json_history.py chat_history.json 2096701815 -1002096701815")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    json_chat_id = int(sys.argv[2])
    db_chat_id = int(sys.argv[3])
    
    asyncio.run(migrate_json_history(json_file_path, json_chat_id, db_chat_id)) 