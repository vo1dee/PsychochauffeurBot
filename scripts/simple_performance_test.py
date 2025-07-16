#!/usr/bin/env python3
"""
Simple Performance Testing Script

This script conducts basic performance testing without requiring database connections:
- Memory usage monitoring
- Response time measurement
- Code optimization analysis
- Performance bottleneck identification
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
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available, using basic resource monitoring")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceResult:
    """Performance test result data structure."""
    test_name: str
    duration: float
    memory_before: float
    memory_after: float
    memory_peak: float
    operations_count: int
    throughput: float
    response_times: List[float]
    success_rate: float
    timestamp: datetime


class SimplePerformanceTester:
    """Simple performance testing without external dependencies."""
    
    def __init__(self):
        self.results: List[PerformanceResult] = []
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        if HAS_PSUTIL:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        else:
            try:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                if sys.platform == 'darwin':
                    return usage.ru_maxrss / 1024 / 1024  # bytes to MB
                else:
                    return usage.ru_maxrss / 1024  # KB to MB
            except:
                return 0.0
    
    async def test_async_operations(self) -> PerformanceResult:
        """Test async operation performance."""
        logger.info("Testing async operations performance...")
        
        test_name = "async_operations"
        start_time = time.time()
        memory_before = self.get_memory_usage()
        response_times = []
        operations_count = 0
        
        async def async_operation(delay: float = 0.001):
            """Simulate an async operation."""
            await asyncio.sleep(delay)
            return f"result_{time.time()}"
        
        # Test concurrent async operations
        for batch in range(10):
            batch_start = time.time()
            
            # Create 50 concurrent operations
            tasks = [async_operation(0.001) for _ in range(50)]
            results = await asyncio.gather(*tasks)
            
            batch_duration = time.time() - batch_start
            response_times.append(batch_duration)
            operations_count += len(results)
        
        duration = time.time() - start_time
        memory_after = self.get_memory_usage()
        memory_peak = max(memory_before, memory_after)
        
        success_rate = 100.0  # All operations succeeded
        throughput = operations_count / duration if duration > 0 else 0
        
        result = PerformanceResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            operations_count=operations_count,
            throughput=throughput,
            response_times=response_times,
            success_rate=success_rate,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Async operations test completed: {throughput:.2f} ops/sec")
        return result
    
    async def test_memory_usage_patterns(self) -> PerformanceResult:
        """Test memory usage patterns and potential leaks."""
        logger.info("Testing memory usage patterns...")
        
        test_name = "memory_patterns"
        start_time = time.time()
        memory_before = self.get_memory_usage()
        memory_readings = []
        operations_count = 0
        
        # Simulate memory-intensive operations
        data_structures = []
        
        for cycle in range(20):
            cycle_start_memory = self.get_memory_usage()
            
            # Create and manipulate data structures
            large_list = list(range(10000))
            large_dict = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}
            data_structures.append((large_list, large_dict))
            
            # Simulate processing
            processed_data = [x * 2 for x in large_list[:1000]]
            filtered_dict = {k: v for k, v in large_dict.items() if len(k) > 5}
            
            operations_count += 2
            
            # Clean up some data
            if len(data_structures) > 10:
                data_structures.pop(0)
            
            cycle_end_memory = self.get_memory_usage()
            memory_readings.append(cycle_end_memory)
            
            # Force garbage collection every few cycles
            if cycle % 5 == 0:
                gc.collect()
        
        duration = time.time() - start_time
        memory_after = self.get_memory_usage()
        memory_peak = max(memory_readings) if memory_readings else memory_after
        
        # Analyze memory growth
        memory_growth = memory_after - memory_before
        has_potential_leak = memory_growth > 50  # More than 50MB growth
        
        success_rate = 100.0 if not has_potential_leak else 80.0
        throughput = operations_count / duration if duration > 0 else 0
        
        result = PerformanceResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            operations_count=operations_count,
            throughput=throughput,
            response_times=[memory_growth],
            success_rate=success_rate,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Memory patterns test completed: {memory_growth:.1f}MB growth")
        return result
    
    async def test_string_processing_performance(self) -> PerformanceResult:
        """Test string processing performance (common in message handling)."""
        logger.info("Testing string processing performance...")
        
        test_name = "string_processing"
        start_time = time.time()
        memory_before = self.get_memory_usage()
        response_times = []
        operations_count = 0
        
        # Test data
        test_strings = [
            "This is a test message with some URLs like https://example.com and https://test.org",
            "Another message with @username mentions and #hashtags",
            "Message with emojis 🚀 🎉 and special characters !@#$%^&*()",
            "Very long message " + "word " * 1000,
            "Short msg",
        ]
        
        # String processing operations
        for iteration in range(100):
            iteration_start = time.time()
            
            for text in test_strings:
                # Simulate common string operations
                processed = text.lower().strip()
                words = processed.split()
                filtered_words = [w for w in words if len(w) > 3]
                joined = " ".join(filtered_words)
                
                # URL extraction simulation
                import re
                urls = re.findall(r'https?://[^\s]+', text)
                
                # Mention extraction
                mentions = re.findall(r'@\w+', text)
                
                operations_count += 5  # 5 operations per string
            
            iteration_duration = time.time() - iteration_start
            response_times.append(iteration_duration)
        
        duration = time.time() - start_time
        memory_after = self.get_memory_usage()
        memory_peak = max(memory_before, memory_after)
        
        success_rate = 100.0
        throughput = operations_count / duration if duration > 0 else 0
        
        result = PerformanceResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            operations_count=operations_count,
            throughput=throughput,
            response_times=response_times,
            success_rate=success_rate,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"String processing test completed: {throughput:.2f} ops/sec")
        return result
    
    async def test_json_processing_performance(self) -> PerformanceResult:
        """Test JSON processing performance (common in config and API operations)."""
        logger.info("Testing JSON processing performance...")
        
        test_name = "json_processing"
        start_time = time.time()
        memory_before = self.get_memory_usage()
        response_times = []
        operations_count = 0
        
        # Create test JSON data
        test_data = {
            "config": {
                "modules": {
                    "gpt": {"enabled": True, "model": "gpt-4", "temperature": 0.7},
                    "weather": {"enabled": True, "api_key": "test_key"},
                    "video": {"enabled": True, "quality": "720p"}
                },
                "chats": {str(i): {"title": f"Chat {i}", "settings": {"lang": "en"}} for i in range(100)},
                "users": {str(i): {"name": f"User {i}", "preferences": {"theme": "dark"}} for i in range(500)}
            }
        }
        
        for iteration in range(50):
            iteration_start = time.time()
            
            # JSON serialization
            json_str = json.dumps(test_data)
            operations_count += 1
            
            # JSON deserialization
            parsed_data = json.loads(json_str)
            operations_count += 1
            
            # Data manipulation
            parsed_data["timestamp"] = time.time()
            parsed_data["config"]["modules"]["new_module"] = {"enabled": False}
            operations_count += 2
            
            # Re-serialization
            final_json = json.dumps(parsed_data)
            operations_count += 1
            
            iteration_duration = time.time() - iteration_start
            response_times.append(iteration_duration)
        
        duration = time.time() - start_time
        memory_after = self.get_memory_usage()
        memory_peak = max(memory_before, memory_after)
        
        success_rate = 100.0
        throughput = operations_count / duration if duration > 0 else 0
        
        result = PerformanceResult(
            test_name=test_name,
            duration=duration,
            memory_before=memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            operations_count=operations_count,
            throughput=throughput,
            response_times=response_times,
            success_rate=success_rate,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"JSON processing test completed: {throughput:.2f} ops/sec")
        return result
    
    def analyze_code_complexity(self) -> Dict[str, Any]:
        """Analyze code complexity and identify optimization opportunities."""
        logger.info("Analyzing code complexity...")
        
        analysis = {
            "files_analyzed": 0,
            "total_lines": 0,
            "complex_functions": [],
            "large_files": [],
            "optimization_opportunities": []
        }
        
        # Analyze main Python files
        files_to_analyze = [
            "main.py",
            "modules/database.py",
            "modules/gpt.py",
            "modules/video_downloader.py",
            "modules/message_processor.py",
            "config/config_manager.py"
        ]
        
        for file_path in files_to_analyze:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        analysis["total_lines"] += line_count
                        analysis["files_analyzed"] += 1
                        
                        # Check for large files
                        if line_count > 500:
                            analysis["large_files"].append({
                                "file": file_path,
                                "lines": line_count,
                                "recommendation": "Consider breaking into smaller modules"
                            })
                        
                        # Look for complex patterns
                        function_lines = 0
                        current_function = None
                        indent_level = 0
                        
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            
                            # Track function definitions
                            if stripped.startswith('def ') or stripped.startswith('async def '):
                                if current_function and function_lines > 50:
                                    analysis["complex_functions"].append({
                                        "file": file_path,
                                        "function": current_function,
                                        "lines": function_lines,
                                        "line_number": i - function_lines + 1
                                    })
                                
                                current_function = stripped.split('(')[0].replace('def ', '').replace('async ', '')
                                function_lines = 1
                                indent_level = len(line) - len(line.lstrip())
                            elif current_function:
                                current_line_indent = len(line) - len(line.lstrip())
                                if stripped and current_line_indent > indent_level:
                                    function_lines += 1
                                elif stripped and current_line_indent <= indent_level:
                                    # Function ended
                                    if function_lines > 50:
                                        analysis["complex_functions"].append({
                                            "file": file_path,
                                            "function": current_function,
                                            "lines": function_lines,
                                            "line_number": i - function_lines + 1
                                        })
                                    current_function = None
                                    function_lines = 0
                        
                        # Check final function
                        if current_function and function_lines > 50:
                            analysis["complex_functions"].append({
                                "file": file_path,
                                "function": current_function,
                                "lines": function_lines,
                                "line_number": len(lines) - function_lines + 1
                            })
                
                except Exception as e:
                    logger.warning(f"Could not analyze {file_path}: {e}")
        
        # Generate optimization recommendations
        if analysis["large_files"]:
            analysis["optimization_opportunities"].append({
                "type": "modularity",
                "priority": "medium",
                "description": f"{len(analysis['large_files'])} files are larger than 500 lines",
                "recommendation": "Break large files into smaller, focused modules"
            })
        
        if analysis["complex_functions"]:
            analysis["optimization_opportunities"].append({
                "type": "complexity",
                "priority": "high",
                "description": f"{len(analysis['complex_functions'])} functions are longer than 50 lines",
                "recommendation": "Refactor complex functions into smaller, single-purpose functions"
            })
        
        if analysis["total_lines"] > 10000:
            analysis["optimization_opportunities"].append({
                "type": "architecture",
                "priority": "medium",
                "description": f"Codebase has {analysis['total_lines']} lines across {analysis['files_analyzed']} files",
                "recommendation": "Consider implementing more modular architecture patterns"
            })
        
        return analysis
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.results:
            return {"error": "No test results available"}
        
        # Code complexity analysis
        code_analysis = self.analyze_code_complexity()
        
        report = {
            "summary": {
                "total_tests": len(self.results),
                "test_duration": sum(r.duration for r in self.results),
                "total_operations": sum(r.operations_count for r in self.results),
                "overall_throughput": sum(r.throughput for r in self.results) / len(self.results),
                "generated_at": datetime.now().isoformat()
            },
            "test_results": [],
            "code_analysis": code_analysis,
            "performance_insights": {},
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
                    'median': statistics.median(result.response_times)
                }
            
            report["test_results"].append(test_data)
        
        # Performance insights
        memory_usage = [r.memory_peak for r in self.results]
        throughput_values = [r.throughput for r in self.results]
        
        report["performance_insights"] = {
            "memory_usage": {
                "max_memory_used": max(memory_usage) if memory_usage else 0,
                "avg_memory_used": statistics.mean(memory_usage) if memory_usage else 0,
                "memory_efficiency": "good" if max(memory_usage) < 200 else "needs_attention"
            },
            "throughput": {
                "max_throughput": max(throughput_values) if throughput_values else 0,
                "avg_throughput": statistics.mean(throughput_values) if throughput_values else 0,
                "throughput_consistency": statistics.stdev(throughput_values) if len(throughput_values) > 1 else 0
            }
        }
        
        # Generate recommendations
        recommendations = []
        
        # Memory recommendations
        if max(memory_usage) > 200:
            recommendations.append({
                "type": "memory",
                "priority": "high",
                "issue": "High memory usage detected",
                "details": f"Peak memory usage: {max(memory_usage):.1f}MB",
                "recommendation": "Implement memory optimization strategies and garbage collection"
            })
        
        # Throughput recommendations
        if statistics.mean(throughput_values) < 100:
            recommendations.append({
                "type": "performance",
                "priority": "medium",
                "issue": "Low throughput detected",
                "details": f"Average throughput: {statistics.mean(throughput_values):.1f} ops/sec",
                "recommendation": "Optimize critical code paths and consider async optimizations"
            })
        
        # Code complexity recommendations
        if code_analysis["complex_functions"]:
            recommendations.append({
                "type": "maintainability",
                "priority": "medium",
                "issue": "Complex functions detected",
                "details": f"{len(code_analysis['complex_functions'])} functions exceed 50 lines",
                "recommendation": "Refactor complex functions for better maintainability"
            })
        
        report["recommendations"] = recommendations
        
        return report
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests and generate report."""
        logger.info("Starting simple performance testing...")
        
        try:
            # Run all performance tests
            await self.test_async_operations()
            await self.test_memory_usage_patterns()
            await self.test_string_processing_performance()
            await self.test_json_processing_performance()
            
            # Generate and return report
            report = self.generate_performance_report()
            
            logger.info("Performance testing completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Performance testing failed: {e}")
            raise


