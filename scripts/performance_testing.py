#!/usr/bin/env python3
"""
Performance Testing and Optimization Script

This script conducts comprehensive performance testing including:
- Load testing with realistic usage patterns
- Response time measurement and optimization
- Concurrent user handling and scalability testing
- Memory usage validation and leak prevention
- Database query performance optimization
"""

import asyncio
import gc
import json
import logging
import os
import resource
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from unittest.mock import AsyncMock, MagicMock

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available, using basic resource monitoring")

from telegram import Update, Message, Chat, User
from telegram.ext import CallbackContext

# Import bot modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.database import Database
from modules.performance_monitor import PerformanceMonitor, performance_monitor
from config.config_manager import ConfigManager
from modules.error_handler import ErrorHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceTestResult:
    """Performance test result data structure."""
    test_name: str
    duration: float
    memory_before: float
    memory_after: float
    memory_peak: float
    cpu_usage: float
    success_rate: float
    error_count: int
    throughput: float
    response_times: List[float]
    timestamp: datetime


class PerformanceTester:
    """Comprehensive performance testing suite."""
    
    def __init__(self):
        self.results: List[PerformanceTestResult] = []
        self.performance_monitor = PerformanceMonitor()
        self.config_manager = ConfigManager()
        self.error_handler = ErrorHandler()
        
    async def initialize(self):
        """Initialize testing environment."""
        logger.info("Initializing performance testing environment...")
        
        # Initialize database
        await Database.initialize()
        
        # Initialize performance monitoring
        await self.performance_monitor.start_monitoring(interval=10)
        
        # Initialize config manager
        await self.config_manager.initialize()
        
        logger.info("Performance testing environment initialized")
    
    async def cleanup(self):
        """Cleanup testing environment."""
        logger.info("Cleaning up performance testing environment...")
        
        await self.performance_monitor.stop_monitoring()
        await Database.close()
        
        logger.info("Performance testing environment cleaned up")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        if HAS_PSUTIL:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        else:
            # Fallback to resource module (Unix only)
            try:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # ru_maxrss is in KB on Linux, bytes on macOS
                if sys.platform == 'darwin':
                    return usage.ru_maxrss / 1024 / 1024  # bytes to MB
                else:
                    return usage.ru_maxrss / 1024  # KB to MB
            except:
                return 0.0
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        if HAS_PSUTIL:
            return psutil.cpu_percent(interval=1)
        else:
            # Fallback - return 0 as we can't measure CPU without psutil
            return 0.0
    
    async def _monitor_resources(self, duration: float) -> Tuple[float, float]:
        """Monitor resources during test execution."""
        start_time = time.time()
        memory_readings = []
        cpu_readings = []
        
        while time.time() - start_time < duration:
            memory_readings.append(self._get_memory_usage())
            if HAS_PSUTIL:
                cpu_readings.append(psutil.cpu_percent())
            await asyncio.sleep(0.5)
        
        peak_memory = max(memory_readings) if memory_readings else 0
        avg_cpu = statistics.mean(cpu_readings) if cpu_readings else 0
        
        return peak_memory, avg_cpu
    
    async def test_database_performance(self) -> PerformanceTestResult:
        """Test database query performance and optimization."""
        logger.info("Testing database performance...")
        
        test_name = "database_performance"
        start_time = time.time()
        memory_before = self._get_memory_usage()
        response_times = []
        error_count = 0
        
        # Create test data
        test_chat = Chat(id=-1001234567890, type="supergroup", title="Test Chat")
        test_user = User(id=123456789, first_name="Test", last_name="User", username="testuser", is_bot=False)
        
        try:
            # Test chat and user operations
            for i in range(100):
                op_start = time.time()
                try:
                    await Database.save_chat_info(test_chat)
                    await Database.save_user_info(test_user)
                    response_times.append(time.time() - op_start)
                except Exception as e:
                    error_count += 1
                    logger.error(f"Database operation failed: {e}")
            
            # Test message queries
            for i in range(50):
                op_start = time.time()
                try:
                    count = await Database.get_message_count(test_chat.id)
                    messages = await Database.get_recent_messages(test_chat.id, limit=20)
                    response_times.append(time.time() - op_start)
                except Exception as e:
                    error_count += 1
                    logger.error(f"Database query failed: {e}")
            
            # Test cache operations
            for i in range(30):
                op_start = time.time()
                try:
                    cache_key = f"test_hash_{i}"
                    await Database.set_analysis_cache(test_chat.id, "test", cache_key, f"result_{i}")
                    result = await Database.get_analysis_cache(test_chat.id, "test", cache_key, 3600)
                    response_times.append(time.time() - op_start)
                except Exception as e:
                    error_count += 1
                    logger.error(f"Cache operation failed: {e}")
            
        except Exception as e:
            logger.error(f"Database performance test failed: {e}")
            error_count += 1
        
        duration = time.time() - start_time
        memory_after = self._get_memory_usage()
        memory_peak = max(memory_before, memory_after)
        cpu_usage = self._get_cpu_usage()
        
        success_rate = (len(response_times) / (len(response_times) + error_count)) * 100 if response_times or error_count else 0
        throughput = len(response_times) / duration if duration > 0 else 0
        
        result = PerformanceTestResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
            error_count=error_count,
            throughput=throughput,
            response_times=response_times,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Database performance test completed: {success_rate:.1f}% success rate, {throughput:.2f} ops/sec")
        return result
    
    async def test_concurrent_message_handling(self, concurrent_users: int = 50) -> PerformanceTestResult:
        """Test concurrent message handling performance."""
        logger.info(f"Testing concurrent message handling with {concurrent_users} users...")
        
        test_name = f"concurrent_messages_{concurrent_users}"
        start_time = time.time()
        memory_before = self._get_memory_usage()
        response_times = []
        error_count = 0
        
        # Create mock objects
        def create_mock_update(user_id: int, chat_id: int, message_text: str):
            update = MagicMock(spec=Update)
            update.message = MagicMock(spec=Message)
            update.message.text = message_text
            update.message.from_user = User(id=user_id, first_name=f"User{user_id}", is_bot=False)
            update.message.chat = Chat(id=chat_id, type="private")
            update.message.date = datetime.now()
            update.effective_user = update.message.from_user
            update.effective_chat = update.message.chat
            return update
        
        async def simulate_message_processing(user_id: int):
            """Simulate processing a message from a user."""
            try:
                op_start = time.time()
                
                # Create mock update and context
                update = create_mock_update(user_id, -1001000000000 - user_id, f"Test message from user {user_id}")
                context = MagicMock(spec=CallbackContext)
                
                # Simulate message processing (without actual GPT calls)
                await Database.save_chat_info(update.message.chat)
                await Database.save_user_info(update.message.from_user)
                
                # Simulate some processing time
                await asyncio.sleep(0.01)
                
                response_times.append(time.time() - op_start)
                
            except Exception as e:
                nonlocal error_count
                error_count += 1
                logger.error(f"Message processing failed for user {user_id}: {e}")
        
        # Run concurrent message processing
        tasks = []
        for user_id in range(concurrent_users):
            for msg_num in range(5):  # 5 messages per user
                tasks.append(simulate_message_processing(user_id * 1000 + msg_num))
        
        # Monitor resources during execution
        resource_task = asyncio.create_task(self._monitor_resources(30))
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Get resource monitoring results
        try:
            memory_peak, cpu_usage = await resource_task
        except:
            memory_peak = self._get_memory_usage()
            cpu_usage = self._get_cpu_usage()
        
        duration = time.time() - start_time
        memory_after = self._get_memory_usage()
        
        success_rate = (len(response_times) / (len(response_times) + error_count)) * 100 if response_times or error_count else 0
        throughput = len(response_times) / duration if duration > 0 else 0
        
        result = PerformanceTestResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
            error_count=error_count,
            throughput=throughput,
            response_times=response_times,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Concurrent message test completed: {success_rate:.1f}% success rate, {throughput:.2f} msgs/sec")
        return result
    
    async def test_memory_leak_detection(self) -> PerformanceTestResult:
        """Test for memory leaks during extended operation."""
        logger.info("Testing memory leak detection...")
        
        test_name = "memory_leak_detection"
        start_time = time.time()
        memory_before = self._get_memory_usage()
        memory_readings = []
        error_count = 0
        
        # Run operations for extended period
        for cycle in range(10):
            cycle_start_memory = self._get_memory_usage()
            
            try:
                # Simulate various operations
                for i in range(100):
                    # Database operations
                    test_chat = Chat(id=-1001000000000 - i, type="group", title=f"Test Chat {i}")
                    await Database.save_chat_info(test_chat)
                    
                    # Cache operations
                    await Database.set_analysis_cache(test_chat.id, "test", f"hash_{i}", f"result_{i}")
                    
                    # Performance monitoring
                    self.performance_monitor.record_metric(f"test_metric_{i}", float(i), "count")
                
                # Force garbage collection
                gc.collect()
                
                cycle_end_memory = self._get_memory_usage()
                memory_readings.append(cycle_end_memory)
                
                logger.info(f"Cycle {cycle + 1}: Memory {cycle_start_memory:.1f}MB -> {cycle_end_memory:.1f}MB")
                
                # Small delay between cycles
                await asyncio.sleep(1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Memory leak test cycle {cycle} failed: {e}")
        
        duration = time.time() - start_time
        memory_after = self._get_memory_usage()
        memory_peak = max(memory_readings) if memory_readings else memory_after
        cpu_usage = self._get_cpu_usage()
        
        # Analyze memory trend
        memory_growth = memory_after - memory_before
        memory_growth_rate = memory_growth / duration if duration > 0 else 0
        
        # Consider it a leak if memory grows more than 50MB or 20% of initial memory
        has_leak = memory_growth > 50 or memory_growth > (memory_before * 0.2)
        
        success_rate = 100.0 if not has_leak and error_count == 0 else 0.0
        throughput = len(memory_readings) / duration if duration > 0 else 0
        
        result = PerformanceTestResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
            error_count=error_count,
            throughput=throughput,
            response_times=[memory_growth_rate],
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        
        if has_leak:
            logger.warning(f"Potential memory leak detected: {memory_growth:.1f}MB growth over {duration:.1f}s")
        else:
            logger.info(f"No memory leaks detected: {memory_growth:.1f}MB growth over {duration:.1f}s")
        
        return result
    
    async def test_response_time_optimization(self) -> PerformanceTestResult:
        """Test response time optimization for various operations."""
        logger.info("Testing response time optimization...")
        
        test_name = "response_time_optimization"
        start_time = time.time()
        memory_before = self._get_memory_usage()
        response_times = []
        error_count = 0
        
        # Test various operations
        operations = [
            ("database_query", self._test_database_query),
            ("cache_operation", self._test_cache_operation),
            ("config_lookup", self._test_config_lookup),
            ("error_handling", self._test_error_handling),
        ]
        
        for op_name, op_func in operations:
            for i in range(20):
                try:
                    op_start = time.time()
                    await op_func(i)
                    op_duration = time.time() - op_start
                    response_times.append(op_duration)
                    
                    # Log slow operations
                    if op_duration > 1.0:
                        logger.warning(f"Slow operation detected: {op_name} took {op_duration:.3f}s")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Operation {op_name} failed: {e}")
        
        duration = time.time() - start_time
        memory_after = self._get_memory_usage()
        memory_peak = max(memory_before, memory_after)
        cpu_usage = self._get_cpu_usage()
        
        success_rate = (len(response_times) / (len(response_times) + error_count)) * 100 if response_times or error_count else 0
        throughput = len(response_times) / duration if duration > 0 else 0
        
        # Calculate response time statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            max_response_time = max(response_times)
            
            logger.info(f"Response times - Avg: {avg_response_time:.3f}s, P95: {p95_response_time:.3f}s, Max: {max_response_time:.3f}s")
        
        result = PerformanceTestResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
            error_count=error_count,
            throughput=throughput,
            response_times=response_times,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Response time test completed: {success_rate:.1f}% success rate, {throughput:.2f} ops/sec")
        return result
    
    async def _test_database_query(self, iteration: int):
        """Test database query performance."""
        chat_id = -1001000000000 - iteration
        await Database.get_message_count(chat_id)
        await Database.get_recent_messages(chat_id, limit=10)
    
    async def _test_cache_operation(self, iteration: int):
        """Test cache operation performance."""
        chat_id = -1001000000000 - iteration
        cache_key = f"test_key_{iteration}"
        await Database.set_analysis_cache(chat_id, "test", cache_key, f"value_{iteration}")
        await Database.get_analysis_cache(chat_id, "test", cache_key, 3600)
    
    async def _test_config_lookup(self, iteration: int):
        """Test configuration lookup performance."""
        chat_id = str(-1001000000000 - iteration)
        config = await self.config_manager.get_config(chat_id=chat_id, chat_type="supergroup")
    
    async def _test_error_handling(self, iteration: int):
        """Test error handling performance."""
        try:
            # Simulate an error condition
            if iteration % 10 == 0:
                raise ValueError(f"Test error {iteration}")
        except ValueError as e:
            # Handle the error through the error handler
            await self.error_handler.handle_error(e, {"test": True})
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.results:
            return {"error": "No test results available"}
        
        report = {
            "summary": {
                "total_tests": len(self.results),
                "test_duration": sum(r.duration for r in self.results),
                "overall_success_rate": statistics.mean([r.success_rate for r in self.results]),
                "total_errors": sum(r.error_count for r in self.results),
                "generated_at": datetime.now().isoformat()
            },
            "test_results": [],
            "performance_analysis": {},
            "recommendations": []
        }
        
        # Add individual test results
        for result in self.results:
            test_data = asdict(result)
            test_data['timestamp'] = result.timestamp.isoformat()
            
            # Add response time statistics
            if result.response_times:
                test_data['response_time_stats'] = {
                    'min': min(result.response_times),
                    'max': max(result.response_times),
                    'avg': statistics.mean(result.response_times),
                    'median': statistics.median(result.response_times),
                    'p95': statistics.quantiles(result.response_times, n=20)[18] if len(result.response_times) >= 20 else max(result.response_times)
                }
            
            report["test_results"].append(test_data)
        
        # Performance analysis
        all_response_times = []
        for result in self.results:
            all_response_times.extend(result.response_times)
        
        if all_response_times:
            report["performance_analysis"] = {
                "overall_response_times": {
                    'min': min(all_response_times),
                    'max': max(all_response_times),
                    'avg': statistics.mean(all_response_times),
                    'median': statistics.median(all_response_times),
                    'p95': statistics.quantiles(all_response_times, n=20)[18] if len(all_response_times) >= 20 else max(all_response_times)
                },
                "memory_usage": {
                    'max_memory_used': max(r.memory_peak for r in self.results),
                    'avg_memory_growth': statistics.mean([r.memory_after - r.memory_before for r in self.results]),
                    'max_memory_growth': max([r.memory_after - r.memory_before for r in self.results])
                },
                "throughput": {
                    'max_throughput': max(r.throughput for r in self.results),
                    'avg_throughput': statistics.mean([r.throughput for r in self.results])
                }
            }
        
        # Generate recommendations
        recommendations = []
        
        # Check for slow operations
        slow_tests = [r for r in self.results if r.response_times and max(r.response_times) > 2.0]
        if slow_tests:
            recommendations.append({
                "type": "performance",
                "priority": "high",
                "issue": "Slow operations detected",
                "details": f"{len(slow_tests)} tests had operations slower than 2 seconds",
                "recommendation": "Investigate and optimize slow database queries and external API calls"
            })
        
        # Check for memory issues
        high_memory_tests = [r for r in self.results if r.memory_peak > 500]
        if high_memory_tests:
            recommendations.append({
                "type": "memory",
                "priority": "medium",
                "issue": "High memory usage detected",
                "details": f"{len(high_memory_tests)} tests used more than 500MB of memory",
                "recommendation": "Review memory usage patterns and implement memory optimization strategies"
            })
        
        # Check for error rates
        high_error_tests = [r for r in self.results if r.success_rate < 95]
        if high_error_tests:
            recommendations.append({
                "type": "reliability",
                "priority": "high",
                "issue": "High error rates detected",
                "details": f"{len(high_error_tests)} tests had success rates below 95%",
                "recommendation": "Investigate and fix error conditions to improve system reliability"
            })
        
        # Check for low throughput
        low_throughput_tests = [r for r in self.results if r.throughput < 10]
        if low_throughput_tests:
            recommendations.append({
                "type": "scalability",
                "priority": "medium",
                "issue": "Low throughput detected",
                "details": f"{len(low_throughput_tests)} tests had throughput below 10 operations per second",
                "recommendation": "Optimize critical paths and consider implementing caching strategies"
            })
        
        report["recommendations"] = recommendations
        
        return report
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests and generate report."""
        logger.info("Starting comprehensive performance testing...")
        
        try:
            await self.initialize()
            
            # Run all performance tests
            await self.test_database_performance()
            await self.test_concurrent_message_handling(concurrent_users=25)
            await self.test_concurrent_message_handling(concurrent_users=50)
            await self.test_memory_leak_detection()
            await self.test_response_time_optimization()
            
            # Generate and return report
            report = self.generate_performance_report()
            
            logger.info("Performance testing completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Performance testing failed: {e}")
            raise
        finally:
            await self.cleanup()


async def main():
    """Main function to run performance tests."""
    tester = PerformanceTester()
    
    try:
        report = await tester.run_all_tests()
        
        # Save report to file
        report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance report saved to {report_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("PERFORMANCE TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Overall Success Rate: {report['summary']['overall_success_rate']:.1f}%")
        print(f"Total Duration: {report['summary']['test_duration']:.2f}s")
        print(f"Total Errors: {report['summary']['total_errors']}")
        
        if report.get('recommendations'):
            print(f"\nRecommendations: {len(report['recommendations'])}")
            for rec in report['recommendations'][:3]:  # Show top 3
                print(f"  - {rec['issue']} ({rec['priority']} priority)")
        
        print("="*80)
        
    except Exception as e:
        logger.error(f"Performance testing failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)