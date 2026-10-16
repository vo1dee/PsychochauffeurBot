"""Saved /weather cities, shared with the weather Mini App.

Each user has a home city, which every `/weather <city>` and the Mini App
update. `/weather <city>` in a group also stores an override for that group.
Lookups prefer the group override, then the home city.

The data lives in Cloudflare D1 (through the Worker API) so the Mini App can
read and write it too. When D1 is not configured or fails, the legacy CSV file
is used instead.
"""

from typing import Optional

from modules import file_manager, utils
from modules.d1_api_client import D1ApiError, get_d1_api_client
from modules.logger import error_logger, general_logger


def _normalize_city(city: str) -> str:
    city = city.strip()
    return "Kyiv" if city.lower() == "kiev" else city


def _group_chat_id(user_id: int, chat_id: Optional[int]) -> Optional[int]:
    """Return chat_id for a group chat, None for a private chat (its id equals the user id)."""
    if chat_id is None or chat_id == user_id or chat_id == 0:
        return None
    return chat_id


async def save_user_location(user_id: int, city: str, chat_id: Optional[int] = None) -> None:
    """Save the user's home city, plus a group override when called from a group."""
    city = _normalize_city(city)
    if not city:
        return
    group_id = _group_chat_id(user_id, chat_id)

    client = await get_d1_api_client(require_dual_write=False)
    if client is not None:
        try:
            await client.set_user_location(user_id, city)
            if group_id is not None:
                await client.set_user_location(user_id, city, chat_id=group_id)
            return
        except D1ApiError as e:
            error_logger.error(f"Saving location to D1 failed, using CSV fallback: {e}")

    file_manager.save_user_location(user_id, city)
    if group_id is not None:
        file_manager.save_user_location(user_id, city, group_id)


async def get_last_used_city(user_id: int, chat_id: Optional[int] = None) -> Optional[str]:
    """Return the group override, else the home city, else None."""
    group_id = _group_chat_id(user_id, chat_id)

    client = await get_d1_api_client(require_dual_write=False)
    if client is not None:
        try:
            return await client.get_user_location(user_id, group_id)
        except D1ApiError as e:
            error_logger.error(f"Reading location from D1 failed, using CSV fallback: {e}")

    city = utils.get_last_used_city(user_id, group_id if group_id is not None else chat_id)
    if city:
        general_logger.info(f"Using CSV location for user {user_id}")
    return city
