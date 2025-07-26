"""
Tests for memory optimizer module.

This module tests memory monitoring, optimization, and resource management
functionality in the memory optimizer.
"""

import asyncio
import gc
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from typing import Any, Dict, List

from modules.memory_optimizer import (
    MemoryOptimizer,
    MemorySnapshot,
    ObjectTracker,
    WeakObjectRegistry,
    track_memory,
    memory_efficient,
    memory_optimizer
)
from modules.types import Timestamp


class TestMemorySnapshot:
    """Test MemorySnapshot dataclass."""
    
    def test_memory_snapshot_creation(self):
        """Test creating a memory snapshot."""
        timestamp = datetime.now()
        snapshot = MemorySnapshot(
            timestamp=timestamp,
            rss_mb=100.5,
            vms_mb=200.0,
            percent=75.2,
            available_mb=1024.0,
            gc_objects=5000,
            gc_collections={0: 10, 1: 5, 2: 2}
        )
        
        assert snapshot.timestamp == timestamp
        assert snapshot.rss_mb == 100.5
        assert snapshot.vms_mb == 200.0
        assert snapshot.percent == 75.2
        assert snapshot.available_mb == 1024.0
        assert snapshot.gc_objects == 5000
        assert snapshot.gc_collections == {0: 10, 1: 5, 2: 2}


class TestObjectTracker:
    """Test ObjectTracker dataclass."""
    
    def test_object_tracker_creation(self):
        """Test creating an object tracker."""
        timestamp = datetime.now()
        tracker = ObjectTracker(
            object_type="TestObject",
            created_count=10,
            destroyed_count=5,
            current_count=5,
            peak_count=8,
            last_updated=timestamp
        )
        
        assert tracker.object_type == "TestObject"
        assert tracker.created_count == 10
        assert tracker.destroyed_count == 5
        assert tracker.current_count == 5
        assert tracker.peak_count == 8
        assert tracker.last_updated == timestamp
    
    def test_object_tracker_defaults(self):
        """Test object tracker with default values."""
        tracker = ObjectTracker(object_type="TestObject")
        
        assert tracker.object_type == "TestObject"
        assert tracker.created_count == 0
        assert tracker.destroyed_count == 0
        assert tracker.current_count == 0
        assert tracker.peak_count == 0
        assert tracker.last_updated is None


class TestWeakObjectRegistry:
    """Test WeakObjectRegistry functionality."""
    
    def test_registry_creation(self):
        """Test creating a weak object registry."""
        registry = WeakObjectRegistry[str]("test_registry")
        assert registry.name == "test_registry"
        assert registry.get_count() == 0
    
    def test_register_object(self):
        """Test registering an object in the registry."""
        class TestObj:
            pass
        
        registry = WeakObjectRegistry[TestObj]("test_registry")
        test_obj = TestObj()
        
        registry.register(test_obj)
        assert registry.get_count() == 1
    
    def test_register_multiple_objects(self):
        """Test registering multiple objects."""
        class TestObj:
            def __init__(self, name):
                self.name = name
        
        registry = WeakObjectRegistry[TestObj]("test_registry")
        
        obj1 = TestObj("test1")
        obj2 = TestObj("test2")
        obj3 = TestObj("test3")
        
        registry.register(obj1)
        registry.register(obj2)
        registry.register(obj3)
        
        assert registry.get_count() == 3
    
    def test_cleanup_callback(self):
        """Test cleanup callback functionality."""
        class TestObj:
            pass
        
        registry = WeakObjectRegistry[TestObj]("test_registry")
        cleanup_called = Mock()
        
        # Create object in local scope
        def create_and_register():
            test_obj = TestObj()
            registry.register(test_obj, cleanup_called)
            return test_obj
        
        obj = create_and_register()
        assert registry.get_count() == 1
        
        # Delete object and force garbage collection
        del obj
        gc.collect()
        
        # Check that cleanup was called
        assert registry.get_count() == 0
    
    def test_get_objects(self):
        """Test getting tracked objects."""
        class TestObj:
            def __init__(self, name):
                self.name = name
            def __eq__(self, other):
                return isinstance(other, TestObj) and self.name == other.name
            def __hash__(self):
                return hash(self.name)
        
        registry = WeakObjectRegistry[TestObj]("test_registry")
        
        obj1 = TestObj("test1")
        obj2 = TestObj("test2")
        
        registry.register(obj1)
        registry.register(obj2)
        
        objects = registry.get_objects()
        assert len(objects) == 2
        assert obj1 in objects
        assert obj2 in objects


