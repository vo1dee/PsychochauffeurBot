#!/usr/bin/env python3
import asyncio
from modules.database import Database

async def check_schema():
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # Get tables
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        
        for table in tables:
            table_name = table['table_name']
            print(f"\nTable: {table_name}")
            print("-" * 40)
            
            # Get columns for this table
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
            """, table_name)
            
            for col in columns:
                print(f"  {col['column_name']} ({col['data_type']}) {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
                if col['column_default']:
                    print(f"    DEFAULT: {col['column_default']}")

if __name__ == "__main__":
    asyncio.run(check_schema())
