import asyncio
from modules.database import Database

async def initialize_database():
    """
    Initialize the PostgreSQL database by creating tables.
    This is a one-time setup function.
    """
    try:
        # Initialize the database (creates tables if they don't exist)
        await Database.initialize()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(initialize_database()) 