#!/usr/bin/env python3
"""
Script to migrate data from an existing PostgreSQL database to Docker database.

This script helps you:
1. Check if your old database is accessible
2. Backup your old database
3. Restore it to the Docker database
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import Database, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


async def check_old_database(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str
) -> Optional[asyncpg.Connection]:
    """Check if old database is accessible."""
    try:
        print(f"Attempting to connect to old database: {user}@{host}:{port}/{database}")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        print("✅ Successfully connected to old database!")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to old database: {e}")
        return None


async def get_message_count(conn: asyncpg.Connection, chat_id: Optional[int] = None) -> int:
    """Get total message count from database."""
    if chat_id:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE chat_id = $1", chat_id
        )
    else:
        count = await conn.fetchval("SELECT COUNT(*) FROM messages")
    return count


async def get_date_range(conn: asyncpg.Connection) -> tuple:
    """Get date range of messages in database."""
    row = await conn.fetchrow("""
        SELECT 
            MIN(timestamp) as min_date,
            MAX(timestamp) as max_date,
            COUNT(*) as total
        FROM messages
    """)
    return row['min_date'], row['max_date'], row['total']


async def backup_database(
    old_host: str,
    old_port: int,
    old_database: str,
    old_user: str,
    old_password: str,
    backup_file: str
) -> bool:
    """Backup database using pg_dump."""
    import subprocess
    
    # Build connection string
    conn_str = f"postgresql://{old_user}:{old_password}@{old_host}:{old_port}/{old_database}"
    
    try:
        print(f"Creating backup to {backup_file}...")
        result = subprocess.run(
            ["pg_dump", "-Fc", "-f", backup_file, conn_str],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Backup created successfully: {backup_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Backup failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ pg_dump not found. Please install PostgreSQL client tools.")
        return False


async def restore_to_docker(backup_file: str) -> bool:
    """Restore backup to Docker database."""
    import subprocess
    
    # Docker database connection
    docker_host = "localhost"
    docker_port = 5432
    docker_database = "telegram_bot"
    docker_user = "postgres"
    docker_password = "psychochauffeur"
    
    conn_str = f"postgresql://{docker_user}:{docker_password}@{docker_host}:{docker_port}/{docker_database}"
    
    try:
        print(f"Restoring backup to Docker database...")
        result = subprocess.run(
            ["pg_restore", "-d", conn_str, "-c", backup_file],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Backup restored successfully to Docker database!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Restore failed: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ pg_restore not found. Please install PostgreSQL client tools.")
        return False


async def migrate_data_direct(
    old_conn: asyncpg.Connection,
    docker_host: str = "localhost",
    docker_port: int = 5432,
    docker_database: str = "telegram_bot",
    docker_user: str = "postgres",
    docker_password: str = "psychochauffeur"
) -> bool:
    """Directly migrate data from old database to Docker database."""
    try:
        print("Connecting to Docker database...")
        docker_conn = await asyncpg.connect(
            host=docker_host,
            port=docker_port,
            database=docker_database,
            user=docker_user,
            password=docker_password
        )
        print("✅ Connected to Docker database!")
        
        # Get data from old database
        print("Fetching data from old database...")
        
        # Migrate chats
        print("Migrating chats...")
        old_chats = await old_conn.fetch("SELECT * FROM chats")
        for chat in old_chats:
            await docker_conn.execute("""
                INSERT INTO chats (chat_id, chat_type, title, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (chat_id) DO UPDATE
                SET chat_type = EXCLUDED.chat_type,
                    title = EXCLUDED.title
            """, chat['chat_id'], chat['chat_type'], chat['title'], chat['created_at'])
        print(f"  Migrated {len(old_chats)} chats")
        
        # Migrate users
        print("Migrating users...")
        old_users = await old_conn.fetch("SELECT * FROM users")
        for user in old_users:
            await docker_conn.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, is_bot, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) DO UPDATE
                SET first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    username = EXCLUDED.username,
                    is_bot = EXCLUDED.is_bot
            """, user['user_id'], user['first_name'], user['last_name'],
                user['username'], user['is_bot'], user['created_at'])
        print(f"  Migrated {len(old_users)} users")
        
        # Migrate messages
        print("Migrating messages...")
        batch_size = 1000
        offset = 0
        total_migrated = 0
        
        while True:
            old_messages = await old_conn.fetch("""
                SELECT * FROM messages
                ORDER BY timestamp
                LIMIT $1 OFFSET $2
            """, batch_size, offset)
            
            if not old_messages:
                break
            
            for msg in old_messages:
                await docker_conn.execute("""
                    INSERT INTO messages (
                        message_id, chat_id, user_id, timestamp, text,
                        is_command, command_name, is_gpt_reply,
                        replied_to_message_id, gpt_context_message_ids,
                        raw_telegram_message
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (chat_id, message_id) DO NOTHING
                """,
                    msg['message_id'], msg['chat_id'], msg['user_id'],
                    msg['timestamp'], msg['text'], msg['is_command'],
                    msg['command_name'], msg['is_gpt_reply'],
                    msg['replied_to_message_id'], msg['gpt_context_message_ids'],
                    msg['raw_telegram_message']
                )
            
            total_migrated += len(old_messages)
            offset += batch_size
            print(f"  Migrated {total_migrated} messages...", end='\r')
        
        print(f"\n✅ Migrated {total_migrated} messages total")
        
        await docker_conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main migration function."""
    print("=" * 60)
    print("Database Migration Tool")
    print("=" * 60)
    print()
    
    # Get old database connection details
    print("Please provide your OLD database connection details:")
    print("(Press Enter to use defaults from .env or current config)")
    print()
    
    old_host = input("Old DB Host [default: check current DB_HOST]: ").strip() or None
    old_port = input("Old DB Port [default: 5432]: ").strip() or "5432"
    old_database = input("Old DB Name [default: telegram_bot]: ").strip() or "telegram_bot"
    old_user = input("Old DB User [default: postgres]: ").strip() or "postgres"
    old_password = input("Old DB Password [default: from env]: ").strip() or DB_PASSWORD
    
    # Use current config if not provided
    if old_host is None:
        # Try to detect if there's another PostgreSQL instance
        print("\nChecking for existing database...")
        # Try connecting to current config first
        old_host = DB_HOST
        old_port = int(DB_PORT)
        old_database = DB_NAME
        old_user = DB_USER
        old_password = old_password or DB_PASSWORD
    
    # Check old database
    old_conn = await check_old_database(
        old_host, int(old_port), old_database, old_user, old_password
    )
    
    if not old_conn:
        print("\n❌ Cannot connect to old database.")
        print("Please check your connection details and try again.")
        return
    
    # Get statistics
    print("\n" + "=" * 60)
    print("Old Database Statistics:")
    print("=" * 60)
    
    total_messages = await get_message_count(old_conn)
    min_date, max_date, _ = await get_date_range(old_conn)
    
    print(f"Total messages: {total_messages:,}")
    if min_date and max_date:
        print(f"Date range: {min_date} to {max_date}")
    
    # Check Docker database
    print("\n" + "=" * 60)
    print("Checking Docker database...")
    print("=" * 60)
    
    docker_conn = await check_old_database(
        "localhost", 5432, "telegram_bot", "postgres", "psychochauffeur"
    )
    
    if docker_conn:
        docker_messages = await get_message_count(docker_conn)
        print(f"Docker database has {docker_messages:,} messages")
        await docker_conn.close()
    
    # Ask what to do
    print("\n" + "=" * 60)
    print("Migration Options:")
    print("=" * 60)
    print("1. Migrate data directly (recommended)")
    print("2. Create backup file")
    print("3. Exit")
    
    choice = input("\nChoose an option [1-3]: ").strip()
    
    if choice == "1":
        print("\nStarting direct migration...")
        success = await migrate_data_direct(old_conn)
        if success:
            print("\n✅ Migration completed successfully!")
        else:
            print("\n❌ Migration failed. Please check the errors above.")
    elif choice == "2":
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"
        if await backup_database(old_host, int(old_port), old_database, old_user, old_password, backup_file):
            print(f"\n✅ Backup created: {backup_file}")
            restore = input("\nRestore to Docker database now? [y/N]: ").strip().lower()
            if restore == 'y':
                await restore_to_docker(backup_file)
    else:
        print("Exiting...")
    
    await old_conn.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
