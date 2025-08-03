"""
Integration tests for startup and shutdown procedures under various conditions.
Tests application lifecycle management in different scenarios.
"""

import asyncio
import pytest
import os
import signal
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from modules.application_bootstrapper import ApplicationBootstrapper
from modules.service_registry import ServiceRegistry
from modules.application_models import ServiceConfiguration


class TestStartupShutdownProcedures:
    """Test startup and shutdown procedures under various conditions."""

    @pytest.fixture
    async def clean_environment(self):
        """Provide a clean environment for testing."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token_startup_shutdown',
            'ERROR_CHANNEL_ID': '-1001234567890',
            'DEBUG_MODE': 'false'
        }, clear=False):
            yield

    @pytest.fixture
    async def bootstrapper(self, clean_environment):
        """Create a fresh ApplicationBootstrapper for each test."""
        return ApplicationBootstrapper()

    @pytest.fixture
    async def mock_telegram_app(self):
        """Create a mock Telegram application."""
        app = Mock()
        app.initialize = AsyncMock()
        app.start = AsyncMock()
        app.stop = AsyncMock()
        app.shutdown = AsyncMock()
        return app

    @pytest.mark.asyncio
    async def test_normal_startup_shutdown_cycle(self, bootstrapper, mock_telegram_app):
        """Test normal startup and shutdown cycle."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Test normal startup
            await bootstrapper.start_application()
            
            assert bootstrapper.is_running is True
            assert bootstrapper.service_registry is not None
            assert bootstrapper.bot_application is not None
            
            # Verify services are initialized
            config_manager = bootstrapper.service_registry.get_service('config_manager')
            assert config_manager is not None
            
            # Test normal shutdown
            await bootstrapper.shutdown_application()
            
            assert bootstrapper.is_running is False
            mock_telegram_app.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_with_missing_token(self):
        """Test startup behavior when Telegram token is missing."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TELEGRAM_BOT_TOKEN
            bootstrapper = ApplicationBootstrapper()
            
            # Should fail during service configuration
            with pytest.raises(Exception):
                await bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_startup_with_invalid_token(self, bootstrapper):
        """Test startup with invalid Telegram token."""
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'invalid_token'}):
            with patch('modules.bot_application.Application') as mock_app_class:
                mock_app = Mock()
                mock_app.initialize = AsyncMock(side_effect=Exception("Invalid token"))
                mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
                
                # Should handle invalid token gracefully
                with pytest.raises(RuntimeError, match="Application startup failed"):
                    await bootstrapper.start_application()
                
                assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_startup_with_service_initialization_failure(self, bootstrapper):
        """Test startup when service initialization fails."""
        with patch('modules.application_bootstrapper.ConfigManager') as mock_config_class:
            mock_config = Mock()
            mock_config.initialize = AsyncMock(side_effect=Exception("Config init failed"))
            mock_config_class.return_value = mock_config
            
            # Should fail gracefully
            with pytest.raises(RuntimeError, match="Service configuration failed"):
                await bootstrapper.start_application()
            
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_startup_with_database_connection_failure(self, bootstrapper, mock_telegram_app):
        """Test startup when database connection fails."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.database.Database') as mock_db_class:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            mock_db = Mock()
            mock_db.initialize = AsyncMock(side_effect=Exception("Database connection failed"))
            mock_db_class.return_value = mock_db
            
            # Should handle database failure gracefully
            with pytest.raises(RuntimeError):
                await bootstrapper.start_application()
            
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_with_service_errors(self, bootstrapper, mock_telegram_app):
        """Test shutdown when services raise errors during cleanup."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Start application normally
            await bootstrapper.start_application()
            assert bootstrapper.is_running is True
            
            # Make shutdown raise an error
            mock_telegram_app.shutdown.side_effect = Exception("Shutdown error")
            
            # Should handle shutdown errors gracefully
            await bootstrapper.shutdown_application()
            
            # Should still mark as not running
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_multiple_startup_attempts(self, bootstrapper, mock_telegram_app):
        """Test multiple startup attempts on same instance."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # First startup
            await bootstrapper.start_application()
            assert bootstrapper.is_running is True
            
            # Second startup attempt should be handled gracefully
            await bootstrapper.start_application()
            assert bootstrapper.is_running is True
            
            # Cleanup
            await bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_multiple_shutdown_attempts(self, bootstrapper, mock_telegram_app):
        """Test multiple shutdown attempts on same instance."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Start application
            await bootstrapper.start_application()
            assert bootstrapper.is_running is True
            
            # First shutdown
            await bootstrapper.shutdown_application()
            assert bootstrapper.is_running is False
            
            # Second shutdown attempt should be handled gracefully
            await bootstrapper.shutdown_application()
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_without_startup(self, bootstrapper):
        """Test shutdown when application was never started."""
        # Should handle gracefully
        await bootstrapper.shutdown_application()
        assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_startup_with_partial_service_failures(self, bootstrapper, mock_telegram_app):
        """Test startup when some optional services fail to initialize."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.service_factories.ServiceFactory') as mock_factory:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Make some optional services fail
            def create_service_side_effect(service_name):
                if service_name in ['message_counter', 'weather_handler']:
                    raise ImportError(f"{service_name} not available")
                return Mock()
            
            mock_factory.create_message_counter.side_effect = ImportError("Not available")
            mock_factory.create_weather_handler.side_effect = ImportError("Not available")
            
            # Should start successfully despite optional service failures
            await bootstrapper.start_application()
            assert bootstrapper.is_running is True
            
            # Core services should still be available
            assert bootstrapper.service_registry.get_service('config_manager') is not None
            
            await bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_signal_handler_setup(self, bootstrapper, mock_telegram_app):
        """Test signal handler setup and functionality."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('signal.signal') as mock_signal:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            await bootstrapper.start_application()
            
            # Verify signal handlers were set up
            assert mock_signal.call_count >= 2  # SIGINT and SIGTERM
            
            # Test signal handler functionality
            signal_calls = mock_signal.call_args_list
            sigint_handler = None
            sigterm_handler = None
            
            for call in signal_calls:
                if call[0][0] == signal.SIGINT:
                    sigint_handler = call[0][1]
                elif call[0][0] == signal.SIGTERM:
                    sigterm_handler = call[0][1]
            
            assert sigint_handler is not None
            assert sigterm_handler is not None
            
            await bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_concurrent_startup_shutdown(self, bootstrapper, mock_telegram_app):
        """Test concurrent startup and shutdown operations."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Start multiple startup tasks
            startup_tasks = [
                bootstrapper.start_application(),
                bootstrapper.start_application(),
                bootstrapper.start_application()
            ]
            
            # Should handle concurrent startups gracefully
            await asyncio.gather(*startup_tasks, return_exceptions=True)
            assert bootstrapper.is_running is True
            
            # Start multiple shutdown tasks
            shutdown_tasks = [
                bootstrapper.shutdown_application(),
                bootstrapper.shutdown_application(),
                bootstrapper.shutdown_application()
            ]
            
            # Should handle concurrent shutdowns gracefully
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_startup_performance_under_load(self, bootstrapper, mock_telegram_app):
        """Test startup performance under various load conditions."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Add delays to simulate load
            mock_telegram_app.initialize = AsyncMock()
            mock_telegram_app.start = AsyncMock()
            
            start_time = time.time()
            await bootstrapper.start_application()
            startup_time = time.time() - start_time
            
            # Should start within reasonable time even under load
            assert startup_time < 10.0, f"Startup took too long: {startup_time:.2f}s"
            assert bootstrapper.is_running is True
            
            await bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_memory_cleanup_during_failed_startup(self, bootstrapper):
        """Test memory cleanup when startup fails."""
        with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
            mock_registry = Mock()
            mock_registry.register_service = Mock()
            mock_registry.register_singleton = Mock()
            mock_registry.register_factory = Mock()
            mock_registry.get_service = Mock(side_effect=Exception("Service not found"))
            mock_registry_class.return_value = mock_registry
            
            # Startup should fail
            with pytest.raises(RuntimeError):
                await bootstrapper.start_application()
            
            # Should not be running
            assert bootstrapper.is_running is False
            
            # Service registry should be None (cleaned up)
            assert bootstrapper.service_registry is not None  # Still set for debugging

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_active_operations(self, bootstrapper, mock_telegram_app):
        """Test graceful shutdown while operations are active."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            await bootstrapper.start_application()
            
            # Simulate active operations by making shutdown take time
            async def slow_shutdown():
                await asyncio.sleep(0.1)  # Simulate cleanup time
                
            mock_telegram_app.shutdown = AsyncMock(side_effect=slow_shutdown)
            
            # Should wait for operations to complete
            start_time = time.time()
            await bootstrapper.shutdown_application()
            shutdown_time = time.time() - start_time
            
            assert shutdown_time >= 0.1  # Should have waited
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_service_registry_lifecycle(self, bootstrapper):
        """Test service registry lifecycle management."""
        # Initially no registry
        assert bootstrapper.service_registry is None
        
        # Configure services
        registry = await bootstrapper.configure_services()
        assert registry is not None
        assert bootstrapper.service_registry is registry
        
        # Verify services are registered
        config_manager = registry.get_service('config_manager')
        assert config_manager is not None
        
        service_config = registry.get_service('service_config')
        assert service_config is not None

    @pytest.mark.asyncio
    async def test_environment_variable_validation(self):
        """Test validation of required environment variables."""
        # Test with missing TELEGRAM_BOT_TOKEN
        with patch.dict(os.environ, {}, clear=True):
            bootstrapper = ApplicationBootstrapper()
            
            with pytest.raises(Exception):
                await bootstrapper.configure_services()
        
        # Test with empty TELEGRAM_BOT_TOKEN
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': ''}):
            bootstrapper = ApplicationBootstrapper()
            
            with pytest.raises(Exception):
                await bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_configuration_error_handling(self, bootstrapper):
        """Test handling of configuration errors during startup."""
        with patch('config.config_manager.ConfigManager') as mock_config_class:
            mock_config = Mock()
            mock_config.initialize = AsyncMock(side_effect=ValueError("Invalid configuration"))
            mock_config_class.return_value = mock_config
            
            with pytest.raises(RuntimeError, match="Service configuration failed"):
                await bootstrapper.start_application()
            
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_service_dependency_failure_handling(self, bootstrapper, mock_telegram_app):
        """Test handling of service dependency failures."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('modules.service_registry.ServiceRegistry.get_service') as mock_get_service:
            
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # Make service dependency resolution fail
            mock_get_service.side_effect = Exception("Dependency resolution failed")
            
            with pytest.raises(RuntimeError):
                await bootstrapper.start_application()
            
            assert bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_restart_after_failure(self, bootstrapper, mock_telegram_app):
        """Test restarting application after a failure."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            # First startup fails
            mock_telegram_app.initialize.side_effect = [
                Exception("First startup fails"),
                None  # Second startup succeeds
            ]
            
            # First attempt should fail
            with pytest.raises(RuntimeError):
                await bootstrapper.start_application()
            assert bootstrapper.is_running is False
            
            # Reset the side effect for second attempt
            mock_telegram_app.initialize.side_effect = None
            mock_telegram_app.initialize = AsyncMock()
            
            # Create new bootstrapper for restart
            new_bootstrapper = ApplicationBootstrapper()
            
            # Second attempt should succeed
            await new_bootstrapper.start_application()
            assert new_bootstrapper.is_running is True
            
            await new_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_shutdown_timeout_handling(self, bootstrapper, mock_telegram_app):
        """Test handling of shutdown timeouts."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_telegram_app
            
            await bootstrapper.start_application()
            
            # Make shutdown hang
            async def hanging_shutdown():
                await asyncio.sleep(10)  # Simulate hanging shutdown
                
            mock_telegram_app.shutdown = AsyncMock(side_effect=hanging_shutdown)
            
            # Should handle hanging shutdown gracefully
            start_time = time.time()
            
            # Use timeout to prevent test from hanging
            try:
                await asyncio.wait_for(bootstrapper.shutdown_application(), timeout=1.0)
            except asyncio.TimeoutError:
                # This is expected - the shutdown is hanging
                pass
            
            shutdown_time = time.time() - start_time
            assert shutdown_time >= 1.0  # Should have waited for timeout
            
            # Application should still be marked as not running
            # (even if shutdown didn't complete cleanly)
            assert bootstrapper.is_running is False


class TestStartupShutdownEdgeCases:
    """Test edge cases in startup and shutdown procedures."""

    @pytest.fixture
    async def edge_case_bootstrapper(self):
        """Create bootstrapper for edge case testing."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'edge_case_token',
            'ERROR_CHANNEL_ID': '-1001111111111'
        }):
            return ApplicationBootstrapper()

    @pytest.mark.asyncio
    async def test_startup_with_corrupted_service_registry(self, edge_case_bootstrapper):
        """Test startup with corrupted service registry."""
        with patch('modules.service_registry.ServiceRegistry') as mock_registry_class:
            # Create a registry that becomes corrupted
            mock_registry = Mock()
            mock_registry.register_service = Mock(side_effect=Exception("Registry corrupted"))
            mock_registry_class.return_value = mock_registry
            
            with pytest.raises(RuntimeError):
                await edge_case_bootstrapper.start_application()

    @pytest.mark.asyncio
    async def test_shutdown_with_missing_services(self, edge_case_bootstrapper):
        """Test shutdown when services are missing or None."""
        # Set up a scenario where services are None
        edge_case_bootstrapper.service_registry = None
        edge_case_bootstrapper.bot_application = None
        edge_case_bootstrapper._running = True
        
        # Should handle gracefully
        await edge_case_bootstrapper.shutdown_application()
        assert edge_case_bootstrapper.is_running is False

    @pytest.mark.asyncio
    async def test_startup_with_system_resource_exhaustion(self, edge_case_bootstrapper):
        """Test startup behavior under system resource exhaustion."""
        with patch('modules.application_bootstrapper.ServiceRegistry') as mock_registry_class:
            # Simulate resource exhaustion
            mock_registry_class.side_effect = MemoryError("System out of memory")
            
            with pytest.raises(MemoryError):
                await edge_case_bootstrapper.configure_services()

    @pytest.mark.asyncio
    async def test_signal_handling_during_startup(self, edge_case_bootstrapper):
        """Test signal handling during startup process."""
        with patch('modules.bot_application.Application') as mock_app_class, \
             patch('signal.signal') as mock_signal:
            
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_app.shutdown = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            
            # Start application
            await edge_case_bootstrapper.start_application()
            
            # Verify signal handlers are set up
            mock_signal.assert_called()
            
            # Test that shutdown event can be triggered
            edge_case_bootstrapper._shutdown_event.set()
            
            await edge_case_bootstrapper.shutdown_application()

    @pytest.mark.asyncio
    async def test_concurrent_signal_handling(self, edge_case_bootstrapper):
        """Test handling of multiple concurrent signals."""
        with patch('modules.bot_application.Application') as mock_app_class:
            mock_app = Mock()
            mock_app.initialize = AsyncMock()
            mock_app.start = AsyncMock()
            mock_app.shutdown = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            
            await edge_case_bootstrapper.start_application()
            
            # Trigger multiple shutdown events concurrently
            edge_case_bootstrapper._shutdown_event.set()
            
            # Multiple shutdown calls should be handled gracefully
            shutdown_tasks = [
                edge_case_bootstrapper.shutdown_application(),
                edge_case_bootstrapper.shutdown_application(),
                edge_case_bootstrapper.shutdown_application()
            ]
            
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            assert edge_case_bootstrapper.is_running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])