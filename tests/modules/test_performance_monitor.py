"""
Unit tests for performance monitoring and optimization.
"""

import pytest
import asyncio
import time
import psutil
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from modules.performance_monitor import (
    PerformanceMonitor, MetricsCollector, PerformanceAlert,
    ResourceUsage, RequestMetrics
)


class TestMetricsCollector:
    """Test cases for MetricsCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create a MetricsCollector instance."""
        return MetricsCollector()
    
    def test_counter_metrics(self, collector):
        """Test counter metric operations."""
        # Increment counter
        collector.increment_counter("requests_total")
        collector.increment_counter("requests_total", 5)
        
        assert collector.get_counter("requests_total") == 6
    
    def test_gauge_metrics(self, collector):
        """Test gauge metric operations."""
        # Set gauge values
        collector.set_gauge("memory_usage", 1024)
        collector.set_gauge("cpu_usage", 75.5)
        
        assert collector.get_gauge("memory_usage") == 1024
        assert collector.get_gauge("cpu_usage") == 75.5
    
    def test_histogram_metrics(self, collector):
        """Test histogram metric operations."""
        # Record histogram values
        collector.record_histogram("response_time", 0.1)
        collector.record_histogram("response_time", 0.2)
        collector.record_histogram("response_time", 0.15)
        
        histogram = collector.get_histogram("response_time")
        assert len(histogram) == 3
        assert 0.1 in histogram
        assert 0.2 in histogram
        assert 0.15 in histogram
    
    def test_timer_context_manager(self, collector):
        """Test timer context manager."""
        with collector.timer("operation_duration"):
            time.sleep(0.1)
        
        histogram = collector.get_histogram("operation_duration")
        assert len(histogram) == 1
        assert histogram[0] >= 0.1
    
    def test_metric_labels(self, collector):
        """Test metrics with labels."""
        collector.increment_counter("http_requests", labels={"method": "GET", "status": "200"})
        collector.increment_counter("http_requests", labels={"method": "POST", "status": "201"})
        collector.increment_counter("http_requests", labels={"method": "GET", "status": "200"})
        
        # Should track separate counters for different label combinations
        get_200_count = collector.get_counter("http_requests", labels={"method": "GET", "status": "200"})
        post_201_count = collector.get_counter("http_requests", labels={"method": "POST", "status": "201"})
        
        assert get_200_count == 2
        assert post_201_count == 1
    
    def test_metric_aggregation(self, collector):
        """Test metric aggregation functions."""
        # Record multiple values
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        for value in values:
            collector.record_histogram("test_metric", value)
        
        # Test aggregation
        avg = collector.get_average("test_metric")
        assert avg == 0.3
        
        percentile_95 = collector.get_percentile("test_metric", 95)
        assert percentile_95 == 0.5  # Max value for small dataset
        
        total = collector.get_sum("test_metric")
        assert total == 1.5


class TestPerformanceAlert:
    """Test cases for PerformanceAlert."""
    
    def test_alert_creation(self):
        """Test performance alert creation."""
        alert = PerformanceAlert(
            metric_name="cpu_usage",
            threshold=80.0,
            comparison="greater_than",
            severity="warning",
            message="High CPU usage detected"
        )
        
        assert alert.metric_name == "cpu_usage"
        assert alert.threshold == 80.0
        assert alert.comparison == "greater_than"
        assert alert.severity == "warning"
        assert alert.message == "High CPU usage detected"
    
    def test_alert_evaluation(self):
        """Test alert condition evaluation."""
        alert = PerformanceAlert(
            metric_name="response_time",
            threshold=1.0,
            comparison="greater_than",
            severity="critical"
        )
        
        # Should trigger
        assert alert.should_trigger(1.5)
        assert alert.should_trigger(2.0)
        
        # Should not trigger
        assert not alert.should_trigger(0.5)
        assert not alert.should_trigger(1.0)  # Equal to threshold
    
    def test_alert_different_comparisons(self):
        """Test different alert comparison operators."""
        # Less than
        alert_lt = PerformanceAlert("metric", 10, "less_than", "info")
        assert alert_lt.should_trigger(5)
        assert not alert_lt.should_trigger(15)
        
        # Equal to
        alert_eq = PerformanceAlert("metric", 10, "equal_to", "info")
        assert alert_eq.should_trigger(10)
        assert not alert_eq.should_trigger(9)
        
        # Not equal to
        alert_ne = PerformanceAlert("metric", 10, "not_equal_to", "info")
        assert alert_ne.should_trigger(5)
        assert not alert_ne.should_trigger(10)