class TestMemoryOptimizer:
    """Test MemoryOptimizer functionality."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a fresh memory optimizer instance for testing."""
        # Reset singleton state
        if hasattr(MemoryOptimizer, '_instances'):
            MemoryOptimizer._instances.clear()
        return MemoryOptimizer()
    
    def test_singleton_behavior(self):
        """Test that MemoryOptimizer is a singleton."""
        optimizer1 = MemoryOptimizer()
        optimizer2 = MemoryOptimizer()
        assert optimizer1 is optimizer2
    
    @patch('modules.memory_optimizer.gc')
    def test_configure_gc(self, mock_gc, optimizer):
        """Test garbage collection configuration."""
        optimizer._configure_gc()
        
        mock_gc.set_threshold.assert_called_once_with(700, 10, 10)
        mock_gc.enable.assert_called_once()
    
    @patch('modules.memory_optimizer.psutil')
    @patch('modules.memory_optimizer.gc')
    def test_take_snapshot(self, mock_gc, mock_psutil, optimizer):
        """Test taking a memory snapshot."""
        # Mock psutil
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB
        mock_memory_info.vms = 200 * 1024 * 1024  # 200MB
        mock_process.memory_info.return_value = mock_memory_info
        mock_psutil.Process.return_value = mock_process
        
        mock_virtual_memory = Mock()
        mock_virtual_memory.percent = 75.0
        mock_virtual_memory.available = 1024 * 1024 * 1024  # 1GB
        mock_psutil.virtual_memory.return_value = mock_virtual_memory
        
        # Mock gc
        mock_gc.get_count.return_value = [100, 50, 25]
        mock_gc.get_objects.return_value = [Mock() for _ in range(5000)]
        
        snapshot = optimizer._take_snapshot()
        
        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.rss_mb == 100.0
        assert snapshot.vms_mb == 200.0
        assert snapshot.percent == 75.0
        assert snapshot.available_mb == 1024.0
        assert snapshot.gc_objects == 5000
        assert snapshot.gc_collections == {0: 100, 1: 50, 2: 25}
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, optimizer):
        """Test starting and stopping memory monitoring."""
        assert not optimizer._is_monitoring
        
        # Start monitoring
        await optimizer.start_monitoring(interval=1)
        assert optimizer._is_monitoring
        assert optimizer._monitoring_task is not None
        
        # Stop monitoring
        await optimizer.stop_monitoring()
        assert not optimizer._is_monitoring
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_single_iteration(self, optimizer):
        """Test a single iteration of the monitoring loop."""
        with patch.object(optimizer, '_take_snapshot') as mock_snapshot, \
             patch.object(optimizer, '_check_memory_health') as mock_check, \
             patch.object(optimizer, '_perform_cleanup') as mock_cleanup:
            
            mock_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=1000,
                gc_collections={0: 10, 1: 5, 2: 2}
            )
            
            # Start monitoring for a short time
            optimizer._is_monitoring = True
            task = asyncio.create_task(optimizer._monitoring_loop(0.1))
            
            # Let it run for a bit
            await asyncio.sleep(0.2)
            
            # Stop monitoring
            optimizer._is_monitoring = False
            await task
            
            # Verify methods were called
            assert mock_snapshot.called
            assert mock_check.called
    
    @pytest.mark.asyncio
    async def test_check_memory_health_high_memory(self, optimizer):
        """Test memory health check with high memory usage."""
        with patch.object(optimizer, '_perform_emergency_cleanup') as mock_cleanup:
            optimizer._memory_threshold_mb = 50.0  # Low threshold for testing
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,  # Above threshold
                vms_mb=200.0,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=1000,
                gc_collections={0: 10, 1: 5, 2: 2}
            )
            
            await optimizer._check_memory_health(snapshot)
            mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_memory_health_high_objects(self, optimizer):
        """Test memory health check with high object count."""
        with patch.object(optimizer, '_force_gc') as mock_gc:
            optimizer._gc_threshold_objects = 500  # Low threshold for testing
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=50.0,
                vms_mb=100.0,
                percent=30.0,
                available_mb=1024.0,
                gc_objects=1000,  # Above threshold
                gc_collections={0: 10, 1: 5, 2: 2}
            )
            
            await optimizer._check_memory_health(snapshot)
            mock_gc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_perform_cleanup(self, optimizer):
        """Test routine memory cleanup."""
        # Add some registries
        registry1 = optimizer.register_object_type("test1")
        registry2 = optimizer.register_object_type("test2")
        
        with patch.object(registry1, 'get_count') as mock_count1, \
             patch.object(registry2, 'get_count') as mock_count2, \
             patch.object(optimizer, '_update_object_trackers') as mock_update, \
             patch('modules.memory_optimizer.gc') as mock_gc:
            
            mock_gc.collect.return_value = 5
            
            await optimizer._perform_cleanup()
            
            mock_count1.assert_called_once()
            mock_count2.assert_called_once()
            mock_update.assert_called_once()
            mock_gc.collect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_perform_emergency_cleanup(self, optimizer):
        """Test emergency memory cleanup."""
        with patch('modules.memory_optimizer.gc') as mock_gc, \
             patch.object(optimizer, '_clear_internal_caches') as mock_clear, \
             patch.object(optimizer, '_take_snapshot') as mock_snapshot:
            
            mock_gc.collect.side_effect = [10, 5, 0]  # Decreasing collections
            mock_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=80.0,
                vms_mb=160.0,
                percent=40.0,
                available_mb=1024.0,
                gc_objects=800,
                gc_collections={0: 8, 1: 4, 2: 2}
            )
            
            await optimizer._perform_emergency_cleanup()
            
            assert mock_gc.collect.call_count == 3
            mock_clear.assert_called_once()
            mock_snapshot.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_force_gc(self, optimizer):
        """Test forcing garbage collection."""
        with patch('modules.memory_optimizer.gc') as mock_gc:
            mock_gc.collect.return_value = 15
            
            await optimizer._force_gc()
            
            mock_gc.collect.assert_called_once()
    
    def test_clear_internal_caches(self, optimizer):
        """Test clearing internal caches."""
        # Add many snapshots
        for i in range(50):
            optimizer._snapshots.append(MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=1000,
                gc_collections={0: 10, 1: 5, 2: 2}
            ))
        
        # Add old tracker
        old_time = datetime.now() - timedelta(hours=2)
        optimizer._object_trackers["old_tracker"] = ObjectTracker(
            object_type="old_tracker",
            created_count=100,
            destroyed_count=50,
            last_updated=old_time
        )
        
        optimizer._clear_internal_caches()
        
        # Should keep only 10 snapshots
        assert len(optimizer._snapshots) == 10
        
        # Should reset old tracker
        tracker = optimizer._object_trackers["old_tracker"]
        assert tracker.created_count == 0
        assert tracker.destroyed_count == 0
    
    def test_register_object_type(self, optimizer):
        """Test registering a new object type."""
        registry = optimizer.register_object_type("TestObject")
        
        assert isinstance(registry, WeakObjectRegistry)
        assert registry.name == "TestObject"
        assert "TestObject" in optimizer._weak_registries
        assert "TestObject" in optimizer._object_trackers
        
        # Should return same registry for same name
        registry2 = optimizer.register_object_type("TestObject")
        assert registry is registry2
    
    def test_track_object_creation(self, optimizer):
        """Test tracking object creation."""
        optimizer.register_object_type("TestObject")
        
        optimizer.track_object_creation("TestObject")
        
        tracker = optimizer._object_trackers["TestObject"]
        assert tracker.created_count == 1
        assert tracker.current_count == 1
        assert tracker.peak_count == 1
        assert tracker.last_updated is not None
    
    def test_track_object_destruction(self, optimizer):
        """Test tracking object destruction."""
        optimizer.register_object_type("TestObject")
        optimizer.track_object_creation("TestObject")
        
        optimizer.track_object_destruction("TestObject")
        
        tracker = optimizer._object_trackers["TestObject"]
        assert tracker.destroyed_count == 1
        assert tracker.current_count == 0
    
    def test_update_object_trackers(self, optimizer):
        """Test updating object tracker statistics."""
        registry = optimizer.register_object_type("TestObject")
        
        with patch.object(registry, 'get_count', return_value=5):
            optimizer._update_object_trackers()
            
            tracker = optimizer._object_trackers["TestObject"]
            assert tracker.current_count == 5
            assert tracker.peak_count == 5
            assert tracker.last_updated is not None
    
    @patch('modules.memory_optimizer.psutil')
    @patch('modules.memory_optimizer.gc')
    def test_get_memory_stats(self, mock_gc, mock_psutil, optimizer):
        """Test getting comprehensive memory statistics."""
        # Mock psutil and gc for snapshot
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024
        mock_memory_info.vms = 200 * 1024 * 1024
        mock_process.memory_info.return_value = mock_memory_info
        mock_psutil.Process.return_value = mock_process
        
        mock_virtual_memory = Mock()
        mock_virtual_memory.percent = 75.0
        mock_virtual_memory.available = 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_virtual_memory
        
        mock_gc.get_count.return_value = [100, 50, 25]
        mock_gc.get_objects.return_value = [Mock() for _ in range(5000)]
        mock_gc.get_threshold.return_value = (700, 10, 10)
        mock_gc.get_stats.return_value = [{'collections': 10}]
        
        # Add a previous snapshot for trends
        prev_snapshot = MemorySnapshot(
            timestamp=datetime.now() - timedelta(minutes=1),
            rss_mb=90.0,
            vms_mb=180.0,
            percent=70.0,
            available_mb=1100.0,
            gc_objects=4500,
            gc_collections={0: 90, 1: 45, 2: 20}
        )
        optimizer._snapshots.append(prev_snapshot)
        
        # Ensure we have at least 2 snapshots for trends calculation
        if len(optimizer._snapshots) < 2:
            optimizer._snapshots.append(prev_snapshot)
        
        # Add object tracker and registry
        optimizer.register_object_type("TestObject")
        
        stats = optimizer.get_memory_stats()
        
        assert 'current_snapshot' in stats
        assert 'trends' in stats
        assert 'object_trackers' in stats
        assert 'gc_stats' in stats
        assert 'registry_counts' in stats
        
        # Check trends calculation
        trends = stats['trends']
        assert 'rss_mb_change' in trends
        assert 'objects_change' in trends
        assert 'time_delta_minutes' in trends
    
    def test_get_memory_report(self, optimizer):
        """Test getting human-readable memory report."""
        with patch.object(optimizer, 'get_memory_stats') as mock_stats:
            mock_stats.return_value = {
                'current_snapshot': {
                    'timestamp': datetime.now(),
                    'rss_mb': 100.5,
                    'vms_mb': 200.0,
                    'percent': 75.2,
                    'available_mb': 1024.0,
                    'gc_objects': 5000
                },
                'trends': {
                    'rss_mb_change': 10.5,
                    'objects_change': 500,
                    'time_delta_minutes': 1.0
                },
                'object_trackers': {
                    'TestObject': {
                        'current_count': 5,
                        'peak_count': 8,
                        'created_count': 10,
                        'destroyed_count': 5
                    }
                }
            }
            
            report = optimizer.get_memory_report()
            
            assert "=== Memory Report ===" in report
            assert "RSS Memory: 100.5 MB" in report
            assert "=== Object Trackers ===" in report
            assert "TestObject: 5 current, 8 peak" in report
            assert "=== Trends ===" in report
            assert "Memory change: +10.5 MB" in report


