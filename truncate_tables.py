import asyncio
from modules.database import Database

async def truncate_tables():
    """
    Truncate all tables in the database to prepare for a fresh migration.
    """
    try:
        # Initialize the database
        await Database.initialize()
        print("Database initialized successfully!")

        # Get database pool
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Disable foreign key checks temporarily
            await conn.execute("SET session_replication_role = 'replica';")
            
            # Truncate tables in correct order (child tables first)
            print("Truncating messages table...")
            await conn.execute("TRUNCATE TABLE messages;")
            
            print("Truncating users table...")
            await conn.execute("TRUNCATE TABLE users;")
            
            print("Truncating chats table...")
            await conn.execute("TRUNCATE TABLE chats;")
            
            # Re-enable foreign key checks
            await conn.execute("SET session_replication_role = 'origin';")
            
            print("\nAll tables have been truncated successfully!")
            
    except Exception as e:
        print(f"Error during truncation: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(truncate_tables()) 