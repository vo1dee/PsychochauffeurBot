"""
Performance monitoring and alerting system for the user leveling service.

This module provides comprehensive performance monitoring, alerting, and
optimization recommendations specifically for the leveling system.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from modules.performance_monitor import performance_monitor
from modules.service_error_boundary import health_monitor

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PerformanceAlert:
    """Performance alert for the leveling system."""
    timestamp: datetime
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold: float
    message: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceThresholds:
    """Performance thresholds for monitoring."""
    # Processing time thresholds (seconds)
    message_processing_warning: float = 0.1
    message_processing_critical: float = 0.5
    
    # Database operation thresholds (seconds)
    db_query_warning: float = 0.05
    db_query_critical: float = 0.2
    
    # Cache performance thresholds
    cache_hit_rate_warning: float = 0.7  # 70%
    cache_hit_rate_critical: float = 0.5  # 50%
    
    # Error rate thresholds (per minute)
    error_rate_warning: int = 5
    error_rate_critical: int = 20
    
    # Memory usage thresholds (MB)
    memory_usage_warning: float = 100.0
    memory_usage_critical: float = 200.0
    
    # Queue/backlog thresholds
    processing_queue_warning: int = 100
    processing_queue_critical: int = 500


class LevelingPerformanceMonitor:
    """
    Comprehensive performance monitoring for the leveling system.
    
    Features:
    - Real-time performance metrics collection
    - Threshold-based alerting
    - Performance trend analysis
    - Optimization recommendations
    - Health status reporting
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.thresholds = PerformanceThresholds()
        self.alerts: List[PerformanceAlert] = []
        self.alert_handlers: List[Callable[[PerformanceAlert], None]] = []
        
        # Performance metrics tracking
        self.metrics_history: Dict[str, List[tuple[datetime, float]]] = {}
        self.last_cleanup = datetime.now()
        self.cleanup_interval = 3600  # 1 hour
        
        # Performance baselines
        self.baselines: Dict[str, float] = {
            'message_processing_time': 0.05,  # 50ms baseline
            'db_query_time': 0.02,  # 20ms baseline
            'cache_hit_rate': 0.8,  # 80% baseline
            'error_rate': 0.0  # 0 errors baseline
        }
        
        # Optimization recommendations cache
        self.last_recommendations_update = datetime.now()
        self.recommendations_cache: List[str] = []
    
    def record_metric(self, metric_name: str, value: float, context: Optional[Dict[str, Any]] = None) -> None:
        """Record a performance metric and check thresholds."""
        timestamp = datetime.now()
        
        # Store metric in history
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = []
        
        self.metrics_history[metric_name].append((timestamp, value))
        
        # Keep only recent history (last 24 hours)
        cutoff_time = timestamp - timedelta(hours=24)
        self.metrics_history[metric_name] = [
            (ts, val) for ts, val in self.metrics_history[metric_name]
            if ts > cutoff_time
        ]
        
        # Check thresholds and generate alerts
        self._check_thresholds(metric_name, value, timestamp, context or {})
        
        # Record in global performance monitor
        performance_monitor.record_metric(
            f"leveling_{metric_name}",
            value,
            tags={'component': 'leveling_system', **(context or {})}
        )
    
    def _check_thresholds(self, metric_name: str, value: float, timestamp: datetime, context: Dict[str, Any]) -> None:
        """Check if metric value exceeds thresholds and generate alerts."""
        alerts_to_generate = []
        
        # Message processing time thresholds
        if metric_name == "message_processing_time":
            if value > self.thresholds.message_processing_critical:
                alerts_to_generate.append((AlertSeverity.CRITICAL, self.thresholds.message_processing_critical))
            elif value > self.thresholds.message_processing_warning:
                alerts_to_generate.append((AlertSeverity.WARNING, self.thresholds.message_processing_warning))
        
        # Database query time thresholds
        elif metric_name.endswith("_db_time"):
            if value > self.thresholds.db_query_critical:
                alerts_to_generate.append((AlertSeverity.CRITICAL, self.thresholds.db_query_critical))
            elif value > self.thresholds.db_query_warning:
                alerts_to_generate.append((AlertSeverity.WARNING, self.thresholds.db_query_warning))
        
        # Cache hit rate thresholds (inverted - lower is worse)
        elif metric_name == "cache_hit_rate":
            if value < self.thresholds.cache_hit_rate_critical:
                alerts_to_generate.append((AlertSeverity.CRITICAL, self.thresholds.cache_hit_rate_critical))
            elif value < self.thresholds.cache_hit_rate_warning:
                alerts_to_generate.append((AlertSeverity.WARNING, self.thresholds.cache_hit_rate_warning))
        
        # Error rate thresholds
        elif metric_name == "error_rate":
            if value > self.thresholds.error_rate_critical:
                alerts_to_generate.append((AlertSeverity.CRITICAL, self.thresholds.error_rate_critical))
            elif value > self.thresholds.error_rate_warning:
                alerts_to_generate.append((AlertSeverity.WARNING, self.thresholds.error_rate_warning))
        
        # Generate alerts
        for severity, threshold in alerts_to_generate:
            alert = PerformanceAlert(
                timestamp=timestamp,
                severity=severity,
                metric_name=metric_name,
                current_value=value,
                threshold=threshold,
                message=self._generate_alert_message(metric_name, value, threshold, severity),
                context=context
            )
            
            self._add_alert(alert)
    
    def _generate_alert_message(self, metric_name: str, value: float, threshold: float, severity: AlertSeverity) -> str:
        """Generate a human-readable alert message."""
        if metric_name == "message_processing_time":
            return f"Leveling message processing is slow: {value:.3f}s (threshold: {threshold:.3f}s)"
        elif metric_name.endswith("_db_time"):
            return f"Database operation is slow: {value:.3f}s (threshold: {threshold:.3f}s)"
        elif metric_name == "cache_hit_rate":
            return f"Cache hit rate is low: {value:.1%} (threshold: {threshold:.1%})"
        elif metric_name == "error_rate":
            return f"Error rate is high: {value:.1f}/min (threshold: {threshold:.1f}/min)"
        else:
            return f"Performance threshold exceeded for {metric_name}: {value} (threshold: {threshold})"
    
    def _add_alert(self, alert: PerformanceAlert) -> None:
        """Add an alert and notify handlers."""
        # Avoid duplicate alerts (same metric within 5 minutes)
        recent_cutoff = alert.timestamp - timedelta(minutes=5)
        duplicate_alert = any(
            existing.metric_name == alert.metric_name and
            existing.severity == alert.severity and
            existing.timestamp > recent_cutoff
            for existing in self.alerts
        )
        
        if not duplicate_alert:
            self.alerts.append(alert)
            
            # Keep only recent alerts (last 24 hours)
            cutoff_time = alert.timestamp - timedelta(hours=24)
            self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]
            
            # Notify alert handlers
            for handler in self.alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Error in alert handler: {e}")
            
            # Log the alert
            log_level = {
                AlertSeverity.INFO: logging.INFO,
                AlertSeverity.WARNING: logging.WARNING,
                AlertSeverity.ERROR: logging.ERROR,
                AlertSeverity.CRITICAL: logging.CRITICAL
            }.get(alert.severity, logging.WARNING)
            
            logger.log(log_level, f"Leveling performance alert: {alert.message}")
    
    def add_alert_handler(self, handler: Callable[[PerformanceAlert], None]) -> None:
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
    
    def get_recent_alerts(self, hours: int = 1, severity: Optional[AlertSeverity] = None) -> List[PerformanceAlert]:
        """Get recent alerts within the specified time window."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_metric_statistics(self, metric_name: str, hours: int = 1) -> Dict[str, float]:
        """Get statistics for a specific metric."""
        if metric_name not in self.metrics_history:
            return {}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_values = [
            value for timestamp, value in self.metrics_history[metric_name]
            if timestamp > cutoff_time
        ]
        
        if not recent_values:
            return {}
        
        return {
            'count': len(recent_values),
            'min': min(recent_values),
            'max': max(recent_values),
            'avg': sum(recent_values) / len(recent_values),
            'latest': recent_values[-1] if recent_values else 0
        }
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """Analyze performance trends over time."""
        trends = {}
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for metric_name, history in self.metrics_history.items():
            recent_data = [(ts, val) for ts, val in history if ts > cutoff_time]
            
            if len(recent_data) < 2:
                continue
            
            # Calculate trend (simple linear regression slope)
            n = len(recent_data)
            sum_x = sum(i for i, _ in enumerate(recent_data))
            sum_y = sum(val for _, val in recent_data)
            sum_xy = sum(i * val for i, (_, val) in enumerate(recent_data))
            sum_x2 = sum(i * i for i, _ in enumerate(recent_data))
            
            if n * sum_x2 - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                
                # Determine trend direction
                if abs(slope) < 0.001:
                    trend_direction = "stable"
                elif slope > 0:
                    trend_direction = "increasing"
                else:
                    trend_direction = "decreasing"
                
                trends[metric_name] = {
                    'direction': trend_direction,
                    'slope': slope,
                    'data_points': n,
                    'time_span_hours': hours
                }
        
        return trends
    
    def get_optimization_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations."""
        now = datetime.now()
        
        # Update recommendations every 30 minutes
        if (now - self.last_recommendations_update).total_seconds() < 1800:
            return self.recommendations_cache
        
        recommendations = []
        
        # Analyze recent performance data
        recent_alerts = self.get_recent_alerts(hours=1)
        trends = self.get_performance_trends(hours=6)
        
        # Check for slow message processing
        processing_stats = self.get_metric_statistics("message_processing_time", hours=1)
        if processing_stats and processing_stats.get('avg', 0) > 0.1:
            recommendations.append(
                f"Message processing is averaging {processing_stats['avg']:.3f}s. "
                "Consider optimizing database queries or enabling more aggressive caching."
            )
        
        # Check cache performance
        cache_stats = self.get_metric_statistics("cache_hit_rate", hours=1)
        if cache_stats and cache_stats.get('avg', 1.0) < 0.8:
            recommendations.append(
                f"Cache hit rate is {cache_stats['avg']:.1%}. "
                "Consider increasing cache TTL or warming up frequently accessed data."
            )
        
        # Check database performance
        db_stats = self.get_metric_statistics("db_query_time", hours=1)
        if db_stats and db_stats.get('avg', 0) > 0.05:
            recommendations.append(
                f"Database queries are averaging {db_stats['avg']:.3f}s. "
                "Consider adding database indexes or optimizing query patterns."
            )
        
        # Check error trends
        if "error_rate" in trends and trends["error_rate"]["direction"] == "increasing":
            recommendations.append(
                "Error rate is increasing. Review recent error logs and consider implementing "
                "additional error handling or circuit breakers."
            )
        
        # Check for critical alerts
        critical_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            recommendations.append(
                f"There are {len(critical_alerts)} critical performance alerts. "
                "Immediate attention required to prevent service degradation."
            )
        
        # Memory usage recommendations
        memory_stats = self.get_metric_statistics("memory_usage", hours=1)
        if memory_stats and memory_stats.get('max', 0) > 150:
            recommendations.append(
                f"Peak memory usage is {memory_stats['max']:.1f}MB. "
                "Consider implementing memory cleanup routines or reducing cache sizes."
            )
        
        # Default recommendation if no issues found
        if not recommendations:
            recommendations.append("Performance is within normal parameters. No optimizations needed.")
        
        self.recommendations_cache = recommendations
        self.last_recommendations_update = now
        
        return recommendations
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the leveling system."""
        now = datetime.now()
        recent_alerts = self.get_recent_alerts(hours=1)
        
        # Determine health status
        critical_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
        error_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.ERROR]
        warning_alerts = [a for a in recent_alerts if a.severity == AlertSeverity.WARNING]
        
        if critical_alerts:
            health_status = "critical"
            status_message = f"{len(critical_alerts)} critical performance issues detected"
        elif error_alerts:
            health_status = "degraded"
            status_message = f"{len(error_alerts)} performance errors detected"
        elif warning_alerts:
            health_status = "warning"
            status_message = f"{len(warning_alerts)} performance warnings detected"
        else:
            health_status = "healthy"
            status_message = "All performance metrics within normal ranges"
        
        # Get key metrics
        key_metrics = {}
        for metric in ["message_processing_time", "cache_hit_rate", "error_rate"]:
            stats = self.get_metric_statistics(metric, hours=1)
            if stats:
                key_metrics[metric] = stats
        
        return {
            'timestamp': now.isoformat(),
            'health_status': health_status,
            'status_message': status_message,
            'alerts_summary': {
                'critical': len(critical_alerts),
                'error': len(error_alerts),
                'warning': len(warning_alerts),
                'total': len(recent_alerts)
            },
            'key_metrics': key_metrics,
            'recommendations': self.get_optimization_recommendations()
        }
    
    def cleanup_old_data(self) -> None:
        """Clean up old performance data to prevent memory leaks."""
        now = datetime.now()
        
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return
        
        cutoff_time = now - timedelta(hours=24)
        
        # Clean up metrics history
        for metric_name in list(self.metrics_history.keys()):
            self.metrics_history[metric_name] = [
                (ts, val) for ts, val in self.metrics_history[metric_name]
                if ts > cutoff_time
            ]
            
            # Remove empty metric histories
            if not self.metrics_history[metric_name]:
                del self.metrics_history[metric_name]
        
        # Clean up alerts
        self.alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
        
        self.last_cleanup = now
        logger.debug("Cleaned up old performance monitoring data")


# Global leveling performance monitor instance
leveling_performance_monitor = LevelingPerformanceMonitor()


# Convenience functions for easy integration
def record_processing_time(operation: str, duration: float, context: Optional[Dict[str, Any]] = None) -> None:
    """Record processing time for a leveling operation."""
    leveling_performance_monitor.record_metric(f"{operation}_time", duration, context)


def record_database_time(operation: str, duration: float, context: Optional[Dict[str, Any]] = None) -> None:
    """Record database operation time."""
    leveling_performance_monitor.record_metric(f"{operation}_db_time", duration, context)


def record_cache_performance(hit_rate: float, context: Optional[Dict[str, Any]] = None) -> None:
    """Record cache performance metrics."""
    leveling_performance_monitor.record_metric("cache_hit_rate", hit_rate, context)


def record_error_rate(errors_per_minute: float, context: Optional[Dict[str, Any]] = None) -> None:
    """Record error rate metrics."""
    leveling_performance_monitor.record_metric("error_rate", errors_per_minute, context)


def get_performance_report() -> Dict[str, Any]:
    """Get a comprehensive performance report."""
    return leveling_performance_monitor.get_health_status()