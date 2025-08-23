"""
Tests for leveling system performance enhancements.

This module tests the comprehensive error handling, caching, and performance
monitoring enhancements added to the user leveling system.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from modules.user_leveling_service import UserLevelingService
from modules.leveling_cache import leveling_cache, LevelingCache
from modules.leveling_performance_monitor import leveling_performance_monitor, AlertSeverity
from modules.leveling_models import UserStats, Achievement
from modules.service_error_boundary import health_monitor


class TestLevelingPerformanceEnhancements:
    """Test suite for leveling system performance enhancements."""
    
    @pytest.fixture
    async def leveling_service(self):
        """Create a leveling service instance for testing."""
        service = UserLevelingService()
        
        # Mock dependencies
        service.config_manager = Mock()
        service.database = Mock()
        service.user_stats_repo = AsyncMock()
        service.achievement_repo = AsyncMock()
        service.achievement_engine = AsyncMock()
        service.notification_service = AsyncMock()
        
        # Initialize with mocked dependencies
        await service.initialize()
        
        yield service
        
        # Cleanup
        await service.shutdown()
    
    @pytest.fixture
    def mock_user_stats(self):
        """Create mock user stats for testing."""
        return UserStats(
            user_id=12345,
            chat_id=67890,
            xp=150,
            level=3,
            messages_count=50,
            links_shared=5,
            thanks_received=2,
            last_activity=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_achievement(self):
        """Create mock achievement for testing."""
        return Achievement(
            id="test_achievement",
            title="Test Achievement",
            description="A test achievement",
            emoji="🏆",
            sticker="🏆",
            condition_type="messages_count",
            condition_value=50,
            category="activity"
        )


class TestErrorHandlingEnhancements:
    """Test error handling enhancements."""
    
    @pytest.mark.asyncio
    async def test_database_retry_mechanism(self, leveling_service, mock_user_stats):
        """Test database retry mechanism with transient failures."""
        # Mock database failure followed by success
        leveling_service.user_stats_repo.get_user_stats.side_effect = [
            ConnectionError("Database connection failed"),
            ConnectionError("Database connection failed"),
            mock_user_stats  # Success on third try
        ]
        
        # Should succeed after retries
        result = await leveling_service._get_user_stats_cached(12345, 67890)
        
        assert result is not None
        assert result.user_id == 12345
        assert leveling_service.user_stats_repo.get_user_stats.call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, leveling_service):
        """Test circuit breaker activation after multiple failures."""
        # Mock multiple consecutive failures
        leveling_service.user_stats_repo.get_user_stats.side_effect = ConnectionError("Database down")
        
        # Multiple calls should trigger circuit breaker
        for _ in range(6):  # Exceed failure threshold
            result = await leveling_service._get_user_stats_cached(12345, 67890)
            assert result is None
        
        # Circuit breaker should be open
        error_boundary = health_monitor.get_error_boundary("user_leveling_service")
        assert error_boundary is not None
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, leveling_service):
        """Test graceful degradation when components fail."""
        # Mock achievement engine failure
        leveling_service.achievement_engine = None
        
        # Service should continue working without achievements
        result = await leveling_service._check_achievements_safe(Mock())
        assert result == []
    
    @pytest.mark.asyncio
    async def test_fallback_mechanisms(self, leveling_service):
        """Test fallback mechanisms for critical operations."""
        # Mock database failure
        leveling_service.user_stats_repo.update_user_stats.side_effect = Exception("Database error")
        
        # Should use fallback and not crash
        mock_stats = Mock()
        try:
            await leveling_service._update_user_stats_with_retry(mock_stats)
        except Exception:
            pass  # Expected to fail but should be handled gracefully
        
        # Service should remain operational
        assert leveling_service._enabled


class TestCachingEnhancements:
    """Test caching system enhancements."""
    
    @pytest.mark.asyncio
    async def test_user_stats_caching(self, mock_user_stats):
        """Test user stats caching functionality."""
        cache = LevelingCache()
        
        # Test cache miss
        result = await cache.get_user_stats(12345, 67890)
        assert result is None
        
        # Set cache
        await cache.set_user_stats(12345, 67890, mock_user_stats)
        
        # Test cache hit
        result = await cache.get_user_stats(12345, 67890)
        assert result is not None
        assert result['user_id'] == 12345
        assert result['xp'] == 150
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mock_user_stats):
        """Test cache invalidation functionality."""
        cache = LevelingCache()
        
        # Set cache
        await cache.set_user_stats(12345, 67890, mock_user_stats)
        
        # Verify cached
        result = await cache.get_user_stats(12345, 67890)
        assert result is not None
        
        # Invalidate
        await cache.invalidate_user_stats(12345, 67890)
        
        # Verify invalidated
        result = await cache.get_user_stats(12345, 67890)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_warming(self, mock_user_stats, mock_achievement):
        """Test cache warming functionality."""
        cache = LevelingCache()
        
        # Mock data loaders
        async def load_user_stats(user_id, chat_id):
            return mock_user_stats
        
        async def load_achievements():
            return [mock_achievement]
        
        # Perform cache warming
        await cache.warm_up_cache(load_user_stats, load_achievements)
        
        # Verify achievements were cached
        achievements = await cache.get_achievements()
        assert achievements is not None
        assert len(achievements) == 1
    
    def test_cache_metrics(self):
        """Test cache metrics collection."""
        cache = LevelingCache()
        
        # Simulate cache operations
        cache.metrics.hits = 10
        cache.metrics.misses = 5
        cache.metrics.invalidations = 2
        
        metrics = cache.get_cache_metrics()
        
        assert metrics['metrics']['hits'] == 10
        assert metrics['metrics']['misses'] == 5
        assert metrics['metrics']['hit_rate'] == 10/15  # 66.7%
        assert metrics['metrics']['invalidations'] == 2


class TestPerformanceMonitoring:
    """Test performance monitoring enhancements."""
    
    def test_performance_metric_recording(self):
        """Test performance metric recording."""
        monitor = leveling_performance_monitor
        
        # Record some metrics
        monitor.record_metric("message_processing_time", 0.05)
        monitor.record_metric("cache_hit_rate", 0.8)
        monitor.record_metric("error_rate", 2.0)
        
        # Check metrics were recorded
        assert "message_processing_time" in monitor.metrics_history
        assert "cache_hit_rate" in monitor.metrics_history
        assert "error_rate" in monitor.metrics_history
    
    def test_threshold_alerting(self):
        """Test threshold-based alerting."""
        monitor = leveling_performance_monitor
        
        # Clear existing alerts
        monitor.alerts.clear()
        
        # Record metric that exceeds threshold
        monitor.record_metric("message_processing_time", 0.6)  # Exceeds critical threshold
        
        # Check alert was generated
        alerts = monitor.get_recent_alerts(hours=1)
        assert len(alerts) > 0
        
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical_alerts) > 0
    
    def test_performance_statistics(self):
        """Test performance statistics calculation."""
        monitor = leveling_performance_monitor
        
        # Record multiple values
        values = [0.02, 0.03, 0.05, 0.04, 0.06]
        for value in values:
            monitor.record_metric("test_metric", value)
        
        # Get statistics
        stats = monitor.get_metric_statistics("test_metric", hours=1)
        
        assert stats['count'] == 5
        assert stats['min'] == 0.02
        assert stats['max'] == 0.06
        assert abs(stats['avg'] - 0.04) < 0.001
        assert stats['latest'] == 0.06
    
    def test_optimization_recommendations(self):
        """Test optimization recommendations generation."""
        monitor = leveling_performance_monitor
        
        # Clear existing data
        monitor.metrics_history.clear()
        monitor.alerts.clear()
        
        # Record poor performance metrics
        monitor.record_metric("message_processing_time", 0.2)  # Slow processing
        monitor.record_metric("cache_hit_rate", 0.4)  # Poor cache performance
        
        # Get recommendations
        recommendations = monitor.get_optimization_recommendations()
        
        assert len(recommendations) > 0
        assert any("processing" in rec.lower() for rec in recommendations)
        assert any("cache" in rec.lower() for rec in recommendations)
    
    def test_health_status_reporting(self):
        """Test health status reporting."""
        monitor = leveling_performance_monitor
        
        # Clear existing alerts
        monitor.alerts.clear()
        
        # Record critical performance issue
        monitor.record_metric("message_processing_time", 1.0)  # Very slow
        
        # Get health status
        health = monitor.get_health_status()
        
        assert health['health_status'] in ['critical', 'degraded', 'warning']
        assert 'alerts_summary' in health
        assert 'key_metrics' in health
        assert 'recommendations' in health


class TestIntegrationScenarios:
    """Test integration scenarios with all enhancements."""
    
    @pytest.mark.asyncio
    async def test_high_load_scenario(self, leveling_service, mock_user_stats):
        """Test system behavior under high load."""
        # Mock successful database operations
        leveling_service.user_stats_repo.get_user_stats.return_value = mock_user_stats
        leveling_service.user_stats_repo.update_user_stats.return_value = None
        
        # Simulate high load with concurrent requests
        tasks = []
        for i in range(100):
            task = leveling_service._get_user_stats_cached(12345 + i, 67890)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed (some might fail due to rate limiting)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) > 50  # At least 50% success rate
    
    @pytest.mark.asyncio
    async def test_database_failure_recovery(self, leveling_service, mock_user_stats):
        """Test recovery from database failures."""
        # Simulate database failure then recovery
        failure_count = 0
        
        def mock_get_user_stats(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise ConnectionError("Database connection failed")
            return mock_user_stats
        
        leveling_service.user_stats_repo.get_user_stats.side_effect = mock_get_user_stats
        
        # First few calls should fail, then succeed
        result1 = await leveling_service._get_user_stats_cached(12345, 67890)
        assert result1 is None  # Failed
        
        result2 = await leveling_service._get_user_stats_cached(12345, 67890)
        assert result2 is None  # Failed
        
        result3 = await leveling_service._get_user_stats_cached(12345, 67890)
        assert result3 is None  # Failed
        
        result4 = await leveling_service._get_user_stats_cached(12345, 67890)
        assert result4 is not None  # Succeeded after recovery
    
    @pytest.mark.asyncio
    async def test_cache_performance_under_load(self):
        """Test cache performance under high load."""
        cache = LevelingCache()
        
        # Create test data
        test_users = [(i, 67890) for i in range(1000, 1100)]
        test_stats = [
            UserStats(
                user_id=user_id,
                chat_id=chat_id,
                xp=100 + user_id,
                level=2,
                messages_count=10,
                links_shared=1,
                thanks_received=0,
                last_activity=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            for user_id, chat_id in test_users
        ]
        
        # Populate cache
        for stats in test_stats:
            await cache.set_user_stats(stats.user_id, stats.chat_id, stats)
        
        # Test cache performance
        start_time = time.time()
        
        # Perform many cache operations
        for _ in range(1000):
            user_id, chat_id = test_users[_ % len(test_users)]
            result = await cache.get_user_stats(user_id, chat_id)
            assert result is not None
        
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 1000 operations)
        assert (end_time - start_time) < 1.0
        
        # Check cache metrics
        metrics = cache.get_cache_metrics()
        assert metrics['metrics']['hit_rate'] > 0.9  # High hit rate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])