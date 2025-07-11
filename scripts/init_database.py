#!/usr/bin/env python3
"""
Script to manually initialize the database tables.
Run this when you've updated the database schema.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import Database

async def main():
    """Initialize the database tables."""
    try:
        print("Initializing database...")
        await Database.initialize()
        print("✅ Database initialized successfully!")
        
        # Test the connection
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Check if tables exist
            result = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('chats', 'users', 'messages', 'analysis_cache')
                ORDER BY table_name
            """)
            
            print(f"✅ Found {len(result)} tables:")
            for row in result:
                print(f"   - {row['table_name']}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)
    finally:
        await Database.close()

if __name__ == "__main__":
    asyncio.run(main()) 