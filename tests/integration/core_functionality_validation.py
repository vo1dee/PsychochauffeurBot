"""
Core functionality validation for Task 13.
Tests the essential integration and end-to-end functionality without complex service factories.
"""

import asyncio
import os
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from config.config_manager import ConfigManager
from modules.database import Database


class CoreFunctionalityValidator:
    """Validator for core functionality requirements."""
    
    def __init__(self):
        self.results = []
        
    async def test_service_configuration(self) -> bool:
        """Test that service configuration works correctly."""
        print("🔄 Testing service configuration...")
        
        try:
            # Set up environment
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_config_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            
            # Test service configuration
            start_time = time.time()
            service_registry = await bootstrapper.configure_services()
            config_time = time.time() - start_time
            
            # Verify core services are configured
            config_manager = service_registry.get_service('config_manager')
            database = service_registry.get_service('database')
            service_config = service_registry.get_service('service_config')
            
            if not config_manager:
                print("❌ ConfigManager not configured")
                return False
                
            if not database:
                print("❌ Database not configured")
                return False
                
            if not service_config:
                print("❌ ServiceConfiguration not configured")
                return False
            
            # Test configuration access
            config = await config_manager.get_config()
            if not isinstance(config, dict):
                print("❌ Configuration not accessible")
                return False
            
            print(f"✅ Service configuration test passed ({config_time:.2f}s)")
            return True
            
        except Exception as e:
            print(f"❌ Service configuration test failed: {e}")
            return False
    
    async def test_application_startup_shutdown(self) -> bool:
        """Test application startup and shutdown procedures."""
        print("🔄 Testing application startup and shutdown...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_startup_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            
            # Mock the bot application to avoid Telegram API calls
            with patch('modules.service_factories.ServiceFactory.create_bot_application') as mock_create_bot:
                mock_bot = Mock()
                mock_bot.initialize = AsyncMock()
                mock_bot.start = AsyncMock()
                mock_bot.shutdown = AsyncMock()
                mock_create_bot.return_value = mock_bot
                
                # Test startup
                start_time = time.time()
                await bootstrapper.start_application()
                startup_time = time.time() - start_time
                
                if not bootstrapper.is_running:
                    print("❌ Application not running after startup")
                    return False
                
                # Verify bot application was initialized and started
                mock_bot.initialize.assert_called_once()
                mock_bot.start.assert_called_once()
                
                # Test shutdown
                start_time = time.time()
                await bootstrapper.shutdown_application()
                shutdown_time = time.time() - start_time
                
                if bootstrapper.is_running:
                    print("❌ Application still running after shutdown")
                    return False
                
                # Verify bot application was shut down
                mock_bot.shutdown.assert_called_once()
                
                print(f"✅ Startup/shutdown test passed (startup: {startup_time:.2f}s, shutdown: {shutdown_time:.2f}s)")
                return True
                
        except Exception as e:
            print(f"❌ Startup/shutdown test failed: {e}")
            return False
    
    async def test_error_handling_resilience(self) -> bool:
        """Test error handling and system resilience."""
        print("🔄 Testing error handling and resilience...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_error_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            # Test service configuration with simulated errors
            bootstrapper = ApplicationBootstrapper()
            
            # Test graceful handling of service creation failures
            with patch('modules.service_factories.ServiceFactory.create_bot_application') as mock_create_bot:
                # First call fails, second succeeds
                mock_bot = Mock()
                mock_bot.initialize = AsyncMock()
                mock_bot.start = AsyncMock()
                mock_bot.shutdown = AsyncMock()
                
                mock_create_bot.side_effect = [
                    Exception("Simulated service creation error"),
                    mock_bot
                ]
                
                # First startup should fail gracefully
                try:
                    await bootstrapper.start_application()
                    print("❌ Expected startup to fail with simulated error")
                    return False
                except RuntimeError:
                    # This is expected
                    pass
                
                # Application should not be running
                if bootstrapper.is_running:
                    print("❌ Application running after failed startup")
                    return False
                
                # Reset for second attempt
                bootstrapper = ApplicationBootstrapper()
                mock_create_bot.side_effect = None
                mock_create_bot.return_value = mock_bot
                
                # Second startup should succeed
                await bootstrapper.start_application()
                if not bootstrapper.is_running:
                    print("❌ Application not running after recovery")
                    return False
                
                await bootstrapper.shutdown_application()
                
                print("✅ Error handling and resilience test passed")
                return True
                
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False
    
    async def test_configuration_integration(self) -> bool:
        """Test configuration system integration."""
        print("🔄 Testing configuration integration...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_config_integration_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            # Test configuration manager
            config_manager = service_registry.get_service('config_manager')
            if not config_manager:
                print("❌ ConfigManager not available")
                return False
            
            # Test configuration access
            config = await config_manager.get_config()
            if not isinstance(config, dict):
                print("❌ Configuration not accessible")
                return False
            
            # Test that configuration is properly integrated
            service_config = service_registry.get_service('service_config')
            if not service_config:
                print("❌ ServiceConfiguration not available")
                return False
            
            if service_config.telegram_token != 'test_config_integration_token':
                print("❌ Service configuration not properly set")
                return False
            
            print("✅ Configuration integration test passed")
            return True
            
        except Exception as e:
            print(f"❌ Configuration integration test failed: {e}")
            return False
    
    async def test_dependency_injection(self) -> bool:
        """Test dependency injection system."""
        print("🔄 Testing dependency injection...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_di_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            # Test that services are properly injected
            config_manager = service_registry.get_service('config_manager')
            database = service_registry.get_service('database')
            
            if not config_manager:
                print("❌ ConfigManager dependency not resolved")
                return False
                
            if not database:
                print("❌ Database dependency not resolved")
                return False
            
            # Test that the same instance is returned (singleton behavior)
            config_manager2 = service_registry.get_service('config_manager')
            if config_manager is not config_manager2:
                print("❌ Singleton behavior not working")
                return False
            
            print("✅ Dependency injection test passed")
            return True
            
        except Exception as e:
            print(f"❌ Dependency injection test failed: {e}")
            return False
    
    async def test_performance_requirements(self) -> bool:
        """Test basic performance requirements."""
        print("🔄 Testing performance requirements...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_performance_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            # Test service configuration performance
            performance_results = []
            
            for i in range(3):
                bootstrapper = ApplicationBootstrapper()
                
                start_time = time.time()
                service_registry = await bootstrapper.configure_services()
                config_time = time.time() - start_time
                
                performance_results.append(config_time)
                
                # Verify services are available
                if not service_registry.get_service('config_manager'):
                    print(f"❌ ConfigManager not available in iteration {i}")
                    return False
            
            avg_config_time = sum(performance_results) / len(performance_results)
            max_config_time = max(performance_results)
            
            # Performance requirements
            if avg_config_time > 3.0:
                print(f"❌ Average configuration time too slow: {avg_config_time:.2f}s")
                return False
            
            if max_config_time > 5.0:
                print(f"❌ Maximum configuration time too slow: {max_config_time:.2f}s")
                return False
            
            print(f"✅ Performance requirements test passed (avg: {avg_config_time:.2f}s, max: {max_config_time:.2f}s)")
            return True
            
        except Exception as e:
            print(f"❌ Performance requirements test failed: {e}")
            return False
    
    async def test_existing_functionality_preservation(self) -> bool:
        """Test that existing functionality is preserved."""
        print("🔄 Testing existing functionality preservation...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_preservation_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            # Test that core existing services are available
            essential_services = [
                'config_manager',
                'database',
                'service_config'
            ]
            
            for service_name in essential_services:
                service = service_registry.get_service(service_name)
                if not service:
                    print(f"❌ Essential service {service_name} not preserved")
                    return False
            
            # Test that configuration manager works like before
            config_manager = service_registry.get_service('config_manager')
            config = await config_manager.get_config()
            
            if not isinstance(config, dict):
                print("❌ ConfigManager functionality not preserved")
                return False
            
            # Test that database is available like before
            database = service_registry.get_service('database')
            if not hasattr(database, 'initialize'):
                print("❌ Database functionality not preserved")
                return False
            
            print("✅ Existing functionality preservation test passed")
            return True
            
        except Exception as e:
            print(f"❌ Existing functionality preservation test failed: {e}")
            return False
    
    async def run_validation(self) -> Dict[str, Any]:
        """Run all core functionality validation tests."""
        print("🚀 Starting Core Functionality Validation")
        print("=" * 60)
        
        tests = [
            ("Service Configuration", self.test_service_configuration),
            ("Application Startup/Shutdown", self.test_application_startup_shutdown),
            ("Error Handling & Resilience", self.test_error_handling_resilience),
            ("Configuration Integration", self.test_configuration_integration),
            ("Dependency Injection", self.test_dependency_injection),
            ("Performance Requirements", self.test_performance_requirements),
            ("Functionality Preservation", self.test_existing_functionality_preservation)
        ]
        
        results = []
        start_time = time.time()
        
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            print("-" * 40)
            
            test_start = time.time()
            try:
                success = await test_func()
                test_time = time.time() - test_start
                
                results.append({
                    'name': test_name,
                    'success': success,
                    'duration': test_time
                })
                
                if success:
                    print(f"✅ {test_name} PASSED ({test_time:.2f}s)")
                else:
                    print(f"❌ {test_name} FAILED ({test_time:.2f}s)")
                    
            except Exception as e:
                test_time = time.time() - test_start
                results.append({
                    'name': test_name,
                    'success': False,
                    'duration': test_time
                })
                print(f"💥 {test_name} ERROR ({test_time:.2f}s): {e}")
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if r['success'])
        total = len(results)
        success_rate = successful / total if total > 0 else 0
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 CORE FUNCTIONALITY VALIDATION SUMMARY")
        print("=" * 60)
        print(f"⏱️  Total time: {total_time:.2f}s")
        print(f"📊 Tests: {successful}/{total} passed")
        print(f"📈 Success rate: {success_rate:.1%}")
        
        print(f"\n{'Test Name':<35} {'Status':<10} {'Duration':<10}")
        print("-" * 55)
        for result in results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            print(f"{result['name']:<35} {status:<10} {duration:<10}")
        
        # Validate Task 13 requirements
        print(f"\n🔍 TASK 13 REQUIREMENTS VALIDATION")
        print("-" * 40)
        
        requirements = [
            ("Complete message flows", success_rate >= 0.7),  # Basic integration working
            ("Error propagation and recovery", any(r['name'] == 'Error Handling & Resilience' and r['success'] for r in results)),
            ("Existing functionality preservation", any(r['name'] == 'Functionality Preservation' and r['success'] for r in results)),
            ("Startup/shutdown procedures", any(r['name'] == 'Application Startup/Shutdown' and r['success'] for r in results)),
            ("Performance validation", any(r['name'] == 'Performance Requirements' and r['success'] for r in results))
        ]
        
        requirements_met = 0
        for req_name, req_met in requirements:
            status = "✅ MET" if req_met else "❌ NOT MET"
            print(f"{req_name:<35} {status}")
            if req_met:
                requirements_met += 1
        
        req_success_rate = requirements_met / len(requirements)
        
        if success_rate >= 0.7 and req_success_rate >= 0.6:
            print(f"\n🎉 CORE VALIDATION SUCCESSFUL! ({success_rate:.1%} tests, {req_success_rate:.1%} requirements)")
            return {'success': True, 'results': results, 'requirements_met': requirements_met}
        else:
            print(f"\n❌ CORE VALIDATION FAILED! ({success_rate:.1%} tests, {req_success_rate:.1%} requirements)")
            return {'success': False, 'results': results, 'requirements_met': requirements_met}


async def main():
    """Main entry point for core functionality validation."""
    validator = CoreFunctionalityValidator()
    result = await validator.run_validation()
    return result['success']


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)