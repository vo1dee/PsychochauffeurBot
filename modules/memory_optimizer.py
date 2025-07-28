"""
Memory optimization utilities and garbage collection management.

This module provides tools for optimizing memory usage, preventing memory leaks,
and managing garbage collection in the PsychoChauffeur bot.
"""

import gc
import logging
import weakref
import asyncio
from typing import Dict, List, Optional, Any, Set, Callable, TypeVar, Generic
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps

import psutil

from modules.types import Timestamp
from modules.shared_utilities import SingletonMeta
from modules.shared_constants import PerformanceConstants

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: Timestamp
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    percent: float  # Memory percentage
    available_mb: float
    gc_objects: int
    gc_collections: Dict[int, int]


@dataclass
class ObjectTracker:
    """Tracks object creation and destruction."""
    object_type: str
    created_count: int = 0
    destroyed_count: int = 0
    current_count: int = 0
    peak_count: int = 0
    last_updated: Optional[Timestamp] = None


class WeakObjectRegistry(Generic[T]):
    """Registry for tracking objects using weak references."""
    
    def __init__(self, name: str):
        self.name = name
        self._objects: Set[weakref.ref[T]] = set()
        self._cleanup_callbacks: List[Callable[[], None]] = []
    
    def register(self, obj: T, cleanup_callback: Optional[Callable[[], None]] = None) -> None:
        """Register an object for tracking."""
        def remove_ref(ref: weakref.ref[T]) -> None:
            self._objects.discard(ref)
            if cleanup_callback:
                try:
                    cleanup_callback()
                except Exception as e:
                    logger.warning(f"Cleanup callback failed for {self.name}: {e}")
        
        ref = weakref.ref(obj, remove_ref)
        self._objects.add(ref)
    
    def get_count(self) -> int:
        """Get current count of tracked objects."""
        # Clean up dead references
        dead_refs = {ref for ref in self._objects if ref() is None}
        self._objects -= dead_refs
        return len(self._objects)
    
    def get_objects(self) -> List[T]:
        """Get list of currently tracked objects."""
        objects = []
        dead_refs = set()
        
        for ref in self._objects:
            obj = ref()
            if obj is not None:
                objects.append(obj)
            else:
                dead_refs.add(ref)
        
        # Clean up dead references
        self._objects -= dead_refs
        return objects


