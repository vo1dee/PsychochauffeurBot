"""Tests for the main module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import signal
import sys

import main


class TestMainUtilities:
    """Test utility functions in main module."""

    @patch('main.general_logger')
    def test_handle_shutdown_signal(self, mock_logger):
        """Test shutdown signal handling."""
        with pytest.raises(SystemExit) as exc_info:
            main.handle_shutdown_signal(signal.SIGTERM, None)
        
        assert str(exc_info.value) == "Shutdown signal received."
        mock_logger.info.assert_called_once_with(
            f"Received signal {signal.SIGTERM}, initiating graceful shutdown..."
        )

    @patch('main.general_logger')
    def test_handle_shutdown_signal_sigint(self, mock_logger):
        """Test shutdown signal handling with SIGINT."""
        with pytest.raises(SystemExit) as exc_info:
            main.handle_shutdown_signal(signal.SIGINT, None)
        
        assert str(exc_info.value) == "Shutdown signal received."
        mock_logger.info.assert_called_once_with(
            f"Received signal {signal.SIGINT}, initiating graceful shutdown..."
        )

    @patch('main.Config')
    @patch('main.error_logger')
    @pytest.mark.asyncio
    async def test_main_no_token(self, mock_error_logger, mock_config):
        """Test main function when no token is provided."""
        mock_config.TELEGRAM_BOT_TOKEN = None
        
        await main.main()
        
        mock_error_logger.critical.assert_called_once_with(
            "TELEGRAM_BOT_TOKEN is not set. The bot cannot start."
        )

    @patch('main.Config')
    @patch('main.init_directories')
    @patch('main.error_logger')
    @pytest.mark.asyncio
    async def test_main_with_token_calls_init(self, mock_error_logger, mock_init_dirs, mock_config):
        """Test that main function calls init_directories when token is present."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the ApplicationBuilder to avoid actual bot creation
        with patch('main.ApplicationBuilder') as mock_builder:
            mock_app = AsyncMock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            mock_app.run_polling = AsyncMock()
            
            # This will fail at some point but we just want to test the init call
            try:
                await main.main()
            except Exception:
                pass  # Expected to fail due to mocking
            
            mock_init_dirs.assert_called_once()

    @patch('main.main')
    @patch('main.signal.signal')
    @patch('main.nest_asyncio.apply')
    @patch('main.asyncio.run')
    def test_run_bot_signal_registration(self, mock_asyncio_run, mock_nest_asyncio, mock_signal, mock_main_func):
        """Test that run_bot registers signal handlers."""
        # Mock the main function to return a simple coroutine
        mock_main_func.return_value = AsyncMock()
        mock_asyncio_run.return_value = None
        
        main.run_bot()
        
        # Verify signal handlers are registered
        mock_signal.assert_any_call(signal.SIGINT, main.handle_shutdown_signal)
        mock_signal.assert_any_call(signal.SIGTERM, main.handle_shutdown_signal)
        
        # nest_asyncio is not called in run_bot function
        mock_nest_asyncio.assert_not_called()
        
        # Verify asyncio.run is called
        mock_asyncio_run.assert_called_once()


class TestMainIntegration:
    """Test integration aspects of main module."""

    @patch('main.register_handlers')
    @patch('main.Config')
    @patch('main.init_directories')
    @patch('main.ApplicationBuilder')
    @pytest.mark.asyncio
    async def test_main_integration_flow(self, mock_builder, mock_init_dirs, mock_config, mock_register):
        """Test the main integration flow."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the application builder chain
        mock_app = AsyncMock()
        mock_builder_instance = Mock()
        mock_builder.return_value = mock_builder_instance
        mock_builder_instance.token.return_value = mock_builder_instance
        mock_builder_instance.build.return_value = mock_app
        mock_app.run_polling = AsyncMock()
        
        # Mock other dependencies
        with patch('main.ConfigManager') as mock_config_manager, \
             patch('main.ReminderManager') as mock_reminder_manager, \
             patch('main.init_telegram_error_handler') as mock_init_error:
            
            mock_config_manager_instance = AsyncMock()
            mock_config_manager.return_value = mock_config_manager_instance
            
            mock_reminder_manager_instance = AsyncMock()
            mock_reminder_manager.return_value = mock_reminder_manager_instance
            
            try:
                await main.main()
            except Exception:
                pass  # Expected to fail due to incomplete mocking
            
            # Verify initialization steps
            mock_init_dirs.assert_called_once()
            mock_builder.assert_called_once()
            mock_builder_instance.token.assert_called_once_with("test_token")