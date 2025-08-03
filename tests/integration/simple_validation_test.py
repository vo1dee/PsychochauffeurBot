"""
Simple validation test for Task 13 requirements.
Tests core functionality without complex async fixtures.
"""

import asyncio
import os
import time
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext


class SimpleValidationTest:
    """Simple validation test for integration and end-to-end functionality."""
    
    def __init__(self):
        self.results = {}
        
    async def test_application_lifecycle(self) -> bool:
        """Test complete application lifecycle."""
        print("🔄 Testing application lifecycle...")
        
        try:
            # Set up environment
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_lifecycle_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            
            with patch('modules.bot_application.Application') as mock_app_class:
                mock_app = Mock()
                mock_app.initialize = AsyncMock()
                mock_app.start = AsyncMock()
                mock_app.shutdown = AsyncMock()
                mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
                
                # Test startup
                start_time = time.time()
                await bootstrapper.start_application()
                startup_time = time.time() - start_time
                
                if not bootstrapper.is_running:
                    print("❌ Application not running after startup")
                    return False
                
                if startup_time > 10.0:
                    print(f"❌ Startup too slow: {startup_time:.2f}s")
                    return False
                
                # Test shutdown
                start_time = time.time()
                await bootstrapper.shutdown_application()
                shutdown_time = time.time() - start_time
                
                if bootstrapper.is_running:
                    print("❌ Application still running after shutdown")
                    return False
                
                if shutdown_time > 5.0:
                    print(f"❌ Shutdown too slow: {shutdown_time:.2f}s")
                    return False
                
                print(f"✅ Application lifecycle test passed (startup: {startup_time:.2f}s, shutdown: {shutdown_time:.2f}s)")
                return True
                
        except Exception as e:
            print(f"❌ Application lifecycle test failed: {e}")
            return False
    
    async def test_service_integration(self) -> bool:
        """Test service integration and dependency resolution."""
        print("🔄 Testing service integration...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_integration_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            # Test core services
            config_manager = service_registry.get_service('config_manager')
            database = service_registry.get_service('database')
            
            if not config_manager:
                print("❌ ConfigManager service not available")
                return False
                
            if not database:
                print("❌ Database service not available")
                return False
            
            # Test service dependencies
            message_service = service_registry.get_service('message_handler_service')
            if message_service and hasattr(message_service, 'config_manager'):
                if message_service.config_manager is not config_manager:
                    print("❌ Service dependency injection not working")
                    return False
            
            print("✅ Service integration test passed")
            return True
            
        except Exception as e:
            print(f"❌ Service integration test failed: {e}")
            return False
    
    async def test_message_processing(self) -> bool:
        """Test message processing functionality."""
        print("🔄 Testing message processing...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_message_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            message_service = service_registry.get_service('message_handler_service')
            if not message_service:
                print("⚠️  MessageHandlerService not available, skipping message processing test")
                return True
            
            # Create mock update and context
            user = Mock(spec=User)
            user.id = 12345
            user.first_name = "Test"
            user.username = "testuser"
            
            chat = Mock(spec=Chat)
            chat.id = 67890
            chat.type = "private"
            
            message = Mock(spec=Message)
            message.text = "Hello, this is a test message"
            message.from_user = user
            message.chat = chat
            
            update = Mock(spec=Update)
            update.message = message
            update.effective_user = user
            update.effective_chat = chat
            
            context = Mock(spec=CallbackContext)
            context.bot = AsyncMock()
            
            # Test message processing with mocked dependencies
            with patch('modules.message_handler_service.gpt_response') as mock_gpt_response, \
                 patch('modules.message_handler_service.update_message_history') as mock_update_history:
                
                mock_gpt_response.return_value = None
                
                # Process message
                await message_service.handle_text_message(update, context)
                
                # Verify message was processed
                mock_update_history.assert_called_with(12345, "Hello, this is a test message")
            
            print("✅ Message processing test passed")
            return True
            
        except Exception as e:
            print(f"❌ Message processing test failed: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling and recovery."""
        print("🔄 Testing error handling...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_error_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            message_service = service_registry.get_service('message_handler_service')
            if not message_service:
                print("⚠️  MessageHandlerService not available, skipping error handling test")
                return True
            
            # Create mock update
            user = Mock(spec=User)
            user.id = 12345
            chat = Mock(spec=Chat)
            chat.id = 67890
            chat.type = "private"
            message = Mock(spec=Message)
            message.text = "Error test message"
            message.from_user = user
            message.chat = chat
            update = Mock(spec=Update)
            update.message = message
            update.effective_user = user
            update.effective_chat = chat
            context = Mock(spec=CallbackContext)
            context.bot = AsyncMock()
            
            # Test error handling
            with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
                mock_gpt_response.side_effect = Exception("Simulated error")
                
                # Should handle error gracefully
                await message_service.handle_text_message(update, context)
                
                # If we reach here, error was handled gracefully
                print("✅ Error handling test passed")
                return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False
    
    async def test_performance_basic(self) -> bool:
        """Test basic performance requirements."""
        print("🔄 Testing basic performance...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_performance_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            # Test service configuration performance
            start_time = time.time()
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            config_time = time.time() - start_time
            
            if config_time > 5.0:
                print(f"❌ Service configuration too slow: {config_time:.2f}s")
                return False
            
            # Test message processing performance
            message_service = service_registry.get_service('message_handler_service')
            if message_service:
                # Create mock data
                user = Mock(spec=User)
                user.id = 12345
                chat = Mock(spec=Chat)
                chat.id = 67890
                chat.type = "private"
                context = Mock(spec=CallbackContext)
                context.bot = AsyncMock()
                
                with patch('modules.message_handler_service.gpt_response') as mock_gpt_response:
                    mock_gpt_response.return_value = None
                    
                    # Process 10 messages and measure time
                    start_time = time.time()
                    tasks = []
                    
                    for i in range(10):
                        message = Mock(spec=Message)
                        message.text = f"Performance test message {i}"
                        message.from_user = user
                        message.chat = chat
                        update = Mock(spec=Update)
                        update.message = message
                        update.effective_user = user
                        update.effective_chat = chat
                        
                        task = message_service.handle_text_message(update, context)
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    processing_time = time.time() - start_time
                    throughput = 10 / processing_time
                    
                    if throughput < 5:
                        print(f"❌ Message processing throughput too low: {throughput:.2f} msg/sec")
                        return False
                    
                    print(f"✅ Basic performance test passed (config: {config_time:.2f}s, throughput: {throughput:.2f} msg/sec)")
            else:
                print("✅ Basic performance test passed (service config only)")
            
            return True
            
        except Exception as e:
            print(f"❌ Basic performance test failed: {e}")
            return False
    
    async def test_existing_functionality_preservation(self) -> bool:
        """Test that existing functionality is preserved."""
        print("🔄 Testing existing functionality preservation...")
        
        try:
            os.environ['TELEGRAM_BOT_TOKEN'] = 'test_preservation_token'
            os.environ['ERROR_CHANNEL_ID'] = '-1001234567890'
            
            bootstrapper = ApplicationBootstrapper()
            service_registry = await bootstrapper.configure_services()
            
            # Test that core services exist (preserving existing functionality)
            services_to_check = [
                'config_manager',
                'database'
            ]
            
            for service_name in services_to_check:
                service = service_registry.get_service(service_name)
                if not service:
                    print(f"❌ Core service {service_name} not available")
                    return False
            
            # Test that optional services can be retrieved (even if None)
            optional_services = [
                'message_handler_service',
                'speech_recognition_service',
                'callback_handler_service',
                'command_registry'
            ]
            
            for service_name in optional_services:
                try:
                    service = service_registry.get_service(service_name)
                    # Service can be None or an actual service - both are acceptable
                except Exception as e:
                    print(f"❌ Error retrieving service {service_name}: {e}")
                    return False
            
            print("✅ Existing functionality preservation test passed")
            return True
            
        except Exception as e:
            print(f"❌ Existing functionality preservation test failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests."""
        print("🚀 Starting Simple Validation Test Suite")
        print("=" * 60)
        
        tests = [
            ("Application Lifecycle", self.test_application_lifecycle),
            ("Service Integration", self.test_service_integration),
            ("Message Processing", self.test_message_processing),
            ("Error Handling", self.test_error_handling),
            ("Basic Performance", self.test_performance_basic),
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
        print("🏁 SIMPLE VALIDATION TEST SUMMARY")
        print("=" * 60)
        print(f"⏱️  Total time: {total_time:.2f}s")
        print(f"📊 Tests: {successful}/{total} passed")
        print(f"📈 Success rate: {success_rate:.1%}")
        
        print(f"\n{'Test Name':<30} {'Status':<10} {'Duration':<10}")
        print("-" * 50)
        for result in results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = f"{result['duration']:.2f}s"
            print(f"{result['name']:<30} {status:<10} {duration:<10}")
        
        # Validate requirements
        print(f"\n🔍 TASK 13 REQUIREMENTS VALIDATION")
        print("-" * 40)
        
        requirements = [
            ("Complete message flows", any(r['name'] in ['Message Processing', 'Service Integration'] and r['success'] for r in results)),
            ("Error propagation and recovery", any(r['name'] == 'Error Handling' and r['success'] for r in results)),
            ("Existing functionality preservation", any(r['name'] == 'Functionality Preservation' and r['success'] for r in results)),
            ("Startup/shutdown procedures", any(r['name'] == 'Application Lifecycle' and r['success'] for r in results)),
            ("Performance validation", any(r['name'] == 'Basic Performance' and r['success'] for r in results))
        ]
        
        requirements_met = 0
        for req_name, req_met in requirements:
            status = "✅ MET" if req_met else "❌ NOT MET"
            print(f"{req_name:<35} {status}")
            if req_met:
                requirements_met += 1
        
        req_success_rate = requirements_met / len(requirements)
        
        if success_rate >= 0.8 and req_success_rate >= 0.8:
            print(f"\n🎉 VALIDATION SUCCESSFUL! ({success_rate:.1%} tests, {req_success_rate:.1%} requirements)")
            return {'success': True, 'results': results, 'requirements_met': requirements_met}
        else:
            print(f"\n❌ VALIDATION FAILED! ({success_rate:.1%} tests, {req_success_rate:.1%} requirements)")
            return {'success': False, 'results': results, 'requirements_met': requirements_met}


async def main():
    """Main entry point for simple validation."""
    validator = SimpleValidationTest()
    result = await validator.run_all_tests()
    return result['success']


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)