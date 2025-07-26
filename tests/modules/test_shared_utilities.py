"""
Comprehensive tests for the shared utilities module.

This module tests all utility functions, helpers, and classes in the shared_utilities module
to improve test coverage and ensure reliability.
"""

import asyncio
import hashlib
import pytest
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from telegram import Update, User, Chat, InlineKeyboardMarkup, InlineKeyboardButton

from modules.shared_utilities import (
    SingletonMeta, BaseService, AsyncContextManager, RateLimiter, CircuitBreaker,
    RetryManager, CacheManager, ValidationMixin, TextProcessor, HashGenerator,
    TelegramHelpers, PerformanceMonitor, async_retry, measure_performance,
    rate_limit, performance_monitor, text_processor, hash_generator, telegram_helpers
)
from modules.types import CacheEntry, PerformanceMetric, ValidationResult


class TestSingletonMeta:
    """Test the singleton metaclass."""
    
    def test_singleton_creates_single_instance(self):
        """Test that singleton creates only one instance."""
        class TestSingleton(metaclass=SingletonMeta):
            def __init__(self, value: int):
                self.value = value
        
        instance1 = TestSingleton(1)
        instance2 = TestSingleton(2)
        
        assert instance1 is instance2
        assert instance1.value == 1  # First instance value is preserved
    
    def test_singleton_different_classes(self):
        """Test that different singleton classes have separate instances."""
        class SingletonA(metaclass=SingletonMeta):
            pass
        
        class SingletonB(metaclass=SingletonMeta):
            pass
        
        instance_a = SingletonA()
        instance_b = SingletonB()
        
        assert instance_a is not instance_b
        assert type(instance_a) != type(instance_b)


class TestBaseService:
    """Test the base service class."""
    
    class ConcreteService(BaseService):
        """Concrete implementation for testing."""
        
        def __init__(self, name: str):
            super().__init__(name)
            self.init_called = False
            self.start_called = False
            self.stop_called = False
        
        async def initialize(self) -> None:
            self.init_called = True
            self._initialized = True
        
        async def start(self) -> None:
            self.start_called = True
            self._running = True
            self._start_time = datetime.now()
        
        async def stop(self) -> None:
            self.stop_called = True
            self._running = False
    
    @pytest.fixture
    def service(self):
        """Create a test service instance."""
        return self.ConcreteService("test_service")
    
    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.name == "test_service"
        assert not service.is_initialized()
        assert not service.is_running()
        assert service.get_uptime() is None
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, service):
        """Test complete service lifecycle."""
        # Initialize
        await service.initialize()
        assert service.init_called
        assert service.is_initialized()
        assert not service.is_running()
        
        # Start
        await service.start()
        assert service.start_called
        assert service.is_running()
        assert service.get_uptime() is not None
        
        # Health check
        assert await service.health_check()
        
        # Stop
        await service.stop()
        assert service.stop_called
        assert not service.is_running()
    
    @pytest.mark.asyncio
    async def test_service_health_check_states(self, service):
        """Test health check in different states."""
        # Not initialized
        assert not await service.health_check()
        
        # Initialized but not running
        await service.initialize()
        assert not await service.health_check()
        
        # Running
        await service.start()
        assert await service.health_check()


class TestAsyncContextManager:
    """Test the async context manager base class."""
    
    class ConcreteAsyncContextManager(AsyncContextManager[str]):
        """Concrete implementation for testing."""
        
        def __init__(self):
            self.setup_called = False
            self.cleanup_called = False
            self.value = "test_value"
        
        async def setup(self) -> None:
            self.setup_called = True
        
        async def cleanup(self) -> None:
            self.cleanup_called = True
    
    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """Test async context manager lifecycle."""
        manager = self.ConcreteAsyncContextManager()
        
        async with manager as ctx:
            assert manager.setup_called
            assert not manager.cleanup_called
            assert ctx is manager
        
        assert manager.cleanup_called
    
    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self):
        """Test context manager handles exceptions properly."""
        manager = self.ConcreteAsyncContextManager()
        
        with pytest.raises(ValueError):
            async with manager:
                assert manager.setup_called
                raise ValueError("Test exception")
        
        assert manager.cleanup_called