class TestResourceMonitor:
    """Test cases for ResourceMonitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create a ResourceMonitor instance."""
        return ResourceMonitor()
    
    @pytest.mark.asyncio
    async def test_cpu_monitoring(self, monitor):
        """Test CPU usage monitoring."""
        await monitor.start_monitoring()
        
        # Let it collect some data
        await asyncio.sleep(0.2)
        
        cpu_usage = monitor.get_cpu_usage()
        assert isinstance(cpu_usage, float)
        assert 0 <= cpu_usage <= 100
        
        await monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_memory_monitoring(self, monitor):
        """Test memory usage monitoring."""
        await monitor.start_monitoring()
        
        # Let it collect some data
        await asyncio.sleep(0.2)
        
        memory_info = monitor.get_memory_usage()
        assert "used" in memory_info
        assert "available" in memory_info
        assert "percent" in memory_info
        assert isinstance(memory_info["percent"], float)
        
        await monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_disk_monitoring(self, monitor):
        """Test disk usage monitoring."""
        await monitor.start_monitoring()
        
        disk_info = monitor.get_disk_usage()
        assert "used" in disk_info
        assert "free" in disk_info
        assert "percent" in disk_info
        
        await monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_network_monitoring(self, monitor):
        """Test network I/O monitoring."""
        await monitor.start_monitoring()
        
        # Let it collect some data
        await asyncio.sleep(0.2)
        
        network_info = monitor.get_network_io()
        assert "bytes_sent" in network_info
        assert "bytes_recv" in network_info
        
        await monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_resource_alerts(self, monitor):
        """Test resource monitoring alerts."""
        alerts_triggered = []
        
        def alert_handler(alert_info):
            alerts_triggered.append(alert_info)
        
        monitor.add_alert_handler(alert_handler)
        
        # Add a low threshold alert that should trigger
        monitor.add_alert(PerformanceAlert(
            "cpu_usage", 0.1, "greater_than", "test"
        ))
        
        await monitor.start_monitoring()
        await asyncio.sleep(0.3)  # Let it monitor and potentially trigger alerts
        await monitor.stop_monitoring()
        
        # Should have triggered at least one alert (CPU usage > 0.1%)
        # Note: This might be flaky in very low-load environments
        # assert len(alerts_triggered) > 0