class MemoryOptimizer(metaclass=SingletonMeta):
    """Memory optimization and monitoring system."""
    
    def __init__(self) -> None:
        self._snapshots: List[MemorySnapshot] = []
        self._object_trackers: Dict[str, ObjectTracker] = defaultdict(lambda: ObjectTracker(""))
        self._weak_registries: Dict[str, WeakObjectRegistry[Any]] = {}
        self._gc_task: Optional[asyncio.Task[None]] = None
        self._monitoring_task: Optional[asyncio.Task[None]] = None
        self._is_monitoring = False
        
        # Memory thresholds
        self._memory_threshold_mb = PerformanceConstants.HIGH_MEMORY_THRESHOLD
        self._gc_threshold_objects = 10000
        
        # Configure garbage collection
        self._configure_gc()
    
    def _configure_gc(self) -> None:
        """Configure garbage collection settings."""
        # Set more aggressive GC thresholds
        gc.set_threshold(700, 10, 10)  # More frequent collection
        
        # Enable automatic garbage collection
        gc.enable()
        
        logger.info(f"Garbage collection configured: thresholds={gc.get_threshold()}")
    
    async def start_monitoring(self, interval: int = 60) -> None:
        """Start memory monitoring."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop(interval))
        logger.info(f"Memory monitoring started with {interval}s interval")
    
    async def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Memory monitoring stopped")
    
    async def _monitoring_loop(self, interval: int) -> None:
        """Main memory monitoring loop."""
        while self._is_monitoring:
            try:
                # Take memory snapshot
                snapshot = self._take_snapshot()
                self._snapshots.append(snapshot)
                
                # Keep only last 100 snapshots
                if len(self._snapshots) > 100:
                    self._snapshots = self._snapshots[-100:]
                
                # Check for memory issues
                await self._check_memory_health(snapshot)
                
                # Periodic cleanup
                if len(self._snapshots) % 10 == 0:
                    await self._perform_cleanup()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    def _take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot."""
        process = psutil.Process()
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        
        # Get garbage collection stats
        gc_stats = {}
        for i in range(3):
            gc_stats[i] = gc.get_count()[i]
        
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            percent=system_memory.percent,
            available_mb=system_memory.available / 1024 / 1024,
            gc_objects=len(gc.get_objects()),
            gc_collections=gc_stats
        )
        
        return snapshot
    
    async def _check_memory_health(self, snapshot: MemorySnapshot) -> None:
        """Check memory health and trigger cleanup if needed."""
        # Check if memory usage is too high
        if snapshot.rss_mb > self._memory_threshold_mb:
            logger.warning(
                f"High memory usage detected: {snapshot.rss_mb:.1f}MB "
                f"(threshold: {self._memory_threshold_mb}MB)"
            )
            await self._perform_emergency_cleanup()
        
        # Check if too many objects in GC
        if snapshot.gc_objects > self._gc_threshold_objects:
            logger.info(
                f"High object count detected: {snapshot.gc_objects} objects, "
                "triggering garbage collection"
            )
            await self._force_gc()
    
    async def _perform_cleanup(self) -> None:
        """Perform routine memory cleanup."""
        # Clean up weak registries
        for registry in self._weak_registries.values():
            registry.get_count()  # This cleans up dead references
        
        # Update object trackers
        self._update_object_trackers()
        
        # Gentle garbage collection
        collected = gc.collect()
        if collected > 0:
            logger.debug(f"Routine cleanup collected {collected} objects")
    
    async def _perform_emergency_cleanup(self) -> None:
        """Perform emergency memory cleanup."""
        logger.warning("Performing emergency memory cleanup")
        
        # Force garbage collection multiple times
        total_collected = 0
        for _ in range(3):
            collected = gc.collect()
            total_collected += collected
            if collected == 0:
                break
        
        # Clear internal caches
        self._clear_internal_caches()
        
        # Take new snapshot to see improvement
        new_snapshot = self._take_snapshot()
        logger.info(
            f"Emergency cleanup completed: collected {total_collected} objects, "
            f"memory usage: {new_snapshot.rss_mb:.1f}MB"
        )
    
    async def _force_gc(self) -> None:
        """Force garbage collection."""
        collected = gc.collect()
        logger.debug(f"Forced GC collected {collected} objects")
    
    def _clear_internal_caches(self) -> None:
        """Clear internal caches to free memory."""
        # Keep only recent snapshots
        if len(self._snapshots) > 10:
            self._snapshots = self._snapshots[-10:]
        
        # Reset object trackers
        for tracker in self._object_trackers.values():
            if tracker.last_updated and (
                datetime.now() - tracker.last_updated
            ).total_seconds() > 3600:  # 1 hour old
                tracker.created_count = 0
                tracker.destroyed_count = 0
    
    def _update_object_trackers(self) -> None:
        """Update object tracker statistics."""
        for name, registry in self._weak_registries.items():
            if name in self._object_trackers:
                tracker = self._object_trackers[name]
                current_count = registry.get_count()
                tracker.current_count = current_count
                tracker.peak_count = max(tracker.peak_count, current_count)
                tracker.last_updated = datetime.now()
    
    def register_object_type(self, name: str) -> WeakObjectRegistry[Any]:
        """Register a new object type for tracking."""
        if name not in self._weak_registries:
            self._weak_registries[name] = WeakObjectRegistry[Any](name)
            self._object_trackers[name] = ObjectTracker(
                object_type=name,
                last_updated=datetime.now()
            )
        return self._weak_registries[name]
    
    def track_object_creation(self, object_type: str) -> None:
        """Track object creation."""
        tracker = self._object_trackers[object_type]
        tracker.created_count += 1
        tracker.current_count += 1
        tracker.peak_count = max(tracker.peak_count, tracker.current_count)
        tracker.last_updated = datetime.now()
    
    def track_object_destruction(self, object_type: str) -> None:
        """Track object destruction."""
        tracker = self._object_trackers[object_type]
        tracker.destroyed_count += 1
        tracker.current_count = max(0, tracker.current_count - 1)
        tracker.last_updated = datetime.now()
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        current_snapshot = self._take_snapshot()
        
        # Calculate trends if we have enough data
        trends = {}
        if len(self._snapshots) >= 2:
            prev_snapshot = self._snapshots[-1]
            trends = {
                'rss_mb_change': current_snapshot.rss_mb - prev_snapshot.rss_mb,
                'objects_change': current_snapshot.gc_objects - prev_snapshot.gc_objects,
                'time_delta_minutes': (
                    current_snapshot.timestamp - prev_snapshot.timestamp
                ).total_seconds() / 60
            }
        
        return {
            'current_snapshot': current_snapshot.__dict__,
            'trends': trends,
            'object_trackers': {
                name: tracker.__dict__ 
                for name, tracker in self._object_trackers.items()
            },
            'gc_stats': {
                'counts': gc.get_count(),
                'thresholds': gc.get_threshold(),
                'stats': gc.get_stats() if hasattr(gc, 'get_stats') else None
            },
            'registry_counts': {
                name: registry.get_count()
                for name, registry in self._weak_registries.items()
            }
        }
    
    def get_memory_report(self) -> str:
        """Get human-readable memory report."""
        stats = self.get_memory_stats()
        current = stats['current_snapshot']
        
        report_lines = [
            "=== Memory Report ===",
            f"Timestamp: {current['timestamp']}",
            f"RSS Memory: {current['rss_mb']:.1f} MB",
            f"VMS Memory: {current['vms_mb']:.1f} MB",
            f"Memory %: {current['percent']:.1f}%",
            f"Available: {current['available_mb']:.1f} MB",
            f"GC Objects: {current['gc_objects']:,}",
            "",
            "=== Object Trackers ===",
        ]
        
        for name, tracker in stats['object_trackers'].items():
            report_lines.append(
                f"{name}: {tracker['current_count']} current, "
                f"{tracker['peak_count']} peak, "
                f"{tracker['created_count']} created, "
                f"{tracker['destroyed_count']} destroyed"
            )
        
        if stats['trends']:
            trends = stats['trends']
            report_lines.extend([
                "",
                "=== Trends ===",
                f"Memory change: {trends['rss_mb_change']:+.1f} MB",
                f"Objects change: {trends['objects_change']:+,}",
                f"Time period: {trends['time_delta_minutes']:.1f} minutes"
            ])
        
        return "\n".join(report_lines)


