"""
Lightweight event tracking for bot actions (url_modification, video_download).
"""

from typing import Optional

from modules.logger import error_logger


async def record_bot_event(event_type: str, chat_id: int, user_id: Optional[int] = None) -> None:
    """
    Record a bot event to the bot_events table.

    Args:
        event_type: Event type string ('url_modification' or 'video_download')
        chat_id: Telegram chat ID
        user_id: Telegram user ID (optional)
    """
    try:
        from modules.database import Database
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bot_events (event_type, chat_id, user_id) VALUES ($1, $2, $3)",
                event_type, chat_id, user_id
            )
    except Exception as e:
        error_logger.debug(f"Failed to record bot event '{event_type}': {e}")
