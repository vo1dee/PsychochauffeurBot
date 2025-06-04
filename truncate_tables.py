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
            # Truncate all tables with CASCADE
            print("Truncating all tables...")
            await conn.execute("TRUNCATE TABLE messages, users, chats CASCADE;")
            
            print("\nAll tables have been truncated successfully!")
            
    except Exception as e:
        print(f"Error during truncation: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(truncate_tables()) 