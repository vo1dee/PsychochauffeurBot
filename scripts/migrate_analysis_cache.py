"""
Migration script to create the analysis_cache table for /analyze caching.
Run this once after updating the codebase.
"""
import asyncio
from modules.database import Database

SQL = """
CREATE TABLE IF NOT EXISTS analysis_cache (
    chat_id BIGINT NOT NULL,
    time_period TEXT NOT NULL,
    message_content_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (chat_id, time_period, message_content_hash)
);
"""

async def main() -> None:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SQL)
    print("analysis_cache table created (if not exists)")
    await Database.close()

if __name__ == "__main__":
    asyncio.run(main())
