import asyncio
import sys
from modules.database import Database

async def truncate_tables(chat_id: int = None, delete_all: bool = False):
    """
    Truncate tables in the database.
    If chat_id is provided, only delete data for that specific chat.
    If delete_all is True, truncate all tables (requires explicit 'all' argument).
    
    Args:
        chat_id: Optional chat ID to delete data for a specific chat only
        delete_all: If True, truncate all tables (requires explicit 'all' argument)
    """
    try:
        # Initialize the database
        await Database.initialize()
        print("Database initialized successfully!")

        # Get database pool
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            if delete_all:
                # Truncate all tables with CASCADE
                print("Truncating all tables...")
                await conn.execute("TRUNCATE TABLE messages, users, chats CASCADE;")
                print("\nAll tables have been truncated successfully!")
            elif chat_id is not None:
                # Delete data for specific chat
                print(f"Deleting data for chat {chat_id}...")
                # First delete messages (they reference users and chats)
                await conn.execute("DELETE FROM messages WHERE chat_id = $1", chat_id)
                # Then delete the chat
                await conn.execute("DELETE FROM chats WHERE chat_id = $1", chat_id)
                # Note: We don't delete users as they might be used in other chats
                print(f"\nData for chat {chat_id} has been deleted successfully!")
            else:
                print("No action specified. Use 'all' to delete everything or provide a chat_id.")
                sys.exit(1)
            
    except Exception as e:
        print(f"Error during truncation: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python truncate_tables.py <chat_id|all>")
        print("Examples:")
        print("  python truncate_tables.py -1002096701815  # Delete specific chat")
        print("  python truncate_tables.py all            # Delete all data")
        sys.exit(1)
    
    arg = sys.argv[1]
    if arg.lower() == 'all':
        # Ask for confirmation before deleting everything
        confirm = input("WARNING: This will delete ALL data from the database. Are you sure? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled.")
            sys.exit(0)
        asyncio.run(truncate_tables(delete_all=True))
    else:
        try:
            chat_id = int(arg)
            asyncio.run(truncate_tables(chat_id=chat_id))
        except ValueError:
            print("Error: chat_id must be a number or 'all'")
            sys.exit(1) 