"""
Test implementation classes for performance monitoring tests.

These classes provide the necessary implementations for the test cases in test_performance_monitor.py.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Callable
from contextlib import contextmanager


class ResourceMonitor:
    """Resource monitoring implementation for tests."""
    
    def __init__(self):
        self.alert_handlers = []
        self.is_monitoring = False
    
    async def start_monitoring(self):
        """Start monitoring resources."""
        self.is_monitoring = True
    
    async def stop_monitoring(self):
        """Stop monitoring resources."""
        self.is_monitoring = False
    
    def get_cpu_usage(self):
        """Get current CPU usage."""
        return 5.0  # Mock value
    
    def get_memory_usage(self):
        """Get current memory usage."""
        return {
            "used": 500,
            "available": 1500,
            "percent": 25.0
        }
    
    def get_disk_usage(self):
        """Get current disk usage."""
        return {
            "used": 50000,
            "free": 150000,
            "percent": 25.0
        }
    
    def get_network_io(self):
        """Get current network I/O stats."""
        return {
            "bytes_sent": 1024,
            "bytes_recv": 2048
        }
    
    def add_alert_handler(self, handler):
        """Add an alert handler."""
        self.alert_handlers.append(handler)
    
    def add_alert(self, alert):
        """Add an alert."""
        for handler in self.alert_handlers:
            handler(alert)


class RequestTracker:
    """Request tracking implementation for tests."""
    
    def __init__(self):
        self.requests = {}
        self.start_times = {}
        self.status_codes = {}
        self.response_sizes = {}
        self.endpoints = {}
        self.start_timestamp = time.time()
    
    def start_request(self, endpoint: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start tracking a request."""
        request_id = str(uuid.uuid4())
        self.requests[request_id] = {
            "endpoint": endpoint,
            "start_time": time.time(),
            "metadata": metadata or {}
        }
        
        if endpoint not in self.endpoints:
            self.endpoints[endpoint] = {"count": 0, "total_time": 0.0}
        
        self.endpoints[endpoint]["count"] += 1
        self.start_times[request_id] = time.time()
        
        return request_id
    
    def end_request(self, request_id: str, status_code: int = 200, response_size: int = 0) -> None:
        """End tracking a request."""
        if request_id not in self.requests:
            return
        
        end_time = time.time()
        duration = end_time - self.start_times[request_id]
        
        self.requests[request_id]["duration"] = duration
        self.requests[request_id]["status_code"] = status_code
        self.requests[request_id]["response_size"] = response_size
        
        endpoint = self.requests[request_id]["endpoint"]
        self.endpoints[endpoint]["total_time"] += duration
        
        # Track status codes
        if str(status_code) not in self.status_codes:
            self.status_codes[str(status_code)] = 0
        self.status_codes[str(status_code)] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get request metrics."""
        total_requests = len(self.requests)
        total_duration = sum(req.get("duration", 0) for req in self.requests.values())
        avg_response_time = total_duration / total_requests if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "avg_response_time": avg_response_time,
            "endpoints": self.endpoints,
            "status_codes": self.status_codes
        }
    
    def get_error_rate(self) -> float:
        """Get error rate percentage."""
        total_requests = len(self.requests)
        if total_requests == 0:
            return 0.0
        
        error_count = sum(
            1 for req in self.requests.values() 
            if req.get("status_code", 200) >= 400
        )
        
        return (error_count / total_requests) * 100
    
    def get_throughput(self) -> float:
        """Get requests per second."""
        total_time = time.time() - self.start_timestamp
        if total_time <= 0:
            return 0.0
        
        return len(self.requests) / total_time


class MemoryProfiler:
    """Memory profiling implementation for tests."""
    
    def __init__(self):
        self.snapshots = []
        self.tracking = False
        self.usage_history = []
        self.start_time = None
    
    def take_snapshot(self) -> Dict[str, Any]:
        """Take a memory snapshot."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        
        # Get memory usage
        total_memory = 0
        objects_by_type = {}
        
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            obj_size = sys.getsizeof(obj)
            
            if obj_type not in objects_by_type:
                objects_by_type[obj_type] = {"count": 0, "size": 0}
            
            objects_by_type[obj_type]["count"] += 1
            objects_by_type[obj_type]["size"] += obj_size
            total_memory += obj_size
        
        snapshot = {
            "timestamp": datetime.now(),
            "total_memory": total_memory,
            "objects_by_type": objects_by_type
        }
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def start_tracking(self) -> None:
        """Start tracking memory usage over time."""
        self.tracking = True
        self.start_time = time.time()
        self.usage_history = []
        
        # Take initial snapshot
        self._record_usage()
    
    def stop_tracking(self) -> None:
        """Stop tracking memory usage."""
        self.tracking = False
    
    def _record_usage(self) -> None:
        """Record current memory usage."""
        import psutil
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        self.usage_history.append({
            "timestamp": time.time() - self.start_time,
            "memory_mb": memory_info.rss / 1024 / 1024
        })
    
    def get_usage_history(self) -> List[Dict[str, Any]]:
        """Get memory usage history."""
        return self.usage_history
    
    def analyze_leaks(self) -> Dict[str, Any]:
        """Analyze potential memory leaks."""
        if len(self.snapshots) < 2:
            return {"memory_growth": 0, "potential_leaks": []}
        
        first = self.snapshots[0]
        last = self.snapshots[-1]
        
        memory_growth = last["total_memory"] - first["total_memory"]
        potential_leaks = []
        
        for obj_type, last_info in last["objects_by_type"].items():
            if obj_type in first["objects_by_type"]:
                first_info = first["objects_by_type"][obj_type]
                count_diff = last_info["count"] - first_info["count"]
                size_diff = last_info["size"] - first_info["size"]
                
                if count_diff > 10 and size_diff > 1024 * 1024:  # More than 10 objects and 1MB
                    potential_leaks.append({
                        "type": obj_type,
                        "count_increase": count_diff,
                        "size_increase_mb": size_diff / 1024 / 1024
                    })
            else:
                # New object type
                if last_info["count"] > 10 and last_info["size"] > 1024 * 1024:
                    potential_leaks.append({
                        "type": obj_type,
                        "count_increase": last_info["count"],
                        "size_increase_mb": last_info["size"] / 1024 / 1024
                    })
        
        return {
            "memory_growth": memory_growth,
            "potential_leaks": potential_leaks
        }