class TestRateLimiter:
    """Test the rate limiter class."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        return RateLimiter(max_requests=3, time_window=1)
    
    def test_rate_limiter_allows_requests_under_limit(self, rate_limiter):
        """Test that requests under limit are allowed."""
        key = "test_key"
        
        assert rate_limiter.is_allowed(key)
        assert rate_limiter.is_allowed(key)
        assert rate_limiter.is_allowed(key)
    
    def test_rate_limiter_blocks_requests_over_limit(self, rate_limiter):
        """Test that requests over limit are blocked."""
        key = "test_key"
        
        # Use up the limit
        for _ in range(3):
            assert rate_limiter.is_allowed(key)
        
        # Next request should be blocked
        assert not rate_limiter.is_allowed(key)
    
    def test_rate_limiter_different_keys_independent(self, rate_limiter):
        """Test that different keys have independent limits."""
        key1 = "key1"
        key2 = "key2"
        
        # Use up limit for key1
        for _ in range(3):
            assert rate_limiter.is_allowed(key1)
        
        # key2 should still be allowed
        assert rate_limiter.is_allowed(key2)
        assert not rate_limiter.is_allowed(key1)
    
    def test_rate_limiter_reset_time(self, rate_limiter):
        """Test reset time calculation."""
        key = "test_key"
        
        # Use up the limit
        for _ in range(3):
            rate_limiter.is_allowed(key)
        
        reset_time = rate_limiter.get_reset_time(key)
        assert reset_time is not None
        assert 0 <= reset_time <= 1
    
    def test_rate_limiter_cleanup_old_requests(self, rate_limiter):
        """Test that old requests are cleaned up."""
        key = "test_key"
        
        # Mock time to simulate passage of time
        with patch('time.time') as mock_time:
            mock_time.return_value = 0
            
            # Use up the limit
            for _ in range(3):
                assert rate_limiter.is_allowed(key)
            
            # Should be blocked
            assert not rate_limiter.is_allowed(key)
            
            # Advance time beyond window
            mock_time.return_value = 2
            
            # Should be allowed again
            assert rate_limiter.is_allowed(key)


class TestCircuitBreaker:
    """Test the circuit breaker class."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state."""
        @circuit_breaker
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
        assert circuit_breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures."""
        @circuit_breaker
        async def failing_function():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            await failing_function()
        assert circuit_breaker.state == "closed"
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await failing_function()
        assert circuit_breaker.state == "open"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self, circuit_breaker):
        """Test circuit breaker blocks calls when open."""
        @circuit_breaker
        async def failing_function():
            raise ValueError("Test error")
        
        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await failing_function()
        
        # Should now block with circuit breaker exception
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await failing_function()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through half-open state."""
        @circuit_breaker
        async def test_function(should_fail=True):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await test_function()
        
        assert circuit_breaker.state == "open"
        
        # Wait for recovery timeout to pass
        await asyncio.sleep(1.1)  # Wait longer than recovery_timeout (1 second)
        
        # Should attempt reset and succeed
        result = await test_function(should_fail=False)
        assert result == "success"
        assert circuit_breaker.state == "closed"


class TestRetryManager:
    """Test the retry manager class."""
    
    @pytest.fixture
    def retry_manager(self):
        """Create a retry manager for testing."""
        return RetryManager(max_retries=2, base_delay=0.1)
    
    @pytest.mark.asyncio
    async def test_retry_manager_success_first_attempt(self, retry_manager):
        """Test successful execution on first attempt."""
        async def success_function():
            return "success"
        
        result = await retry_manager.execute(success_function)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_manager_success_after_retries(self, retry_manager):
        """Test successful execution after retries."""
        call_count = 0
        
        async def eventually_success_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await retry_manager.execute(eventually_success_function)
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_manager_exhausts_retries(self, retry_manager):
        """Test that retry manager exhausts retries and raises last exception."""
        async def always_fail_function():
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            await retry_manager.execute(always_fail_function)
    
    @pytest.mark.asyncio
    async def test_retry_manager_exponential_backoff(self):
        """Test exponential backoff timing."""
        retry_manager = RetryManager(max_retries=2, base_delay=0.1, exponential_base=2.0)
        
        call_times = []
        
        async def failing_function():
            call_times.append(time.time())
            raise ValueError("Test error")
        
        start_time = time.time()
        with pytest.raises(ValueError):
            await retry_manager.execute(failing_function)
        
        # Should have 3 calls (initial + 2 retries)
        assert len(call_times) == 3
        
        # Check approximate timing (allowing for some variance)
        assert call_times[1] - call_times[0] >= 0.1  # First retry delay
        assert call_times[2] - call_times[1] >= 0.2  # Second retry delay (exponential)


class TestCacheManager:
    """Test the cache manager class."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create a cache manager for testing."""
        return CacheManager[str](default_ttl=1)
    
    def test_cache_set_and_get(self, cache_manager):
        """Test basic cache set and get operations."""
        cache_manager.set("key1", "value1")
        
        result = cache_manager.get("key1")
        assert result == "value1"
    
    def test_cache_get_nonexistent_key(self, cache_manager):
        """Test getting non-existent key returns None."""
        result = cache_manager.get("nonexistent")
        assert result is None
    
    def test_cache_ttl_expiration(self, cache_manager):
        """Test that cache entries expire after TTL."""
        # Set with very short TTL and wait
        cache_manager.set("key1", "value1", ttl=0.001)  # Very short TTL
        
        # Wait for expiration
        time.sleep(0.002)
        
        # Should be expired
        result = cache_manager.get("key1")
        assert result is None
    
    def test_cache_delete(self, cache_manager):
        """Test cache deletion."""
        cache_manager.set("key1", "value1")
        
        # Verify it exists
        assert cache_manager.get("key1") == "value1"
        
        # Delete and verify
        assert cache_manager.delete("key1") is True
        assert cache_manager.get("key1") is None
        
        # Delete non-existent key
        assert cache_manager.delete("nonexistent") is False
    
    def test_cache_clear(self, cache_manager):
        """Test clearing all cache entries."""
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        
        cache_manager.clear()
        
        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") is None
    
    def test_cache_cleanup_expired(self, cache_manager):
        """Test cleanup of expired entries."""
        # Set entries with different TTLs
        cache_manager.set("key1", "value1", ttl=0.001)  # Very short TTL
        cache_manager.set("key2", "value2", ttl=10)  # Long TTL
        
        # Wait for first entry to expire
        time.sleep(0.002)
        
        expired_count = cache_manager.cleanup_expired()
        
        assert expired_count == 1
        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") == "value2"