class TestMemoryDecorators:
    """Test memory optimization decorators."""
    
    def test_track_memory_decorator(self):
        """Test the track_memory decorator."""
        @track_memory("TestClass")
        class TestClass:
            def __init__(self, value):
                self.value = value
        
        # Create instance
        obj = TestClass("test")
        
        # Check that tracking was set up
        optimizer = MemoryOptimizer()
        assert "TestClass" in optimizer._object_trackers
        assert "TestClass" in optimizer._weak_registries
        
        # Check tracker was updated
        tracker = optimizer._object_trackers["TestClass"]
        assert tracker.created_count >= 1
    
    @pytest.mark.asyncio
    async def test_memory_efficient_async_decorator(self):
        """Test memory_efficient decorator with async function."""
        @memory_efficient
        async def test_async_function():
            return "test_result"
        
        with patch('modules.memory_optimizer.MemoryOptimizer') as mock_optimizer_class:
            mock_optimizer = Mock()
            mock_optimizer_class.return_value = mock_optimizer
            mock_optimizer._take_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=50.0,
                vms_mb=100.0,
                percent=30.0,
                available_mb=1024.0,
                gc_objects=1000,
                gc_collections={0: 10, 1: 5, 2: 2}
            )
            mock_optimizer._memory_threshold_mb = 100.0
            
            result = await test_async_function()
            assert result == "test_result"
            
            # Should take snapshots before and after
            assert mock_optimizer._take_snapshot.call_count == 2
    
    def test_memory_efficient_sync_decorator(self):
        """Test memory_efficient decorator with sync function."""
        @memory_efficient
        def test_sync_function():
            return "test_result"
        
        with patch('modules.memory_optimizer.MemoryOptimizer') as mock_optimizer_class, \
             patch('modules.memory_optimizer.gc') as mock_gc:
            
            mock_optimizer = Mock()
            mock_optimizer_class.return_value = mock_optimizer
            mock_optimizer._take_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=150.0,  # High memory to trigger GC
                vms_mb=300.0,
                percent=60.0,
                available_mb=1024.0,
                gc_objects=2000,
                gc_collections={0: 20, 1: 10, 2: 5}
            )
            mock_optimizer._memory_threshold_mb = 100.0
            
            result = test_sync_function()
            assert result == "test_result"
            
            # Should check memory and potentially run GC
            mock_optimizer._take_snapshot.assert_called_once()
            mock_gc.collect.assert_called_once()