# Decorators for memory optimization
def track_memory(object_type: str) -> Any:
    """Decorator to track memory usage of objects."""
    def decorator(cls: Any) -> Any:
        original_init = cls.__init__
        original_del = getattr(cls, '__del__', None)
        
        optimizer = MemoryOptimizer()
        registry = optimizer.register_object_type(object_type)
        
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            optimizer.track_object_creation(object_type)
            registry.register(self)
        
        def new_del(self: Any) -> None:
            optimizer.track_object_destruction(object_type)
            if original_del:
                original_del(self)
        
        cls.__init__ = new_init
        cls.__del__ = new_del
        
        return cls
    return decorator


def memory_efficient(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to make functions more memory efficient."""
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        # Take snapshot before
        optimizer = MemoryOptimizer()
        before_snapshot = optimizer._take_snapshot()
        
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            # Take snapshot after and check for memory leaks
            after_snapshot = optimizer._take_snapshot()
            memory_delta = after_snapshot.rss_mb - before_snapshot.rss_mb
            
            # If memory increased significantly, log it
            if memory_delta > 10:  # 10MB threshold
                logger.warning(
                    f"Function {func.__name__} used {memory_delta:.1f}MB memory"
                )
            
            # Force GC if memory usage is high
            if after_snapshot.rss_mb > optimizer._memory_threshold_mb:
                await optimizer._force_gc()
    
    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        # For synchronous functions, just run GC after if needed
        result = func(*args, **kwargs)
        
        optimizer = MemoryOptimizer()
        snapshot = optimizer._take_snapshot()
        
        if snapshot.rss_mb > optimizer._memory_threshold_mb:
            gc.collect()
        
        return result
    
    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# Global memory optimizer instance
memory_optimizer = MemoryOptimizer()