class TestValidationMixin:
    """Test the validation mixin class."""
    
    def test_validate_user_id_valid(self):
        """Test valid user ID validation."""
        result, message = ValidationMixin.validate_user_id(12345)
        assert result is True
        assert message is None
    
    def test_validate_user_id_invalid(self):
        """Test invalid user ID validation."""
        # Test negative ID
        result, message = ValidationMixin.validate_user_id(-1)
        assert result is False
        assert "Invalid user ID" in message
        
        # Test zero ID
        result, message = ValidationMixin.validate_user_id(0)
        assert result is False
        assert "Invalid user ID" in message
        
        # Test non-integer
        result, message = ValidationMixin.validate_user_id("not_int")
        assert result is False
        assert "Invalid user ID" in message
    
    def test_validate_chat_id_valid(self):
        """Test valid chat ID validation."""
        result, message = ValidationMixin.validate_chat_id(-12345)
        assert result is True
        assert message is None
    
    def test_validate_chat_id_invalid(self):
        """Test invalid chat ID validation."""
        result, message = ValidationMixin.validate_chat_id("not_int")
        assert result is False
        assert "Invalid chat ID" in message
    
    def test_validate_text_length_valid(self):
        """Test valid text length validation."""
        result, message = ValidationMixin.validate_text_length("Hello world")
        assert result is True
        assert message is None
    
    def test_validate_text_length_invalid(self):
        """Test invalid text length validation."""
        # Test non-string
        result, message = ValidationMixin.validate_text_length(123)
        assert result is False
        assert "Text must be a string" in message
        
        # Test too long text
        long_text = "a" * 5000
        result, message = ValidationMixin.validate_text_length(long_text, max_length=100)
        assert result is False
        assert "Text too long" in message
    
    def test_validate_url_valid(self):
        """Test valid URL validation."""
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://sub.domain.com/path?param=value"
        ]
        
        for url in valid_urls:
            result, message = ValidationMixin.validate_url(url)
            assert result is True, f"URL {url} should be valid"
            assert message is None
    
    def test_validate_url_invalid(self):
        """Test invalid URL validation."""
        invalid_urls = [
            "not_a_url",
            "ftp://example.com",
            "https://",
            ""
        ]
        
        for url in invalid_urls:
            result, message = ValidationMixin.validate_url(url)
            assert result is False, f"URL {url} should be invalid"
            assert "Invalid URL format" in message


class TestTextProcessor:
    """Test the text processor utility class."""
    
    def test_extract_urls(self):
        """Test URL extraction from text."""
        text = "Check out https://example.com and http://test.org for more info"
        urls = TextProcessor.extract_urls(text)
        
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls
    
    def test_extract_urls_no_urls(self):
        """Test URL extraction from text with no URLs."""
        text = "This text has no URLs in it"
        urls = TextProcessor.extract_urls(text)
        
        assert len(urls) == 0
    
    def test_remove_urls(self):
        """Test URL removal from text."""
        text = "Check out https://example.com and http://test.org for more info"
        cleaned_text = TextProcessor.remove_urls(text)
        
        assert "https://example.com" not in cleaned_text
        assert "http://test.org" not in cleaned_text
        assert "Check out" in cleaned_text
        assert "for more info" in cleaned_text
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test invalid characters
        filename = 'file<>:"/\\|?*.txt'
        sanitized = TextProcessor.sanitize_filename(filename)
        
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert '"' not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized
        assert sanitized.endswith(".txt")
    
    def test_sanitize_filename_long(self):
        """Test sanitization of very long filenames."""
        long_name = "a" * 300 + ".txt"
        sanitized = TextProcessor.sanitize_filename(long_name)
        
        assert len(sanitized) <= 255
        assert sanitized.endswith(".txt")
    
    def test_truncate_text(self):
        """Test text truncation."""
        text = "This is a long text that needs to be truncated"
        truncated = TextProcessor.truncate_text(text, max_length=20)
        
        assert len(truncated) == 20
        assert truncated.endswith("...")
    
    def test_truncate_text_short(self):
        """Test truncation of text shorter than max length."""
        text = "Short text"
        truncated = TextProcessor.truncate_text(text, max_length=20)
        
        assert truncated == text
    
    def test_escape_markdown(self):
        """Test markdown character escaping."""
        text = "Text with *bold* and _italic_ and [link](url)"
        escaped = TextProcessor.escape_markdown(text)
        
        assert "\\*" in escaped
        assert "\\_" in escaped
        assert "\\[" in escaped
        assert "\\]" in escaped
        assert "\\(" in escaped
        assert "\\)" in escaped