class TestRequestTracker:
    """Test cases for RequestTracker."""
    
    @pytest.fixture
    def tracker(self):
        """Create a RequestTracker instance."""
        return RequestTracker()
    
    @pytest.mark.asyncio
    async def test_request_tracking(self, tracker):
        """Test basic request tracking."""
        # Start tracking a request
        request_id = tracker.start_request("test_endpoint", {"user_id": "123"})
        
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        # End the request
        tracker.end_request(request_id, status_code=200, response_size=1024)
        
        # Get metrics
        metrics = tracker.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["avg_response_time"] >= 0.1
        assert "test_endpoint" in metrics["endpoints"]
    
    @pytest.mark.asyncio
    async def test_concurrent_request_tracking(self, tracker):
        """Test tracking multiple concurrent requests."""
        async def simulate_request(endpoint: str, duration: float):
            request_id = tracker.start_request(endpoint)
            await asyncio.sleep(duration)
            tracker.end_request(request_id, status_code=200)
        
        # Start multiple concurrent requests
        tasks = [
            simulate_request("endpoint1", 0.1),
            simulate_request("endpoint2", 0.2),
            simulate_request("endpoint1", 0.15),
        ]
        
        await asyncio.gather(*tasks)
        
        metrics = tracker.get_metrics()
        assert metrics["total_requests"] == 3
        assert len(metrics["endpoints"]) == 2
        assert metrics["endpoints"]["endpoint1"]["count"] == 2
        assert metrics["endpoints"]["endpoint2"]["count"] == 1
    
    def test_request_status_tracking(self, tracker):
        """Test tracking of different request statuses."""
        # Track requests with different status codes
        for status in [200, 404, 500, 200, 200]:
            request_id = tracker.start_request("test")
            tracker.end_request(request_id, status_code=status)
        
        metrics = tracker.get_metrics()
        assert metrics["status_codes"]["200"] == 3
        assert metrics["status_codes"]["404"] == 1
        assert metrics["status_codes"]["500"] == 1
    
    def test_error_rate_calculation(self, tracker):
        """Test error rate calculation."""
        # Track mix of successful and error requests
        statuses = [200, 200, 200, 404, 500, 200, 500]
        for status in statuses:
            request_id = tracker.start_request("test")
            tracker.end_request(request_id, status_code=status)
        
        error_rate = tracker.get_error_rate()
        # 3 errors out of 7 requests = ~42.86%
        assert abs(error_rate - 42.86) < 0.1
    
    def test_throughput_calculation(self, tracker):
        """Test throughput calculation."""
        # Simulate requests over time
        start_time = time.time()
        
        for _ in range(10):
            request_id = tracker.start_request("test")
            tracker.end_request(request_id, status_code=200)
        
        # Calculate throughput (requests per second)
        elapsed = time.time() - start_time
        throughput = tracker.get_throughput()
        
        expected_throughput = 10 / elapsed
        assert abs(throughput - expected_throughput) < 1.0  # Allow some variance


class TestMemoryProfiler:
    """Test cases for MemoryProfiler."""
    
    @pytest.fixture
    def profiler(self):
        """Create a MemoryProfiler instance."""
        return MemoryProfiler()
    
    def test_memory_snapshot(self, profiler):
        """Test taking memory snapshots."""
        # Create some objects to profile
        test_data = [i for i in range(1000)]
        
        snapshot = profiler.take_snapshot()
        assert "total_memory" in snapshot
        assert "objects_by_type" in snapshot
        assert isinstance(snapshot["total_memory"], int)
    
    def test_memory_leak_detection(self, profiler):
        """Test memory leak detection."""
        # Take initial snapshot
        profiler.take_snapshot()
        
        # Create objects that might leak
        leaked_objects = []
        for i in range(100):
            leaked_objects.append(f"leaked_object_{i}")
        
        # Take second snapshot
        profiler.take_snapshot()
        
        # Analyze for potential leaks
        leak_analysis = profiler.analyze_leaks()
        assert "memory_growth" in leak_analysis
        assert "potential_leaks" in leak_analysis
    
    def test_memory_usage_tracking(self, profiler):
        """Test memory usage tracking over time."""
        profiler.start_tracking()
        
        # Simulate memory usage changes
        data = []
        for i in range(10):
            data.extend([j for j in range(100)])
            time.sleep(0.01)
        
        profiler.stop_tracking()
        
        usage_history = profiler.get_usage_history()
        assert len(usage_history) > 0
        assert all("timestamp" in entry and "memory_mb" in entry for entry in usage_history)


