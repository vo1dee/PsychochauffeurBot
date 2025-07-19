import pytest
import asyncio
from modules.caching_system import (
    MemoryCache, CacheConfig, CacheManager, cached, CacheBackend, CachePolicy
)
from modules.types import CacheEntry
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from modules.handlers import basic_commands

@pytest.mark.asyncio
async def test_memory_cache_basic_operations():
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=3, default_ttl=2)
    cache = MemoryCache(config)
    await cache.set("a", 1)
    await cache.set("b", 2)
    assert await cache.get("a") == 1
    assert await cache.get("b") == 2
    assert await cache.get("c") is None
    assert await cache.exists("a")
    assert not await cache.exists("c")
    await cache.delete("a")
    assert not await cache.exists("a")
    await cache.clear()
    assert not await cache.exists("b")

@pytest.mark.asyncio
async def test_memory_cache_eviction():
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=2, default_ttl=10)
    cache = MemoryCache(config)
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)  # Should evict 'a'
    assert await cache.get("a") is None
    assert await cache.get("b") == 2
    assert await cache.get("c") == 3

@pytest.mark.asyncio
async def test_memory_cache_ttl_expiry():
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=2, default_ttl=1)
    cache = MemoryCache(config)
    await cache.set("a", 1, ttl=1)
    await asyncio.sleep(1.2)
    assert await cache.get("a") is None

@pytest.mark.asyncio
async def test_memory_cache_stats():
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=2, default_ttl=10)
    cache = MemoryCache(config)
    await cache.set("a", 1)
    await cache.get("a")
    await cache.get("b")
    stats = cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.sets == 1
    assert stats.size == 1
    assert stats.hit_rate == 0.5

@pytest.mark.asyncio
async def test_cache_manager_get_or_create():
    manager = CacheManager()
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=2)
    cache = manager.get_or_create_cache("test", config)
    assert cache is manager.get_cache("test")
    await cache.set("x", 42)
    assert await cache.get("x") == 42
    await manager.clear_all()
    assert await cache.get("x") is None

@pytest.mark.asyncio
async def test_cached_decorator_basic():
    manager = CacheManager()
    config = CacheConfig(backend=CacheBackend.MEMORY, policy=CachePolicy.LRU, max_size=2)
    manager.get_or_create_cache("decorator_test", config)
    calls = {"count": 0}
    @cached(cache_name="decorator_test", ttl=2)
    async def add(x, y):
        calls["count"] += 1
        return x + y
    result1 = await add(1, 2)
    result2 = await add(1, 2)
    assert result1 == 3
    assert result2 == 3
    assert calls["count"] == 1  # Cached
    await asyncio.sleep(2.1)
    result3 = await add(1, 2)
    assert result3 == 3
    assert calls["count"] == 2  # Cache expired 

@pytest.mark.asyncio
async def test_start_command_replies_and_logs():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 123
    context = MagicMock()
    with patch("modules.handlers.basic_commands.general_logger.info") as mock_log:
        await basic_commands.start_command(update, context)
        assert update.message.reply_text.await_count >= 2  # Welcome and button
        mock_log.assert_called_with("Handled /start command for user 123")

@pytest.mark.asyncio
async def test_help_command_calls_start():
    update = MagicMock()
    context = MagicMock()
    with patch("modules.handlers.basic_commands.start_command", new=AsyncMock()) as mock_start:
        await basic_commands.help_command(update, context)
        mock_start.assert_awaited_once_with(update, context)

@pytest.mark.asyncio
async def test_ping_command_replies_and_logs():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 456
    context = MagicMock()
    with patch("modules.handlers.basic_commands.general_logger.info") as mock_log:
        await basic_commands.ping_command(update, context)
        update.message.reply_text.assert_awaited_with("Pong! 🏓")
        mock_log.assert_called_with("Handled /ping command for user 456") 