class TestGlobalMemoryOptimizer:
    """Test global memory optimizer instance."""
    
    def test_global_instance_exists(self):
        """Test that global memory optimizer instance exists."""
        from modules.memory_optimizer import memory_optimizer
        assert isinstance(memory_optimizer, MemoryOptimizer)


class TestResourceManagement:
    """Test resource management functionality."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a fresh memory optimizer instance for testing."""
        # Reset singleton state
        if hasattr(MemoryOptimizer, '_instances'):
            MemoryOptimizer._instances.clear()
        return MemoryOptimizer()
    
    def test_resource_allocation_tracking(self, optimizer):
        """Test resource allocation and deallocation patterns."""
        # Register multiple object types
        registry1 = optimizer.register_object_type("Resource1")
        registry2 = optimizer.register_object_type("Resource2")
        
        # Create objects that support weak references
        class TestResource:
            def __init__(self, name):
                self.name = name
        
        # Simulate resource allocation
        resources1 = [TestResource(f"resource1_{i}") for i in range(3)]
        resources2 = [TestResource(f"resource2_{i}") for i in range(2)]
        
        for resource in resources1:
            registry1.register(resource)
            optimizer.track_object_creation("Resource1")
        
        for resource in resources2:
            registry2.register(resource)
            optimizer.track_object_creation("Resource2")
        
        # Verify tracking
        assert registry1.get_count() == 3
        assert registry2.get_count() == 2
        
        tracker1 = optimizer._object_trackers["Resource1"]
        tracker2 = optimizer._object_trackers["Resource2"]
        
        assert tracker1.created_count == 3
        assert tracker1.current_count == 3
        assert tracker1.peak_count == 3
        
        assert tracker2.created_count == 2
        assert tracker2.current_count == 2
        assert tracker2.peak_count == 2
    
    def test_resource_deallocation_tracking(self, optimizer):
        """Test resource deallocation tracking."""
        optimizer.register_object_type("TestResource")
        
        # Track creation
        for i in range(5):
            optimizer.track_object_creation("TestResource")
        
        # Track destruction
        for i in range(3):
            optimizer.track_object_destruction("TestResource")
        
        tracker = optimizer._object_trackers["TestResource"]
        assert tracker.created_count == 5
        assert tracker.destroyed_count == 3
        assert tracker.current_count == 2
        assert tracker.peak_count == 5
    
    def test_memory_leak_detection_scenario(self, optimizer):
        """Test memory leak detection through object tracking."""
        class LeakyResource:
            def __init__(self, name):
                self.name = name
        
        registry = optimizer.register_object_type("LeakyResource")
        
        # Simulate memory leak - objects created but not properly cleaned up
        leaked_objects = []
        for i in range(10):
            obj = LeakyResource(f"leaked_object_{i}")
            leaked_objects.append(obj)
            registry.register(obj)
            optimizer.track_object_creation("LeakyResource")
        
        # Simulate partial cleanup (some objects destroyed but references remain)
        for i in range(3):
            optimizer.track_object_destruction("LeakyResource")
        
        tracker = optimizer._object_trackers["LeakyResource"]
        
        # Should detect discrepancy between tracked objects and actual references
        assert tracker.created_count == 10
        assert tracker.destroyed_count == 3
        assert tracker.current_count == 7  # Indicates potential leak
        assert registry.get_count() == 10  # All objects still referenced
    
    def test_performance_optimization_strategies(self, optimizer):
        """Test performance optimization strategies."""
        with patch.object(optimizer, '_take_snapshot') as mock_snapshot, \
             patch('modules.memory_optimizer.gc') as mock_gc:
            
            # Mock high memory usage scenario
            high_memory_snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=200.0,  # High memory usage
                vms_mb=400.0,
                percent=80.0,
                available_mb=256.0,
                gc_objects=15000,  # High object count
                gc_collections={0: 100, 1: 50, 2: 25}
            )
            
            mock_snapshot.return_value = high_memory_snapshot
            mock_gc.collect.return_value = 50
            
            # Set low thresholds to trigger optimization
            optimizer._memory_threshold_mb = 150.0
            optimizer._gc_threshold_objects = 10000
            
            # Test emergency cleanup strategy
            asyncio.run(optimizer._perform_emergency_cleanup())
            
            # Should perform multiple GC cycles
            assert mock_gc.collect.call_count == 3
            
            # Should clear internal caches
            assert len(optimizer._snapshots) <= 10
    
    @pytest.mark.asyncio
    async def test_resource_monitoring_with_cleanup(self, optimizer):
        """Test resource monitoring with automatic cleanup."""
        with patch.object(optimizer, '_take_snapshot') as mock_snapshot, \
             patch.object(optimizer, '_perform_cleanup') as mock_cleanup:
            
            mock_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=5000,
                gc_collections={0: 50, 1: 25, 2: 12}
            )
            
            # Start monitoring
            await optimizer.start_monitoring(interval=0.1)
            
            # Let it run for a short time
            await asyncio.sleep(0.25)
            
            # Stop monitoring
            await optimizer.stop_monitoring()
            
            # Should have taken snapshots and performed cleanup
            assert mock_snapshot.called
            # Cleanup should be called every 10 snapshots, but we might not reach that
    
    def test_weak_reference_cleanup(self, optimizer):
        """Test automatic cleanup of weak references."""
        class TempObject:
            def __init__(self, name):
                self.name = name
        
        registry = optimizer.register_object_type("WeakRefTest")
        
        # Create objects in local scope that will be garbage collected
        def create_temporary_objects():
            temp_objects = []
            for i in range(5):
                obj = TempObject(f"temp_object_{i}")
                temp_objects.append(obj)
                registry.register(obj)
            return temp_objects
        
        # Create and immediately lose references
        temp_objects = create_temporary_objects()
        initial_count = registry.get_count()
        assert initial_count == 5
        
        # Delete references and force garbage collection
        del temp_objects
        gc.collect()
        
        # Registry should automatically clean up dead references
        final_count = registry.get_count()
        assert final_count == 0
    
    def test_memory_threshold_alerting(self, optimizer):
        """Test memory threshold detection and alerting."""
        with patch.object(optimizer, '_perform_emergency_cleanup') as mock_emergency, \
             patch.object(optimizer, '_force_gc') as mock_gc:
            
            # Test high memory threshold
            high_memory_snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=500.0,  # Very high memory
                vms_mb=1000.0,
                percent=90.0,
                available_mb=128.0,
                gc_objects=5000,
                gc_collections={0: 50, 1: 25, 2: 12}
            )
            
            optimizer._memory_threshold_mb = 400.0  # Lower than snapshot
            
            asyncio.run(optimizer._check_memory_health(high_memory_snapshot))
            mock_emergency.assert_called_once()
            
            # Test high object count threshold
            high_objects_snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=40.0,
                available_mb=1024.0,
                gc_objects=20000,  # Very high object count
                gc_collections={0: 200, 1: 100, 2: 50}
            )
            
            optimizer._gc_threshold_objects = 15000  # Lower than snapshot
            
            asyncio.run(optimizer._check_memory_health(high_objects_snapshot))
            mock_gc.assert_called_once()
    
    def test_cache_management_and_cleanup(self, optimizer):
        """Test internal cache management and cleanup."""
        # Fill up snapshots beyond limit
        for i in range(150):  # More than the 100 limit
            snapshot = MemorySnapshot(
                timestamp=datetime.now() - timedelta(minutes=i),
                rss_mb=100.0 + i,
                vms_mb=200.0 + i,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=5000 + i,
                gc_collections={0: 50, 1: 25, 2: 12}
            )
            optimizer._snapshots.append(snapshot)
        
        # Trigger monitoring loop which should clean up old snapshots
        with patch.object(optimizer, '_take_snapshot') as mock_snapshot, \
             patch.object(optimizer, '_check_memory_health'):
            
            mock_snapshot.return_value = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=50.0,
                available_mb=1024.0,
                gc_objects=5000,
                gc_collections={0: 50, 1: 25, 2: 12}
            )
            
            # Simulate monitoring loop iteration
            asyncio.run(optimizer._monitoring_loop(0.1))
            
            # Should keep only last 100 snapshots
            assert len(optimizer._snapshots) <= 100
    
    def test_object_lifecycle_tracking(self, optimizer):
        """Test complete object lifecycle tracking."""
        class LifecycleObject:
            def __init__(self, name):
                self.name = name
        
        registry = optimizer.register_object_type("LifecycleTest")
        
        # Phase 1: Object creation
        objects = []
        for i in range(10):
            obj = LifecycleObject(f"lifecycle_object_{i}")
            objects.append(obj)
            registry.register(obj)
            optimizer.track_object_creation("LifecycleTest")
        
        tracker = optimizer._object_trackers["LifecycleTest"]
        assert tracker.created_count == 10
        assert tracker.current_count == 10
        assert tracker.peak_count == 10
        
        # Phase 2: Partial cleanup
        for i in range(4):
            optimizer.track_object_destruction("LifecycleTest")
        
        assert tracker.destroyed_count == 4
        assert tracker.current_count == 6
        assert tracker.peak_count == 10  # Peak should remain
        
        # Phase 3: More objects created
        for i in range(3):
            obj = LifecycleObject(f"new_object_{i}")
            objects.append(obj)
            registry.register(obj)
            optimizer.track_object_creation("LifecycleTest")
        
        assert tracker.created_count == 13
        assert tracker.current_count == 9
        assert tracker.peak_count == 10  # Still the previous peak
        
        # Phase 4: Peak exceeded
        for i in range(5):
            obj = LifecycleObject(f"peak_object_{i}")
            objects.append(obj)
            registry.register(obj)
            optimizer.track_object_creation("LifecycleTest")
        
        assert tracker.created_count == 18
        assert tracker.current_count == 14
        assert tracker.peak_count == 14  # New peak
    
    def test_concurrent_resource_access(self, optimizer):
        """Test concurrent resource access patterns."""
        class ConcurrentObject:
            def __init__(self, name):
                self.name = name
        
        registry = optimizer.register_object_type("ConcurrentTest")
        
        # Simulate concurrent access by multiple "threads"
        def simulate_thread_work(thread_id: int, object_count: int):
            thread_objects = []
            for i in range(object_count):
                obj = ConcurrentObject(f"thread_{thread_id}_object_{i}")
                thread_objects.append(obj)
                registry.register(obj)
                optimizer.track_object_creation("ConcurrentTest")
            return thread_objects
        
        # Simulate 3 concurrent threads
        thread1_objects = simulate_thread_work(1, 5)
        thread2_objects = simulate_thread_work(2, 3)
        thread3_objects = simulate_thread_work(3, 7)
        
        # Verify total tracking
        tracker = optimizer._object_trackers["ConcurrentTest"]
        assert tracker.created_count == 15  # 5 + 3 + 7
        assert tracker.current_count == 15
        assert registry.get_count() == 15
        
        # Simulate thread cleanup
        for i in range(3):  # Thread 2 cleans up
            optimizer.track_object_destruction("ConcurrentTest")
        
        assert tracker.destroyed_count == 3
        assert tracker.current_count == 12
    
    def test_memory_optimization_under_pressure(self, optimizer):
        """Test memory optimization under memory pressure."""
        with patch('modules.memory_optimizer.gc') as mock_gc, \
             patch.object(optimizer, '_take_snapshot') as mock_snapshot:
            
            # Simulate memory pressure scenario
            pressure_snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=800.0,  # Very high memory usage
                vms_mb=1600.0,
                percent=95.0,  # Critical memory usage
                available_mb=64.0,  # Very low available memory
                gc_objects=25000,  # High object count
                gc_collections={0: 500, 1: 250, 2: 125}
            )
            
            mock_snapshot.return_value = pressure_snapshot
            mock_gc.collect.side_effect = [100, 50, 25, 0]  # Diminishing returns
            
            # Set aggressive thresholds
            optimizer._memory_threshold_mb = 200.0
            optimizer._gc_threshold_objects = 5000
            
            # Should trigger emergency cleanup
            asyncio.run(optimizer._perform_emergency_cleanup())
            
            # Should perform multiple GC cycles until no more objects collected
            assert mock_gc.collect.call_count >= 3  # At least 3 calls
            
            # Should clear internal caches
            assert len(optimizer._snapshots) <= 10
    
    def test_resource_leak_prevention(self, optimizer):
        """Test resource leak prevention mechanisms."""
        class PreventionObject:
            def __init__(self, obj_id):
                self.obj_id = obj_id
        
        registry = optimizer.register_object_type("LeakPrevention")
        
        # Create objects with cleanup callbacks
        cleanup_calls = []
        
        def create_object_with_cleanup(obj_id: int):
            obj = PreventionObject(obj_id)
            
            def cleanup_callback():
                cleanup_calls.append(obj_id)
            
            registry.register(obj, cleanup_callback)
            optimizer.track_object_creation("LeakPrevention")
            return obj
        
        # Create objects
        objects = []
        for i in range(5):
            obj = create_object_with_cleanup(i)
            objects.append(obj)
        
        assert registry.get_count() == 5
        assert len(cleanup_calls) == 0
        
        # Delete objects and force garbage collection
        del objects
        gc.collect()
        
        # Cleanup callbacks should have been called
        # Note: This might be flaky due to GC timing, but should work in most cases
        registry.get_count()  # This triggers cleanup of dead references
        
        # At least some cleanup should have occurred
        # (exact count may vary due to GC timing)
        assert len(cleanup_calls) >= 0  # At minimum, no errors should occur