class TestHashGenerator:
    """Test the hash generator utility class."""
    
    def test_md5_hash(self):
        """Test MD5 hash generation."""
        data = "test_data"
        hash_result = HashGenerator.md5_hash(data)
        
        expected = hashlib.md5(data.encode()).hexdigest()
        assert hash_result == expected
        assert len(hash_result) == 32
    
    def test_sha256_hash(self):
        """Test SHA256 hash generation."""
        data = "test_data"
        hash_result = HashGenerator.sha256_hash(data)
        
        expected = hashlib.sha256(data.encode()).hexdigest()
        assert hash_result == expected
        assert len(hash_result) == 64
    
    def test_short_hash(self):
        """Test short hash generation."""
        data = "test_data"
        hash_result = HashGenerator.short_hash(data, length=8)
        
        assert len(hash_result) == 8
        
        # Test different length
        hash_result_12 = HashGenerator.short_hash(data, length=12)
        assert len(hash_result_12) == 12
    
    def test_file_id_hash(self):
        """Test file ID hash generation."""
        file_id = "test_file_id"
        hash_result = HashGenerator.file_id_hash(file_id)
        
        assert len(hash_result) == 16
        
        # Test different length
        hash_result_8 = HashGenerator.file_id_hash(file_id, length=8)
        assert len(hash_result_8) == 8
    
    def test_hash_consistency(self):
        """Test that hashes are consistent for same input."""
        data = "consistent_data"
        
        hash1 = HashGenerator.md5_hash(data)
        hash2 = HashGenerator.md5_hash(data)
        assert hash1 == hash2
        
        sha1 = HashGenerator.sha256_hash(data)
        sha2 = HashGenerator.sha256_hash(data)
        assert sha1 == sha2


class TestTelegramHelpers:
    """Test the Telegram helper functions."""
    
    def test_create_inline_keyboard(self):
        """Test inline keyboard creation."""
        buttons = [
            [("Button 1", "callback_1"), ("Button 2", "callback_2")],
            [("Button 3", "callback_3")]
        ]
        
        keyboard = TelegramHelpers.create_inline_keyboard(buttons)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 2
        assert len(keyboard.inline_keyboard[0]) == 2
        assert len(keyboard.inline_keyboard[1]) == 1
        
        # Check button properties
        button1 = keyboard.inline_keyboard[0][0]
        assert button1.text == "Button 1"
        assert button1.callback_data == "callback_1"
    
    def test_extract_user_info(self):
        """Test user information extraction."""
        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = 12345
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.language_code = "en"
        mock_user.is_bot = False
        
        # Mock update
        mock_update = Mock(spec=Update)
        mock_update.effective_user = mock_user
        
        user_info = TelegramHelpers.extract_user_info(mock_update)
        
        assert user_info is not None
        assert user_info['id'] == 12345
        assert user_info['username'] == "testuser"
        assert user_info['first_name'] == "Test"
        assert user_info['last_name'] == "User"
        assert user_info['language_code'] == "en"
        assert user_info['is_bot'] is False
    
    def test_extract_user_info_no_user(self):
        """Test user info extraction with no user."""
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None
        
        user_info = TelegramHelpers.extract_user_info(mock_update)
        assert user_info is None
    
    def test_extract_chat_info(self):
        """Test chat information extraction."""
        # Mock chat
        mock_chat = Mock(spec=Chat)
        mock_chat.id = -12345
        mock_chat.type = "group"
        mock_chat.title = "Test Group"
        mock_chat.username = "testgroup"
        mock_chat.description = "Test group description"
        
        # Mock update
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = mock_chat
        
        chat_info = TelegramHelpers.extract_chat_info(mock_update)
        
        assert chat_info is not None
        assert chat_info['id'] == -12345
        assert chat_info['type'] == "group"
        assert chat_info['title'] == "Test Group"
        assert chat_info['username'] == "testgroup"
        assert chat_info['description'] == "Test group description"
    
    def test_extract_chat_info_no_chat(self):
        """Test chat info extraction with no chat."""
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = None
        
        chat_info = TelegramHelpers.extract_chat_info(mock_update)
        assert chat_info is None
    
    def test_is_private_chat(self):
        """Test private chat detection."""
        # Mock private chat
        mock_chat = Mock(spec=Chat)
        mock_chat.type = "private"
        
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = mock_chat
        
        assert TelegramHelpers.is_private_chat(mock_update) is True
        
        # Test non-private chat
        mock_chat.type = "group"
        assert TelegramHelpers.is_private_chat(mock_update) is False
    
    def test_is_group_chat(self):
        """Test group chat detection."""
        # Mock group chat
        mock_chat = Mock(spec=Chat)
        mock_chat.type = "group"
        
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = mock_chat
        
        assert TelegramHelpers.is_group_chat(mock_update) is True
        
        # Test supergroup
        mock_chat.type = "supergroup"
        assert TelegramHelpers.is_group_chat(mock_update) is True
        
        # Test private chat
        mock_chat.type = "private"
        assert TelegramHelpers.is_group_chat(mock_update) is False