class CacheMonitor:
    """Cache monitoring implementation for tests."""
    
    def __init__(self):
        self.cache_stats = {}
        self.cache_sizes = {}
        self.eviction_stats = {}
    
    def record_hit(self, cache_name: str) -> None:
        """Record a cache hit."""
        if cache_name not in self.cache_stats:
            self.cache_stats[cache_name] = {"hits": 0, "misses": 0}
        
        self.cache_stats[cache_name]["hits"] += 1
    
    def record_miss(self, cache_name: str) -> None:
        """Record a cache miss."""
        if cache_name not in self.cache_stats:
            self.cache_stats[cache_name] = {"hits": 0, "misses": 0}
        
        self.cache_stats[cache_name]["misses"] += 1
    
    def update_cache_size(self, cache_name: str, size: int) -> None:
        """Update cache size."""
        self.cache_sizes[cache_name] = size
    
    def record_eviction(self, cache_name: str, reason: str) -> None:
        """Record a cache eviction."""
        if cache_name not in self.eviction_stats:
            self.eviction_stats[cache_name] = {"total": 0}
        
        if reason not in self.eviction_stats[cache_name]:
            self.eviction_stats[cache_name][reason] = 0
        
        self.eviction_stats[cache_name][reason] += 1
        self.eviction_stats[cache_name]["total"] += 1
    
    def get_cache_stats(self, cache_name: str) -> Dict[str, Any]:
        """Get cache statistics."""
        if cache_name not in self.cache_stats:
            return {"hits": 0, "misses": 0, "hit_rate": 0.0}
        
        stats = self.cache_stats[cache_name]
        total = stats["hits"] + stats["misses"]
        hit_rate = stats["hits"] / total if total > 0 else 0.0
        
        return {
            "hits": stats["hits"],
            "misses": stats["misses"],
            "hit_rate": hit_rate
        }
    
    def get_total_cache_size(self) -> int:
        """Get total cache size."""
        return sum(self.cache_sizes.values())
    
    def get_cache_sizes(self) -> Dict[str, int]:
        """Get cache sizes by cache name."""
        return self.cache_sizes
    
    def get_eviction_stats(self, cache_name: str) -> Dict[str, int]:
        """Get eviction statistics."""
        if cache_name not in self.eviction_stats:
            return {"total": 0}
        
        return self.eviction_stats[cache_name]


class DatabasePerformanceMonitor:
    """Database performance monitoring implementation for tests."""
    
    def __init__(self):
        self.query_stats = {}
        self.pool_stats = {"active": 0, "idle": 0, "max": 0}
        self.slow_query_threshold = 0.1
        self.slow_queries = []
    
    @contextmanager
    def track_query(self, query: str):
        """Track a database query execution."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            if query not in self.query_stats:
                self.query_stats[query] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "min_duration": float('inf'),
                    "max_duration": 0.0
                }
            
            self.query_stats[query]["count"] += 1
            self.query_stats[query]["total_duration"] += duration
            self.query_stats[query]["min_duration"] = min(
                self.query_stats[query]["min_duration"], duration
            )
            self.query_stats[query]["max_duration"] = max(
                self.query_stats[query]["max_duration"], duration
            )
            
            # Check for slow query
            if duration > self.slow_query_threshold:
                self.slow_queries.append({
                    "query": query,
                    "duration": duration,
                    "timestamp": datetime.now()
                })
    
    def update_pool_stats(self, active_connections: int, idle_connections: int, max_connections: int) -> None:
        """Update connection pool statistics."""
        self.pool_stats = {
            "active": active_connections,
            "idle": idle_connections,
            "max": max_connections,
            "utilization": active_connections / max_connections if max_connections > 0 else 0
        }
    
    def set_slow_query_threshold(self, threshold: float) -> None:
        """Set the threshold for slow queries in seconds."""
        self.slow_query_threshold = threshold
    
    def get_query_stats(self) -> List[Dict[str, Any]]:
        """Get query statistics."""
        result = []
        
        for query, stats in self.query_stats.items():
            avg_duration = stats["total_duration"] / stats["count"] if stats["count"] > 0 else 0
            
            result.append({
                "query": query,
                "count": stats["count"],
                "avg_duration": avg_duration,
                "min_duration": stats["min_duration"] if stats["min_duration"] != float('inf') else 0,
                "max_duration": stats["max_duration"]
            })
        
        return result
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return self.pool_stats
    
    def get_slow_queries(self) -> List[Dict[str, Any]]:
        """Get slow queries."""
        return sorted(self.slow_queries, key=lambda q: q["duration"], reverse=True)