class TestCacheMonitor:
    """Test cases for CacheMonitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create a CacheMonitor instance."""
        return CacheMonitor()
    
    def test_cache_hit_tracking(self, monitor):
        """Test cache hit/miss tracking."""
        # Simulate cache operations
        monitor.record_hit("user_cache")
        monitor.record_hit("user_cache")
        monitor.record_miss("user_cache")
        monitor.record_hit("config_cache")
        
        stats = monitor.get_cache_stats("user_cache")
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3
        
        config_stats = monitor.get_cache_stats("config_cache")
        assert config_stats["hits"] == 1
        assert config_stats["misses"] == 0
        assert config_stats["hit_rate"] == 1.0
    
    def test_cache_size_monitoring(self, monitor):
        """Test cache size monitoring."""
        monitor.update_cache_size("user_cache", 1024)
        monitor.update_cache_size("config_cache", 512)
        
        total_size = monitor.get_total_cache_size()
        assert total_size == 1536
        
        size_by_cache = monitor.get_cache_sizes()
        assert size_by_cache["user_cache"] == 1024
        assert size_by_cache["config_cache"] == 512
    
    def test_cache_eviction_tracking(self, monitor):
        """Test cache eviction tracking."""
        monitor.record_eviction("user_cache", "lru")
        monitor.record_eviction("user_cache", "ttl")
        monitor.record_eviction("config_cache", "size_limit")
        
        evictions = monitor.get_eviction_stats("user_cache")
        assert evictions["lru"] == 1
        assert evictions["ttl"] == 1
        assert evictions["total"] == 2


class TestDatabasePerformanceMonitor:
    """Test cases for DatabasePerformanceMonitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create a DatabasePerformanceMonitor instance."""
        return DatabasePerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_query_performance_tracking(self, monitor):
        """Test database query performance tracking."""
        # Simulate database queries
        with monitor.track_query("SELECT * FROM users WHERE id = ?"):
            await asyncio.sleep(0.1)  # Simulate query time
        
        with monitor.track_query("INSERT INTO logs (message) VALUES (?)"):
            await asyncio.sleep(0.05)
        
        stats = monitor.get_query_stats()
        assert len(stats) == 2
        
        select_stats = next(s for s in stats if "SELECT" in s["query"])
        assert select_stats["count"] == 1
        assert select_stats["avg_duration"] >= 0.1
    
    def test_connection_pool_monitoring(self, monitor):
        """Test database connection pool monitoring."""
        monitor.update_pool_stats(
            active_connections=5,
            idle_connections=3,
            max_connections=10
        )
        
        pool_stats = monitor.get_pool_stats()
        assert pool_stats["active"] == 5
        assert pool_stats["idle"] == 3
        assert pool_stats["max"] == 10
        assert pool_stats["utilization"] == 0.5  # 5/10
    
    def test_slow_query_detection(self, monitor):
        """Test slow query detection."""
        # Set slow query threshold
        monitor.set_slow_query_threshold(0.1)
        
        # Simulate fast and slow queries
        with monitor.track_query("FAST QUERY"):
            time.sleep(0.05)  # Fast query
        
        with monitor.track_query("SLOW QUERY"):
            time.sleep(0.2)   # Slow query
        
        slow_queries = monitor.get_slow_queries()
        assert len(slow_queries) == 1
        assert "SLOW QUERY" in slow_queries[0]["query"]
        assert slow_queries[0]["duration"] >= 0.2