class TestPerformanceMonitor:
    """Test the performance monitor class."""
    
    @pytest.fixture
    def monitor(self):
        """Create a performance monitor for testing."""
        return PerformanceMonitor()
    
    def test_record_metric(self, monitor):
        """Test metric recording."""
        monitor.record_metric("test_metric", 1.5, "seconds")
        
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        
        metric = metrics[0]
        assert metric.name == "test_metric"
        assert metric.value == 1.5
        assert metric.unit == "seconds"
        assert isinstance(metric.timestamp, datetime)
    
    def test_record_metric_with_tags(self, monitor):
        """Test metric recording with tags."""
        tags = {"operation": "test", "user": "123"}
        monitor.record_metric("test_metric", 2.0, "ms", tags=tags)
        
        metrics = monitor.get_metrics()
        metric = metrics[0]
        assert metric.tags == tags
    
    @pytest.mark.asyncio
    async def test_measure_time_context_manager(self, monitor):
        """Test time measurement context manager."""
        async with monitor.measure_time("test_operation"):
            await asyncio.sleep(0.1)
        
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        
        metric = metrics[0]
        assert metric.name == "test_operation_duration"
        assert metric.unit == "seconds"
        assert metric.value >= 0.1
    
    def test_get_metrics_with_filter(self, monitor):
        """Test metric retrieval with filtering."""
        monitor.record_metric("operation_1_duration", 1.0, "s")
        monitor.record_metric("operation_2_duration", 2.0, "s")
        monitor.record_metric("memory_usage", 100, "MB")
        
        # Filter by name
        duration_metrics = monitor.get_metrics(name_filter="duration")
        assert len(duration_metrics) == 2
        
        memory_metrics = monitor.get_metrics(name_filter="memory")
        assert len(memory_metrics) == 1
    
    def test_get_metrics_with_time_filter(self, monitor):
        """Test metric retrieval with time filtering."""
        # Record a metric
        monitor.record_metric("old_metric", 1.0, "s")
        
        # Set time filter to future
        future_time = datetime.now() + timedelta(minutes=1)
        recent_metrics = monitor.get_metrics(since=future_time)
        assert len(recent_metrics) == 0
        
        # Set time filter to past
        past_time = datetime.now() - timedelta(minutes=1)
        all_metrics = monitor.get_metrics(since=past_time)
        assert len(all_metrics) == 1
    
    def test_clear_metrics(self, monitor):
        """Test clearing all metrics."""
        monitor.record_metric("test_metric", 1.0, "s")
        assert len(monitor.get_metrics()) == 1
        
        monitor.clear_metrics()
        assert len(monitor.get_metrics()) == 0


# Test global instances
class TestGlobalInstances:
    """Test the global utility instances."""
    
    def test_global_performance_monitor(self):
        """Test global performance monitor instance."""
        assert isinstance(performance_monitor, PerformanceMonitor)
    
    def test_global_text_processor(self):
        """Test global text processor instance."""
        assert isinstance(text_processor, TextProcessor)
    
    def test_global_hash_generator(self):
        """Test global hash generator instance."""
        assert isinstance(hash_generator, HashGenerator)
    
    def test_global_telegram_helpers(self):
        """Test global telegram helpers instance."""
        assert isinstance(telegram_helpers, TelegramHelpers)

# ============================================================================
# Async Utilities and Error Handling Tests (Task 11.2)
# ============================================================================

class TestAsyncDecorators:
    """Test async decorator utilities."""
    
    @pytest.mark.asyncio
    async def test_async_retry_decorator_success(self):
        """Test async retry decorator with successful function."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.01)
        async def success_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await success_function()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_decorator_eventual_success(self):
        """Test async retry decorator with eventual success."""
        call_count = 0
        
        @async_retry(max_retries=3, delay=0.01)
        async def eventually_success_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await eventually_success_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_decorator_exhausted(self):
        """Test async retry decorator when retries are exhausted."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.01)
        async def always_fail_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            await always_fail_function()
        
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_measure_performance_decorator(self):
        """Test performance measurement decorator."""
        @measure_performance("test_operation")
        async def test_function():
            await asyncio.sleep(0.1)
            return "result"
        
        with patch('modules.shared_utilities.logger') as mock_logger:
            result = await test_function()
            
            assert result == "result"
            mock_logger.info.assert_called_once()
            
            # Check that the log message contains timing info
            log_call = mock_logger.info.call_args[0][0]
            assert "test_operation completed in" in log_call
            assert "s" in log_call
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator_allows_requests(self):
        """Test rate limit decorator allows requests under limit."""
        @rate_limit(max_requests=2, time_window=1)
        async def limited_function():
            return "success"
        
        # First two calls should succeed
        result1 = await limited_function()
        result2 = await limited_function()
        
        assert result1 == "success"
        assert result2 == "success"
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator_blocks_excess_requests(self):
        """Test rate limit decorator blocks excess requests."""
        @rate_limit(max_requests=1, time_window=1)
        async def limited_function():
            return "success"
        
        # First call should succeed
        result = await limited_function()
        assert result == "success"
        
        # Second call should be blocked
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await limited_function()