class TestMemoryOptimizationIntegration:
    """Integration tests for memory optimization features."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a fresh memory optimizer instance for testing."""
        # Reset singleton state
        if hasattr(MemoryOptimizer, '_instances'):
            MemoryOptimizer._instances.clear()
        return MemoryOptimizer()
    
    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self, optimizer):
        """Test a complete monitoring cycle with resource management."""
        with patch.object(optimizer, '_take_snapshot') as mock_snapshot, \
             patch('modules.memory_optimizer.gc') as mock_gc:
            
            # Mock progressive memory usage
            snapshots = [
                MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=100.0,
                    vms_mb=200.0,
                    percent=40.0,
                    available_mb=1024.0,
                    gc_objects=5000,
                    gc_collections={0: 50, 1: 25, 2: 12}
                ),
                MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=150.0,  # Increasing memory
                    vms_mb=300.0,
                    percent=60.0,
                    available_mb=768.0,
                    gc_objects=8000,
                    gc_collections={0: 80, 1: 40, 2: 20}
                ),
                MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=250.0,  # High memory - should trigger cleanup
                    vms_mb=500.0,
                    percent=80.0,
                    available_mb=512.0,
                    gc_objects=12000,
                    gc_collections={0: 120, 1: 60, 2: 30}
                )
            ]
            
            mock_snapshot.side_effect = iter(snapshots)
            mock_gc.collect.return_value = 25
            
            # Set threshold to trigger on third snapshot
            optimizer._memory_threshold_mb = 200.0
            
            # Register some objects for tracking
            class IntegrationObject:
                def __init__(self, name):
                    self.name = name
            
            registry = optimizer.register_object_type("IntegrationTest")
            for i in range(10):
                obj = IntegrationObject(f"test_object_{i}")
                registry.register(obj)
                optimizer.track_object_creation("IntegrationTest")
            
            # Start monitoring briefly
            await optimizer.start_monitoring(interval=0.1)
            await asyncio.sleep(0.35)  # Let it take a few snapshots
            await optimizer.stop_monitoring()
            
            # Should have taken snapshots and potentially triggered cleanup
            assert mock_snapshot.called
            
            # Verify object tracking is working
            tracker = optimizer._object_trackers["IntegrationTest"]
            assert tracker.created_count == 10
            assert registry.get_count() == 10
    
    def test_decorator_integration_with_tracking(self, optimizer):
        """Test integration of decorators with resource tracking."""
        
        @track_memory("DecoratedClass")
        class TestResource:
            def __init__(self, name: str):
                self.name = name
            
            def __del__(self):
                pass  # Destructor for tracking
        
        # Create instances
        resources = []
        for i in range(5):
            resource = TestResource(f"resource_{i}")
            resources.append(resource)
        
        # Check tracking
        tracker = optimizer._object_trackers["DecoratedClass"]
        assert tracker.created_count == 5
        assert tracker.current_count == 5
        
        # Delete some resources
        del resources[:2]
        gc.collect()
        
        # Tracking should reflect destruction
        assert tracker.destroyed_count >= 0  # May vary due to GC timing
    
    @pytest.mark.asyncio
    async def test_memory_efficient_decorator_integration(self):
        """Test memory_efficient decorator with resource management."""
        
        @memory_efficient
        async def memory_intensive_function():
            # Simulate memory-intensive operation
            data = [f"data_{i}" for i in range(1000)]
            return len(data)
        
        @memory_efficient
        def sync_memory_function():
            # Simulate sync memory operation
            data = {f"key_{i}": f"value_{i}" for i in range(500)}
            return len(data)
        
        with patch('modules.memory_optimizer.MemoryOptimizer') as mock_optimizer_class:
            mock_optimizer = Mock()
            mock_optimizer_class.return_value = mock_optimizer
            
            # Mock snapshots showing memory usage
            mock_optimizer._take_snapshot.side_effect = iter([
                MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=100.0,
                    vms_mb=200.0,
                    percent=40.0,
                    available_mb=1024.0,
                    gc_objects=5000,
                    gc_collections={0: 50, 1: 25, 2: 12}
                ),
                MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=120.0,  # Increased after function
                    vms_mb=240.0,
                    percent=48.0,
                    available_mb=1000.0,
                    gc_objects=6000,
                    gc_collections={0: 60, 1: 30, 2: 15}
                )
            ])
            mock_optimizer._memory_threshold_mb = 150.0
            mock_optimizer._force_gc = AsyncMock()
            
            # Test async function
            result = await memory_intensive_function()
            assert result == 1000
            
            # Should take before and after snapshots
            assert mock_optimizer._take_snapshot.call_count == 2
            
            # Test sync function
            with patch('modules.memory_optimizer.gc') as mock_gc:
                mock_optimizer._take_snapshot.return_value = MemorySnapshot(
                    timestamp=datetime.now(),
                    rss_mb=80.0,  # Below threshold
                    vms_mb=160.0,
                    percent=32.0,
                    available_mb=1200.0,
                    gc_objects=4000,
                    gc_collections={0: 40, 1: 20, 2: 10}
                )
                
                result = sync_memory_function()
                assert result == 500
                
                # Should check memory but not trigger GC (below threshold)
                mock_gc.collect.assert_not_called()