async def main():
    """Main function to run performance tests."""
    tester = SimplePerformanceTester()
    
    try:
        report = await tester.run_all_tests()
        
        # Save report to file
        report_file = f"simple_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Performance report saved to {report_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("SIMPLE PERFORMANCE TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Total Operations: {report['summary']['total_operations']}")
        print(f"Overall Throughput: {report['summary']['overall_throughput']:.2f} ops/sec")
        print(f"Test Duration: {report['summary']['test_duration']:.2f}s")
        
        # Code analysis summary
        if report.get('code_analysis'):
            ca = report['code_analysis']
            print(f"\nCode Analysis:")
            print(f"  Files Analyzed: {ca['files_analyzed']}")
            print(f"  Total Lines: {ca['total_lines']}")
            print(f"  Complex Functions: {len(ca['complex_functions'])}")
            print(f"  Large Files: {len(ca['large_files'])}")
        
        # Performance insights
        if report.get('performance_insights'):
            pi = report['performance_insights']
            print(f"\nPerformance Insights:")
            print(f"  Max Memory: {pi['memory_usage']['max_memory_used']:.1f}MB")
            print(f"  Memory Efficiency: {pi['memory_usage']['memory_efficiency']}")
            print(f"  Max Throughput: {pi['throughput']['max_throughput']:.2f} ops/sec")
        
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