class TestAsyncErrorHandling:
    """Test async error handling patterns."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_async_context(self):
        """Test circuit breaker in async context with proper error handling."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        @circuit_breaker
        async def flaky_service():
            # Simulate a service that fails then recovers
            if not hasattr(flaky_service, 'call_count'):
                flaky_service.call_count = 0
            flaky_service.call_count += 1
            
            if flaky_service.call_count <= 2:
                raise ConnectionError("Service unavailable")
            return "service_response"
        
        # First two calls should fail and open circuit
        with pytest.raises(ConnectionError):
            await flaky_service()
        
        with pytest.raises(ConnectionError):
            await flaky_service()
        
        assert circuit_breaker.state == "open"
        
        # Next call should be blocked by circuit breaker
        with pytest.raises(Exception, match="Circuit breaker is open"):
            await flaky_service()
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should now succeed and close circuit
        result = await flaky_service()
        assert result == "service_response"
        assert circuit_breaker.state == "closed"
    
    @pytest.mark.asyncio
    async def test_retry_manager_with_different_exceptions(self):
        """Test retry manager handles different exception types."""
        retry_manager = RetryManager(max_retries=2, base_delay=0.01)
        
        call_count = 0
        
        async def multi_exception_function():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise ConnectionError("Network error")
            elif call_count == 2:
                raise TimeoutError("Request timeout")
            else:
                return "success"
        
        result = await retry_manager.execute(multi_exception_function)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_context_manager_error_cleanup(self):
        """Test async context manager properly cleans up on errors."""
        class TestAsyncResource(AsyncContextManager[str]):
            def __init__(self):
                super().__init__()
                self.setup_called = False
                self.cleanup_called = False
                self.resource_active = False
            
            async def setup(self) -> None:
                self.setup_called = True
                self.resource_active = True
            
            async def cleanup(self) -> None:
                self.cleanup_called = True
                self.resource_active = False
        
        resource = TestAsyncResource()
        
        # Test that cleanup is called even when exception occurs
        with pytest.raises(ValueError):
            async with resource:
                assert resource.setup_called
                assert resource.resource_active
                raise ValueError("Test error")
        
        assert resource.cleanup_called
        assert not resource.resource_active
    
    @pytest.mark.asyncio
    async def test_performance_monitor_with_exceptions(self):
        """Test performance monitor handles exceptions properly."""
        monitor = PerformanceMonitor()
        
        with pytest.raises(ValueError):
            async with monitor.measure_time("failing_operation"):
                await asyncio.sleep(0.05)
                raise ValueError("Operation failed")
        
        # Should still record the metric despite the exception
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        
        metric = metrics[0]
        assert metric.name == "failing_operation_duration"
        assert metric.value >= 0.05