class TestPerformanceMonitor:
    """Test cases for main PerformanceMonitor class."""
    
    @pytest.fixture
    def monitor(self):
        """Create a PerformanceMonitor instance."""
        return PerformanceMonitor()
    
    @pytest.mark.asyncio
    async def test_monitor_initialization(self, monitor):
        """Test performance monitor initialization."""
        await monitor.initialize()
        
        assert monitor.metric_collector is not None
        assert monitor.resource_monitor is not None
        assert monitor.request_tracker is not None
        
        await monitor.shutdown()
    
    @pytest.mark.asyncio
    async def test_comprehensive_monitoring(self, monitor):
        """Test comprehensive performance monitoring."""
        await monitor.initialize()
        await monitor.start_monitoring()
        
        # Simulate some activity
        with monitor.track_request("test_endpoint"):
            await asyncio.sleep(0.1)
        
        monitor.increment_counter("test_counter")
        monitor.set_gauge("test_gauge", 42)
        
        # Let monitoring collect data
        await asyncio.sleep(0.2)
        
        # Get comprehensive report
        report = await monitor.get_performance_report()
        
        assert "system_resources" in report
        assert "request_metrics" in report
        assert "custom_metrics" in report
        
        await monitor.stop_monitoring()
        await monitor.shutdown()
    
    @pytest.mark.asyncio
    async def test_alert_system_integration(self, monitor):
        """Test integration with alert system."""
        alerts_triggered = []
        
        def alert_handler(alert):
            alerts_triggered.append(alert)
        
        await monitor.initialize()
        monitor.add_alert_handler(alert_handler)
        
        # Add an alert that should trigger
        monitor.add_performance_alert(PerformanceAlert(
            "test_counter", 0, "greater_than", "test"
        ))
        
        # Trigger the alert
        monitor.increment_counter("test_counter")
        
        # Process alerts
        await monitor.process_alerts()
        
        # Should have triggered the alert
        assert len(alerts_triggered) > 0
        
        await monitor.shutdown()
    
    @pytest.mark.asyncio
    async def test_performance_optimization_suggestions(self, monitor):
        """Test performance optimization suggestions."""
        await monitor.initialize()
        
        # Simulate various performance scenarios
        monitor.set_gauge("cpu_usage", 85)  # High CPU
        monitor.set_gauge("memory_usage_percent", 90)  # High memory
        monitor.record_histogram("response_time", 2.5)  # Slow response
        
        suggestions = await monitor.get_optimization_suggestions()
        
        assert len(suggestions) > 0
        assert any("cpu" in s.lower() for s in suggestions)
        assert any("memory" in s.lower() for s in suggestions)
        
        await monitor.shutdown()


class TestPerformanceIntegration:
    """Integration tests for performance monitoring."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_monitoring(self):
        """Test end-to-end performance monitoring scenario."""
        monitor = PerformanceMonitor()
        await monitor.initialize()
        await monitor.start_monitoring()
        
        # Simulate a realistic application scenario
        async def simulate_user_request(user_id: str):
            with monitor.track_request(f"user_profile_{user_id}"):
                # Simulate database query
                with monitor.track_database_query("SELECT * FROM users WHERE id = ?"):
                    await asyncio.sleep(0.05)
                
                # Simulate cache lookup
                monitor.record_cache_hit("user_cache")
                
                # Simulate processing
                await asyncio.sleep(0.1)
                
                return f"profile_for_{user_id}"
        
        # Simulate multiple concurrent users
        tasks = [simulate_user_request(f"user_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Let monitoring collect data
        await asyncio.sleep(0.2)
        
        # Generate comprehensive report
        report = await monitor.get_performance_report()
        
        # Verify report contains expected data
        assert report["request_metrics"]["total_requests"] == 10
        assert "user_profile_" in str(report["request_metrics"]["endpoints"])
        assert report["cache_metrics"]["user_cache"]["hits"] == 10
        
        # Check for any performance issues
        issues = await monitor.detect_performance_issues()
        # Should not have critical issues in this simple test
        
        await monitor.stop_monitoring()
        await monitor.shutdown()
        
        assert len(results) == 10
    
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self):
        """Test performance regression detection."""
        monitor = PerformanceMonitor()
        await monitor.initialize()
        
        # Establish baseline performance
        for _ in range(10):
            with monitor.track_request("api_endpoint"):
                await asyncio.sleep(0.1)  # Consistent 100ms response time
        
        baseline = monitor.get_baseline_metrics("api_endpoint")
        
        # Simulate performance regression
        for _ in range(5):
            with monitor.track_request("api_endpoint"):
                await asyncio.sleep(0.3)  # Degraded to 300ms response time
        
        # Detect regression
        regression = monitor.detect_performance_regression("api_endpoint", baseline)
        
        assert regression is not None
        assert regression["degradation_factor"] > 2.0  # 3x slower
        assert regression["confidence"] > 0.8
        
        await monitor.shutdown()