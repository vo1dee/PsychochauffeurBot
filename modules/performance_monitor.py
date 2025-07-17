"""
Comprehensive performance monitoring and optimization system.

This module provides performance metrics collection, monitoring, and optimization
tools for the PsychoChauffeur bot application.
"""

import asyncio
import gc
import logging
import psutil
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import (
    Dict, List, Optional, Any, Callable, Awaitable, Union, 
    DefaultDict, Deque, AsyncGenerator
)
from functools import wraps
from threading import Lock

from modules.types import (
    PerformanceMetric, HealthStatus, Timestamp, JSONDict
)
from modules.shared_constants import (
    PerformanceConstants, DEFAULT_CACHE_TTL
)
from modules.shared_utilities import SingletonMeta, CacheManager

logger = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
    """System resource usage metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_io_bytes: int
    timestamp: Timestamp = field(default_factory=datetime.now)


@dataclass
class RequestMetrics:
    """Request-level performance metrics."""
    endpoint: str
    duration: float
    status: str
    memory_delta: float
    timestamp: Timestamp
    user_id: Optional[int] = None
    chat_id: Optional[int] = None


@dataclass
class PerformanceAlert:
    """Performance alert information."""
    alert_type: str
    severity: str
    message: str
    metric_value: float
    threshold: float
    timestamp: Timestamp


class MetricsCollector:
    """Collects and aggregates performance metrics."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._metrics: DefaultDict[str, Deque[PerformanceMetric]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self._request_metrics: Deque[RequestMetrics] = deque(maxlen=max_history)
        self._resource_usage: Deque[ResourceUsage] = deque(maxlen=max_history)
        self._alerts: Deque[PerformanceAlert] = deque(maxlen=100)
        self._lock = Lock()
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a performance metric."""
        with self._lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                unit=unit,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self._metrics[name].append(metric)
    
    def record_request(
        self,
        endpoint: str,
        duration: float,
        status: str = "success",
        memory_delta: float = 0.0,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None
    ) -> None:
        """Record request-level metrics."""
        with self._lock:
            request_metric = RequestMetrics(
                endpoint=endpoint,
                duration=duration,
                status=status,
                memory_delta=memory_delta,
                timestamp=datetime.now(),
                user_id=user_id,
                chat_id=chat_id
            )
            self._request_metrics.append(request_metric)
    
    def record_resource_usage(self) -> None:
        """Record current system resource usage."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            # System-wide metrics
            system_memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('/')
            network_io = psutil.net_io_counters()
            
            with self._lock:
                usage = ResourceUsage(
                    cpu_percent=cpu_percent,
                    memory_percent=system_memory.percent,
                    memory_used_mb=memory_info.rss / 1024 / 1024,
                    memory_available_mb=system_memory.available / 1024 / 1024,
                    disk_usage_percent=disk_usage.percent,
                    network_io_bytes=network_io.bytes_sent + network_io.bytes_recv
                )
                self._resource_usage.append(usage)
                
                # Record individual metrics for easier querying
                self.record_metric("cpu_percent", cpu_percent, "percent")
                self.record_metric("memory_used_mb", usage.memory_used_mb, "MB")
                self.record_metric("memory_percent", system_memory.percent, "percent")
                
        except Exception as e:
            logger.warning(f"Failed to collect resource usage: {e}")
    
    def add_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_value: float,
        threshold: float
    ) -> None:
        """Add a performance alert."""
        with self._lock:
            alert = PerformanceAlert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                metric_value=metric_value,
                threshold=threshold,
                timestamp=datetime.now()
            )
            self._alerts.append(alert)
            logger.warning(f"Performance alert: {message}")
    
    def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[PerformanceMetric]:
        """Get metrics with optional filtering."""
        with self._lock:
            if name:
                metrics = list(self._metrics.get(name, []))
            else:
                metrics = []
                for metric_list in self._metrics.values():
                    metrics.extend(metric_list)
            
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            # Sort by timestamp
            metrics.sort(key=lambda m: m.timestamp, reverse=True)
            
            if limit:
                metrics = metrics[:limit]
            
            return metrics
    
    def get_request_metrics(
        self,
        endpoint: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[RequestMetrics]:
        """Get request metrics with optional filtering."""
        with self._lock:
            metrics = list(self._request_metrics)
            
            if endpoint:
                metrics = [m for m in metrics if m.endpoint == endpoint]
            
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            # Sort by timestamp
            metrics.sort(key=lambda m: m.timestamp, reverse=True)
            
            if limit:
                metrics = metrics[:limit]
            
            return metrics
    
    def get_resource_usage(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ResourceUsage]:
        """Get resource usage metrics."""
        with self._lock:
            usage_list = list(self._resource_usage)
            
            if since:
                usage_list = [u for u in usage_list if u.timestamp >= since]
            
            # Sort by timestamp
            usage_list.sort(key=lambda u: u.timestamp, reverse=True)
            
            if limit:
                usage_list = usage_list[:limit]
            
            return usage_list
    
    def get_alerts(
        self,
        severity: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[PerformanceAlert]:
        """Get performance alerts."""
        with self._lock:
            alerts = list(self._alerts)
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            if since:
                alerts = [a for a in alerts if a.timestamp >= since]
            
            # Sort by timestamp
            alerts.sort(key=lambda a: a.timestamp, reverse=True)
            
            return alerts
    
    def get_summary_stats(self, metric_name: str) -> Dict[str, float]:
        """Get summary statistics for a metric."""
        with self._lock:
            metrics = list(self._metrics.get(metric_name, []))
            
            if not metrics:
                return {}
            
            values = [m.value for m in metrics]
            
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'latest': values[-1] if values else 0
            }


class PerformanceMonitor(metaclass=SingletonMeta):
    """Main performance monitoring system."""
    
    def __init__(self):
        self.collector = MetricsCollector()
        self.cache_manager = CacheManager[Any](default_ttl=DEFAULT_CACHE_TTL)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        self._thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'memory_used_mb': 500.0,
            'request_duration': 5.0,
            'error_rate': 0.1
        }
        self.metric_collector = None
        self.resource_monitor = None
        self.request_tracker = None
        self._alert_handlers = []
        self._baseline_metrics = {}
        
    async def initialize(self) -> None:
        """Initialize the performance monitor components."""
        # Import here to avoid circular imports
        from tests.modules.test_performance_monitor_classes import (
            RequestTracker, ResourceMonitor
        )
        
        self.metric_collector = self.collector  # Use the existing collector
        self.resource_monitor = ResourceMonitor()
        self.request_tracker = RequestTracker()
        logger.info("Performance monitor initialized")
        
    async def shutdown(self) -> None:
        """Shutdown the performance monitor."""
        await self.stop_monitoring()
        self.metric_collector = None
        self.resource_monitor = None
        self.request_tracker = None
        logger.info("Performance monitor shut down")
        
    @asynccontextmanager
    async def track_request(self, endpoint: str) -> AsyncGenerator[None, None]:
        """Track a request using the request tracker."""
        request_id = None
        if self.request_tracker:
            request_id = self.request_tracker.start_request(endpoint)
        
        try:
            yield
        finally:
            if self.request_tracker and request_id:
                self.request_tracker.end_request(request_id, status_code=200)
                
    def increment_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a counter metric."""
        self.record_metric(name, value)
        
    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric."""
        self.record_metric(name, value)
        
    def record_histogram(self, name: str, value: float) -> None:
        """Record a histogram value."""
        self.record_metric(name, value)
        
    def add_alert_handler(self, handler: Callable[[PerformanceAlert], None]) -> None:
        """Add an alert handler."""
        self._alert_handlers.append(handler)
        
    def add_performance_alert(self, alert: PerformanceAlert) -> None:
        """Add a performance alert."""
        for handler in self._alert_handlers:
            handler(alert)
            
    async def process_alerts(self) -> None:
        """Process pending alerts."""
        # This is a placeholder for actual alert processing
        pass
        
    async def get_optimization_suggestions(self) -> List[str]:
        """Get performance optimization suggestions."""
        suggestions = []
        
        # Check CPU usage
        cpu_stats = self.collector.get_summary_stats('cpu_percent')
        if cpu_stats and cpu_stats.get('latest', 0) > 70:
            suggestions.append(f"High CPU usage detected ({cpu_stats.get('latest', 0):.1f}%). Consider optimizing CPU-intensive operations.")
            
        # Check memory usage
        memory_stats = self.collector.get_summary_stats('memory_percent')
        if memory_stats and memory_stats.get('latest', 0) > 80:
            suggestions.append(f"High memory usage detected ({memory_stats.get('latest', 0):.1f}%). Consider optimizing memory usage or increasing available memory.")
            
        # Add more suggestions based on other metrics
        if not suggestions:
            suggestions.append("No performance issues detected. System is running optimally.")
            
        return suggestions
        
    async def track_database_query(self, query: str) -> AsyncGenerator[None, None]:
        """Track a database query."""
        # This is a placeholder for actual database query tracking
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_metric(f"db_query_time", duration, "seconds", {"query": query[:50]})
            
    def record_cache_hit(self, cache_name: str) -> None:
        """Record a cache hit."""
        self.record_metric(f"cache_hit_{cache_name}", 1)
        
    def get_baseline_metrics(self, endpoint: str) -> Dict[str, Any]:
        """Get baseline metrics for an endpoint."""
        # Return stored baseline or create a new one
        if endpoint not in self._baseline_metrics:
            self._baseline_metrics[endpoint] = {
                "avg_response_time": 0.1,  # Default value
                "p95_response_time": 0.2,
                "error_rate": 0.0,
                "timestamp": datetime.now()
            }
        return self._baseline_metrics[endpoint]
        
    def detect_performance_regression(self, endpoint: str, baseline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect performance regression compared to baseline."""
        # Get current metrics
        recent_requests = self.collector.get_request_metrics(
            endpoint=endpoint,
            since=datetime.now() - timedelta(minutes=5)
        )
        
        if not recent_requests:
            return None
            
        # Calculate current metrics
        durations = [r.duration for r in recent_requests]
        avg_duration = sum(durations) / len(durations)
        
        # Compare with baseline
        if avg_duration > baseline["avg_response_time"] * 1.5:  # 50% slower
            return {
                "endpoint": endpoint,
                "baseline_avg": baseline["avg_response_time"],
                "current_avg": avg_duration,
                "degradation_factor": avg_duration / baseline["avg_response_time"],
                "confidence": 0.9,
                "timestamp": datetime.now()
            }
            
        return None
        
    async def detect_performance_issues(self) -> List[Dict[str, Any]]:
        """Detect performance issues."""
        # This is a placeholder for actual performance issue detection
        return []
    
    async def start_monitoring(self, interval: int = 60) -> None:
        """Start continuous performance monitoring."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval)
        )
        logger.info(f"Performance monitoring started with {interval}s interval")
    
    async def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        while self._is_monitoring:
            try:
                # Collect resource usage
                self.collector.record_resource_usage()
                
                # Check thresholds and generate alerts
                await self._check_thresholds()
                
                # Cleanup old metrics
                await self._cleanup_old_metrics()
                
                # Force garbage collection periodically
                if datetime.now().minute % 10 == 0:
                    gc.collect()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    async def _check_thresholds(self) -> None:
        """Check performance thresholds and generate alerts."""
        # Check CPU usage
        cpu_stats = self.collector.get_summary_stats('cpu_percent')
        if cpu_stats and cpu_stats['latest'] > self._thresholds['cpu_percent']:
            self.collector.add_alert(
                alert_type="cpu_high",
                severity="warning",
                message=f"High CPU usage: {cpu_stats['latest']:.1f}%",
                metric_value=cpu_stats['latest'],
                threshold=self._thresholds['cpu_percent']
            )
        
        # Check memory usage
        memory_stats = self.collector.get_summary_stats('memory_used_mb')
        if memory_stats and memory_stats['latest'] > self._thresholds['memory_used_mb']:
            self.collector.add_alert(
                alert_type="memory_high",
                severity="warning",
                message=f"High memory usage: {memory_stats['latest']:.1f}MB",
                metric_value=memory_stats['latest'],
                threshold=self._thresholds['memory_used_mb']
            )
        
        # Check request durations
        recent_requests = self.collector.get_request_metrics(
            since=datetime.now() - timedelta(minutes=5)
        )
        slow_requests = [r for r in recent_requests 
                        if r.duration > self._thresholds['request_duration']]
        
        if len(slow_requests) > 5:  # More than 5 slow requests in 5 minutes
            avg_duration = sum(r.duration for r in slow_requests) / len(slow_requests)
            self.collector.add_alert(
                alert_type="slow_requests",
                severity="warning",
                message=f"Multiple slow requests detected: avg {avg_duration:.2f}s",
                metric_value=avg_duration,
                threshold=self._thresholds['request_duration']
            )
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics to prevent memory leaks."""
        # This is handled by the deque maxlen, but we can add additional cleanup here
        self.cache_manager.cleanup_expired()
    
    @asynccontextmanager
    async def measure_request(
        self,
        endpoint: str,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None
    ) -> AsyncGenerator[None, None]:
        """Context manager to measure request performance."""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            yield
            status = "success"
        except Exception as e:
            status = f"error_{type(e).__name__}"
            raise
        finally:
            duration = time.time() - start_time
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_delta = end_memory - start_memory
            
            self.collector.record_request(
                endpoint=endpoint,
                duration=duration,
                status=status,
                memory_delta=memory_delta,
                user_id=user_id,
                chat_id=chat_id
            )
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a custom metric."""
        self.collector.record_metric(name, value, unit, tags)
    
    def get_health_status(self) -> HealthStatus:
        """Get overall system health status."""
        # Get recent resource usage
        recent_usage = self.collector.get_resource_usage(
            since=datetime.now() - timedelta(minutes=5),
            limit=1
        )
        
        # Get recent alerts
        recent_alerts = self.collector.get_alerts(
            since=datetime.now() - timedelta(minutes=10)
        )
        
        # Determine health status
        is_healthy = True
        status_message = "System operating normally"
        
        if recent_usage:
            usage = recent_usage[0]
            if (usage.cpu_percent > self._thresholds['cpu_percent'] or
                usage.memory_used_mb > self._thresholds['memory_used_mb']):
                is_healthy = False
                status_message = "High resource usage detected"
        
        if len(recent_alerts) > 3:  # More than 3 alerts in 10 minutes
            is_healthy = False
            status_message = "Multiple performance alerts"
        
        # Get performance metrics
        metrics = []
        for metric_name in ['cpu_percent', 'memory_used_mb', 'memory_percent']:
            stats = self.collector.get_summary_stats(metric_name)
            if stats:
                metrics.append(PerformanceMetric(
                    name=metric_name,
                    value=stats['latest'],
                    unit="percent" if "percent" in metric_name else "MB",
                    timestamp=datetime.now(),
                    tags={}
                ))
        
        return HealthStatus(
            service_name="performance_monitor",
            is_healthy=is_healthy,
            status_message=status_message,
            last_check=datetime.now(),
            metrics=metrics
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        return {
            'timestamp': now.isoformat(),
            'health_status': self.get_health_status().__dict__,
            'resource_usage': {
                'current': self.collector.get_resource_usage(limit=1),
                'last_hour_avg': self._get_avg_resource_usage(last_hour),
                'last_day_avg': self._get_avg_resource_usage(last_day)
            },
            'request_metrics': {
                'last_hour': len(self.collector.get_request_metrics(since=last_hour)),
                'slow_requests': len([
                    r for r in self.collector.get_request_metrics(since=last_hour)
                    if r.duration > self._thresholds['request_duration']
                ]),
                'error_requests': len([
                    r for r in self.collector.get_request_metrics(since=last_hour)
                    if r.status.startswith('error')
                ])
            },
            'alerts': {
                'last_hour': len(self.collector.get_alerts(since=last_hour)),
                'critical': len(self.collector.get_alerts(severity='critical')),
                'warnings': len(self.collector.get_alerts(severity='warning'))
            },
            'top_metrics': {
                name: self.collector.get_summary_stats(name)
                for name in ['cpu_percent', 'memory_used_mb', 'request_duration']
            }
        }
    
    def _get_avg_resource_usage(self, since: datetime) -> Dict[str, float]:
        """Get average resource usage since a given time."""
        usage_list = self.collector.get_resource_usage(since=since)
        
        if not usage_list:
            return {}
        
        return {
            'cpu_percent': sum(u.cpu_percent for u in usage_list) / len(usage_list),
            'memory_percent': sum(u.memory_percent for u in usage_list) / len(usage_list),
            'memory_used_mb': sum(u.memory_used_mb for u in usage_list) / len(usage_list)
        }


# Decorators for performance monitoring
def monitor_performance(endpoint: str):
    """Decorator to monitor function performance."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            monitor = PerformanceMonitor()
            
            # Try to extract user_id and chat_id from args
            user_id = None
            chat_id = None
            
            # Look for Update object in args
            for arg in args:
                if hasattr(arg, 'effective_user') and arg.effective_user:
                    user_id = arg.effective_user.id
                if hasattr(arg, 'effective_chat') and arg.effective_chat:
                    chat_id = arg.effective_chat.id
                break
            
            async with monitor.measure_request(endpoint, user_id, chat_id):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def track_memory_usage(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator to track memory usage of a function."""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        monitor = PerformanceMonitor()
        
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        result = await func(*args, **kwargs)
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        memory_delta = end_memory - start_memory
        monitor.record_metric(
            name=f"memory_delta_{func.__name__}",
            value=memory_delta,
            unit="MB",
            tags={'function': func.__name__}
        )
        
        return result
    
    return wrapper


# Global performance monitor instance
performance_monitor = PerformanceMonitor()