class TestAsyncUtilityIntegration:
    """Test integration of async utilities."""
    
    @pytest.mark.asyncio
    async def test_combined_decorators(self):
        """Test combining multiple async decorators."""
        call_count = 0
        
        @async_retry(max_retries=2, delay=0.01)
        @measure_performance("combined_operation")
        async def decorated_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        with patch('modules.shared_utilities.logger') as mock_logger:
            result = await decorated_function()
            
            assert result == "success"
            assert call_count == 2
            
            # Should have logged performance info
            mock_logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_cache_with_async_operations(self):
        """Test cache manager with async operations."""
        cache = CacheManager[str](default_ttl=1)
        
        async def expensive_operation(key: str) -> str:
            await asyncio.sleep(0.1)
            return f"result_for_{key}"
        
        # First call - cache miss
        start_time = time.time()
        
        cached_result = cache.get("test_key")
        if cached_result is None:
            result = await expensive_operation("test_key")
            cache.set("test_key", result)
            cached_result = result
        
        first_call_time = time.time() - start_time
        assert cached_result == "result_for_test_key"
        assert first_call_time >= 0.1
        
        # Second call - cache hit
        start_time = time.time()
        cached_result = cache.get("test_key")
        second_call_time = time.time() - start_time
        
        assert cached_result == "result_for_test_key"
        assert second_call_time < 0.01  # Should be much faster
    
    @pytest.mark.asyncio
    async def test_rate_limiter_with_async_operations(self):
        """Test rate limiter with async operations."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        async def rate_limited_operation(key: str) -> str:
            if not limiter.is_allowed(key):
                raise Exception("Rate limit exceeded")
            await asyncio.sleep(0.01)
            return f"operation_result_{key}"
        
        # First two operations should succeed
        result1 = await rate_limited_operation("user1")
        result2 = await rate_limited_operation("user1")
        
        assert result1 == "operation_result_user1"
        assert result2 == "operation_result_user1"
        
        # Third operation should fail
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await rate_limited_operation("user1")
        
        # Different user should still work
        result3 = await rate_limited_operation("user2")
        assert result3 == "operation_result_user2"


class TestErrorHandlingUtilities:
    """Test error handling utility functions."""
    
    def test_validation_error_messages(self):
        """Test that validation functions return proper error messages."""
        # Test user ID validation error messages
        result, message = ValidationMixin.validate_user_id(-1)
        assert result is False
        assert isinstance(message, str)
        assert len(message) > 0
        
        # Test text length validation error messages
        result, message = ValidationMixin.validate_text_length("a" * 5000, max_length=100)
        assert result is False
        assert "max 100 characters" in message
        
        # Test URL validation error messages
        result, message = ValidationMixin.validate_url("invalid_url")
        assert result is False
        assert "Invalid URL format" in message
    
    def test_text_processor_edge_cases(self):
        """Test text processor handles edge cases properly."""
        # Test empty string
        assert TextProcessor.extract_urls("") == []
        assert TextProcessor.remove_urls("") == ""
        assert TextProcessor.sanitize_filename("") == ""
        assert TextProcessor.truncate_text("", 10) == ""
        assert TextProcessor.escape_markdown("") == ""
        
        # Test None handling (should not crash)
        with pytest.raises((TypeError, AttributeError)):
            TextProcessor.extract_urls(None)
    
    def test_hash_generator_edge_cases(self):
        """Test hash generator handles edge cases."""
        # Test empty string
        empty_hash = HashGenerator.md5_hash("")
        assert len(empty_hash) == 32
        
        # Test unicode strings
        unicode_hash = HashGenerator.sha256_hash("测试文本")
        assert len(unicode_hash) == 64
        
        # Test very long strings
        long_string = "a" * 10000
        long_hash = HashGenerator.short_hash(long_string, length=16)
        assert len(long_hash) == 16
    
    @pytest.mark.asyncio
    async def test_async_utilities_exception_propagation(self):
        """Test that async utilities properly propagate exceptions."""
        # Test that custom exceptions are preserved through retry
        class CustomError(Exception):
            pass
        
        retry_manager = RetryManager(max_retries=1, base_delay=0.01)
        
        async def custom_error_function():
            raise CustomError("Custom error message")
        
        with pytest.raises(CustomError, match="Custom error message"):
            await retry_manager.execute(custom_error_function)
    
    def test_singleton_thread_safety(self):
        """Test singleton metaclass thread safety (basic test)."""
        import threading
        
        class ThreadTestSingleton(metaclass=SingletonMeta):
            def __init__(self):
                self.thread_id = threading.current_thread().ident
        
        instances = []
        
        def create_instance():
            instances.append(ThreadTestSingleton())
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All instances should be the same object
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance


class TestLoggingAndDebugging:
    """Test logging and debugging utilities."""
    
    @pytest.mark.asyncio
    async def test_performance_monitor_logging_integration(self):
        """Test performance monitor integration with logging."""
        monitor = PerformanceMonitor()
        
        # Record various metrics
        monitor.record_metric("cpu_usage", 75.5, "percent")
        monitor.record_metric("memory_usage", 1024, "MB")
        monitor.record_metric("response_time", 0.250, "seconds")
        
        # Test metric filtering and retrieval
        cpu_metrics = monitor.get_metrics(name_filter="cpu")
        memory_metrics = monitor.get_metrics(name_filter="memory")
        
        assert len(cpu_metrics) == 1
        assert len(memory_metrics) == 1
        assert cpu_metrics[0].value == 75.5
        assert memory_metrics[0].value == 1024
    
    def test_base_service_logging(self):
        """Test base service logging functionality."""
        class TestService(BaseService):
            async def initialize(self) -> None:
                self._initialized = True
            
            async def start(self) -> None:
                self._running = True
                self._start_time = datetime.now()
            
            async def stop(self) -> None:
                self._running = False
        
        service = TestService("test_logging_service")
        
        # Test that logger is properly configured
        assert service.logger is not None
        assert "test_logging_service" in service.logger.name
        
        # Test service state tracking
        assert not service.is_initialized()
        assert not service.is_running()
        assert service.get_uptime() is None
    
    @pytest.mark.asyncio
    async def test_retry_manager_logging(self):
        """Test retry manager logging behavior."""
        retry_manager = RetryManager(max_retries=2, base_delay=0.01)
        
        call_count = 0
        
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return "success"
        
        with patch('modules.shared_utilities.logger') as mock_logger:
            result = await retry_manager.execute(failing_function)
            
            assert result == "success"
            assert call_count == 3
            
            # Should have logged warnings for retries
            assert mock_logger.warning.call_count == 2
            assert mock_logger.error.call_count == 0  # No error since it eventually succeeded
    
    @pytest.mark.asyncio
    async def test_retry_manager_final_failure_logging(self):
        """Test retry manager logging when all retries are exhausted."""
        retry_manager = RetryManager(max_retries=1, base_delay=0.01)
        
        async def always_fail_function():
            raise ValueError("Persistent failure")
        
        with patch('modules.shared_utilities.logger') as mock_logger:
            with pytest.raises(ValueError):
                await retry_manager.execute(always_fail_function)
            
            # Should have logged warning for retry and error for final failure
            assert mock_logger.warning.call_count == 1
            assert mock_logger.error.call_count == 1
            
            error_call = mock_logger.error.call_args[0][0]
            assert "All" in error_call and "attempts failed" in error_call


# Integration tests for complete workflows
class TestIntegrationWorkflows:
    """Test complete workflows using multiple utilities together."""
    
    @pytest.mark.asyncio
    async def test_complete_service_workflow(self):
        """Test a complete service workflow with error handling and monitoring."""
        class CompleteTestService(BaseService):
            def __init__(self, name: str):
                super().__init__(name)
                self.cache = CacheManager[str](default_ttl=60)
                self.monitor = PerformanceMonitor()
                self.retry_manager = RetryManager(max_retries=2, base_delay=0.01)
            
            async def initialize(self) -> None:
                self._initialized = True
                self.logger.info("Service initialized")
            
            async def start(self) -> None:
                self._running = True
                self._start_time = datetime.now()
                self.logger.info("Service started")
            
            async def stop(self) -> None:
                self._running = False
                self.logger.info("Service stopped")
            
            @measure_performance("process_request")
            async def process_request(self, request_id: str) -> str:
                # Check cache first
                cached_result = self.cache.get(request_id)
                if cached_result:
                    return cached_result
                
                # Simulate processing with potential failures
                async def do_processing():
                    await asyncio.sleep(0.01)
                    if request_id == "fail_request":
                        raise ValueError("Processing failed")
                    return f"processed_{request_id}"
                
                # Use retry manager for resilience
                result = await self.retry_manager.execute(do_processing)
                
                # Cache the result
                self.cache.set(request_id, result)
                
                return result
        
        service = CompleteTestService("integration_test_service")
        
        # Test complete lifecycle
        await service.initialize()
        await service.start()
        
        assert service.is_initialized()
        assert service.is_running()
        assert await service.health_check()
        
        # Test successful request processing
        with patch('modules.shared_utilities.logger'):
            result1 = await service.process_request("test_request")
            assert result1 == "processed_test_request"
            
            # Second call should use cache
            result2 = await service.process_request("test_request")
            assert result2 == "processed_test_request"
        
        # Test error handling
        with pytest.raises(ValueError):
            await service.process_request("fail_request")
        
        await service.stop()
        assert not service.is_running()
    
    def test_text_processing_pipeline(self):
        """Test a complete text processing pipeline."""
        # Input text with various elements
        input_text = """
        Check out these links: https://example.com and http://test.org
        This text has *markdown* and _formatting_ and [links](url).
        It also has invalid filename characters: <file>name.txt
        And some very long content that might need truncation...
        """
        
        # Process through various utilities
        processor = TextProcessor()
        
        # Extract URLs
        urls = processor.extract_urls(input_text)
        assert len(urls) == 2
        
        # Remove URLs
        clean_text = processor.remove_urls(input_text)
        assert "https://example.com" not in clean_text
        
        # Escape markdown
        escaped_text = processor.escape_markdown(clean_text)
        assert "\\*" in escaped_text
        assert "\\_" in escaped_text
        
        # Truncate if needed
        truncated_text = processor.truncate_text(escaped_text, max_length=100)
        assert len(truncated_text) <= 100
        
        # Generate hash for processed text
        text_hash = HashGenerator.sha256_hash(truncated_text)
        assert len(text_hash) == 64
        
        # Sanitize for filename
        filename = processor.sanitize_filename("processed_text.txt")
        assert filename == "processed_text.txt"
    
    def test_validation_pipeline(self):
        """Test a complete validation pipeline."""
        validator = ValidationMixin()
        
        # Test data
        test_cases = [
            {"user_id": 12345, "chat_id": -67890, "text": "Hello world", "url": "https://example.com"},
            {"user_id": -1, "chat_id": "invalid", "text": "a" * 5000, "url": "not_a_url"},
            {"user_id": 0, "chat_id": 123, "text": 123, "url": "ftp://example.com"}
        ]
        
        for i, test_case in enumerate(test_cases):
            user_valid, user_msg = validator.validate_user_id(test_case["user_id"])
            chat_valid, chat_msg = validator.validate_chat_id(test_case["chat_id"])
            text_valid, text_msg = validator.validate_text_length(test_case["text"])
            url_valid, url_msg = validator.validate_url(test_case["url"])
            
            if i == 0:  # First case should be all valid
                assert user_valid and chat_valid and text_valid and url_valid
                assert all(msg is None for msg in [user_msg, chat_msg, text_msg, url_msg])
            else:  # Other cases should have validation errors
                assert not all([user_valid, chat_valid, text_valid, url_valid])
                error_messages = [msg for msg in [user_msg, chat_msg, text_msg, url_msg] if msg]
                assert len(error_messages) > 0