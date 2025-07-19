import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from telegram import Chat, User, Message
from modules.database import Database, DatabaseConnectionManager

@pytest.fixture
def mock_chat():
    return Chat(id=-1001234567890, type="supergroup", title="Test Chat")

@pytest.fixture
def mock_user():
    return User(id=123456789, first_name="Test", last_name="User", username="testuser", is_bot=False)

@pytest.fixture
def mock_message(mock_chat, mock_user):
    msg = MagicMock(spec=Message)
    msg.message_id = 1
    msg.chat = mock_chat
    msg.from_user = mock_user
    msg.text = "/start"
    msg.date = asyncio.get_event_loop().time()
    msg.reply_to_message = None
    msg.to_dict.return_value = {"message_id": 1, "text": "/start"}
    return msg

@pytest.mark.asyncio
async def test_get_connection_manager_singleton():
    manager1 = Database.get_connection_manager()
    manager2 = Database.get_connection_manager()
    assert manager1 is manager2

@pytest.mark.asyncio
async def test_save_chat_info_caching(monkeypatch, mock_chat):
    manager = Database.get_connection_manager()
    manager._cache_manager.set(f"chat:{mock_chat.id}", {"title": mock_chat.title}, ttl=3600)
    with patch.object(manager, 'get_connection') as mock_conn:
        await Database.save_chat_info(mock_chat)
        mock_conn.assert_not_called()  # Should hit cache

@pytest.mark.asyncio
async def test_save_user_info_caching(monkeypatch, mock_user):
    manager = Database.get_connection_manager()
    manager._cache_manager.set(f"user:{mock_user.id}", {"username": mock_user.username, "first_name": mock_user.first_name}, ttl=3600)
    with patch.object(manager, 'get_connection') as mock_conn:
        await Database.save_user_info(mock_user)
        mock_conn.assert_not_called()  # Should hit cache

@pytest.mark.asyncio
async def test_save_message_calls_save_chat_and_user(monkeypatch, mock_message):
    with patch.object(Database, 'save_chat_info', new=AsyncMock()) as mock_save_chat, \
         patch.object(Database, 'save_user_info', new=AsyncMock()) as mock_save_user, \
         patch.object(Database.get_connection_manager(), 'get_connection') as mock_conn:
        mock_conn.return_value.__aenter__.return_value = AsyncMock()
        await Database.save_message(mock_message)
        mock_save_chat.assert_awaited_once()
        mock_save_user.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_analysis_cache_cache_hit(monkeypatch):
    manager = Database.get_connection_manager()
    key = "analysis:1:today:hash"
    manager._cache_manager.set(key, "cached_result", ttl=100)
    result = await Database.get_analysis_cache(1, "today", "hash", 100)
    assert result == "cached_result"

@pytest.mark.asyncio
async def test_set_analysis_cache_sets_cache(monkeypatch):
    manager = Database.get_connection_manager()
    with patch.object(manager, 'get_connection') as mock_conn:
        mock_conn.return_value.__aenter__.return_value = AsyncMock()
        await Database.set_analysis_cache(1, "today", "hash", "result")
        assert manager._cache_manager.get("analysis:1:today:hash") == "result"

@pytest.mark.asyncio
async def test_get_recent_messages_cache(monkeypatch):
    manager = Database.get_connection_manager()
    key = "recent_messages:1:10:True"
    manager._cache_manager.set(key, [{"message_id": 1}], ttl=100)
    result = await Database.get_recent_messages(1, limit=10, include_commands=True)
    assert result == [{"message_id": 1}]

@pytest.mark.asyncio
async def test_get_message_count_cache(monkeypatch):
    manager = Database.get_connection_manager()
    key = "msg_count:1:None:None:None"
    manager._cache_manager.set(key, 5, ttl=100)
    result = await Database.get_message_count(1)
    assert result == 5

@pytest.mark.asyncio
async def test_error_handling_on_db_failure(monkeypatch, mock_chat):
    manager = Database.get_connection_manager()
    manager._cache_manager.delete(f"chat:{mock_chat.id}")
    with patch.object(manager, 'get_connection', side_effect=Exception("DB fail")):
        result = await Database.save_chat_info(mock_chat)
        assert result is None