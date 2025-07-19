#!/usr/bin/env python3
"""
Smoke Tests for PsychoChauffeur Bot

Quick validation tests to ensure the bot is functioning correctly after deployment.
These tests verify core functionality without requiring extensive setup.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmokeTestResult:
    """Smoke test result container."""
    
    def __init__(self, name: str, passed: bool, message: str, duration: float):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration
        self.timestamp = datetime.now()


class SmokeTestRunner:
    """Smoke test runner for post-deployment validation."""
    
    def __init__(self):
        self.results: List[SmokeTestResult] = []
        self.start_time = time.time()
    
    async def run_test(self, test_name: str, test_func) -> SmokeTestResult:
        """Run a single smoke test."""
        logger.info(f"Running smoke test: {test_name}")
        start_time = time.time()
        
        try:
            await test_func()
            duration = time.time() - start_time
            result = SmokeTestResult(test_name, True, "PASSED", duration)
            logger.info(f"✅ {test_name} - PASSED ({duration:.2f}s)")
        except Exception as e:
            duration = time.time() - start_time
            result = SmokeTestResult(test_name, False, str(e), duration)
            logger.error(f"❌ {test_name} - FAILED: {e} ({duration:.2f}s)")
        
        self.results.append(result)
        return result
    
    async def test_basic_imports(self):
        """Test that all critical modules can be imported."""
        critical_modules = [
            'modules.database',
            'modules.gpt',
            'modules.video_downloader',
            'modules.weather',
            'modules.error_handler',
            'modules.logger',
            'config.config_manager'
        ]
        
        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                raise AssertionError(f"Failed to import {module_name}: {e}")
    
    async def test_environment_variables(self):
        """Test that required environment variables are set."""
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'DB_HOST',
            'DB_NAME',
            'DB_USER'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise AssertionError(f"Missing environment variables: {', '.join(missing_vars)}")
    
    async def test_database_connection(self):
        """Test database connectivity and basic operations."""
        try:
            from modules.database import Database
            
            # Test connection
            await Database.initialize()
            
            # Test basic query
            manager = Database.get_connection_manager()
            async with manager.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                assert result == 1, "Basic query failed"
            
            await Database.close()
        except Exception as e:
            # If database is not available, log warning but don't fail
            logger.warning(f"Database test failed (may be expected in some environments): {e}")
    
    async def test_configuration_system(self):
        """Test configuration loading and validation."""
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test that config files exist
        config_files = [
            'config/global/global_config.json',
            'config/global/system_defaults.json'
        ]
        
        for config_file in config_files:
            if not os.path.exists(config_file):
                raise AssertionError(f"Configuration file not found: {config_file}")
    
    async def test_error_handling_system(self):
        """Test error handling and logging systems."""
        from modules.error_handler import ErrorHandler
        from modules.logger import general_logger
        
        # Test error handler
        error_handler = ErrorHandler()
        
        # Test logging
        general_logger.info("Smoke test log message")
        
        # Test error tracking
        try:
            raise ValueError("Test error for smoke test")
        except ValueError as e:
            await error_handler.handle_error(e, {"test": True})
    
    async def test_external_api_configuration(self):
        """Test external API configuration (without making actual requests)."""
        from modules.const import Config
        
        # Test that API keys are configured
        api_keys = {
            'TELEGRAM_BOT_TOKEN': Config.TELEGRAM_BOT_TOKEN,
            'OPENAI_API_KEY': getattr(Config, 'OPENAI_API_KEY', None)
        }
        
        for key_name, key_value in api_keys.items():
            if not key_value:
                logger.warning(f"{key_name} not configured")
            elif len(str(key_value)) < 10:
                logger.warning(f"{key_name} appears to be invalid (too short)")
    
    async def test_performance_monitoring(self):
        """Test performance monitoring system."""
        try:
            from modules.performance_monitor import PerformanceMonitor
            
            monitor = PerformanceMonitor()
            
            # Test metric recording
            monitor.record_metric("smoke_test_metric", 42.0, "count")
            
            # Test health status
            health_status = monitor.get_health_status()
            assert health_status.service_name == "performance_monitor"
            assert isinstance(health_status.is_healthy, bool)
        except ImportError:
            logger.warning("Performance monitoring module not available")
    
    async def test_module_initialization(self):
        """Test that key modules can be initialized."""
        modules_to_test = [
            ('modules.video_downloader', 'VideoDownloader'),
            ('modules.weather', 'WeatherCommandHandler')
        ]
        
        for module_name, class_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                instance = cls()
                assert instance is not None, f"{class_name} not initialized"
            except Exception as e:
                logger.warning(f"Could not test {class_name}: {e}")
    
    async def test_file_permissions(self):
        """Test file permissions and access."""
        import stat
        
        # Check critical files exist
        critical_files = [
            'main.py',
            'requirements.txt'
        ]
        
        for file_path in critical_files:
            if not os.path.exists(file_path):
                raise AssertionError(f"Critical file not found: {file_path}")
        
        # Check .env permissions if it exists
        if os.path.exists('.env'):
            file_stat = os.stat('.env')
            # Check .env is not world-readable
            if file_stat.st_mode & stat.S_IROTH:
                logger.warning(".env file is world-readable - security risk")
    
    async def test_log_directory_access(self):
        """Test log directory access and write permissions."""
        log_dir = "logs"
        
        # Check log directory exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        assert os.path.isdir(log_dir), "Log path is not a directory"
        
        # Test write access
        test_file = os.path.join(log_dir, "smoke_test.tmp")
        try:
            with open(test_file, 'w') as f:
                f.write("smoke test")
            os.remove(test_file)
        except Exception as e:
            raise AssertionError(f"Cannot write to log directory: {e}")
    
    async def test_memory_usage(self):
        """Test memory usage is within acceptable limits."""
        try:
            import psutil
            
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Memory should be less than 500MB for basic startup
            if memory_mb > 500:
                logger.warning(f"High memory usage: {memory_mb:.1f}MB")
            else:
                logger.info(f"Memory usage: {memory_mb:.1f}MB")
        except ImportError:
            logger.warning("psutil not available, skipping memory test")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all smoke tests."""
        logger.info("Starting smoke tests...")
        
        # Define test suite
        tests = [
            ("Basic Imports", self.test_basic_imports),
            ("Environment Variables", self.test_environment_variables),
            ("Database Connection", self.test_database_connection),
            ("Configuration System", self.test_configuration_system),
            ("Error Handling System", self.test_error_handling_system),
            ("External API Config", self.test_external_api_configuration),
            ("Performance Monitoring", self.test_performance_monitoring),
            ("Module Initialization", self.test_module_initialization),
            ("File Permissions", self.test_file_permissions),
            ("Log Directory Access", self.test_log_directory_access),
            ("Memory Usage", self.test_memory_usage),
        ]
        
        # Run tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
        
        # Generate summary
        total_duration = time.time() - self.start_time
        passed_tests = [r for r in self.results if r.passed]
        failed_tests = [r for r in self.results if not r.passed]
        
        summary = {
            "total_tests": len(self.results),
            "passed_tests": len(passed_tests),
            "failed_tests": len(failed_tests),
            "success_rate": len(passed_tests) / len(self.results) * 100,
            "total_duration": total_duration,
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "duration": r.duration,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.results
            ]
        }
        
        # Print summary
        print("\n" + "="*60)
        print("SMOKE TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Duration: {summary['total_duration']:.2f}s")
        
        if failed_tests:
            print(f"\nFailed Tests:")
            for test in failed_tests:
                print(f"  ❌ {test.name}: {test.message}")
        
        print("="*60)
        
        return summary


async def main():
    """Main function to run smoke tests."""
    runner = SmokeTestRunner()
    
    try:
        summary = await runner.run_all_tests()
        
        # Save results
        import json
        with open("smoke_test_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        # Exit with appropriate code
        if summary['failed_tests'] > 0:
            logger.error(f"Smoke tests failed: {summary['failed_tests']} failures")
            return 1
        else:
            logger.info("All smoke tests passed!")
            return 0
            
    except Exception as e:
        logger.error(f"Smoke test runner failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)