"""Tests for the main module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import signal
import sys

import main


class TestMainUtilities:
    """Test utility functions in main module."""

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
    @patch('main.ApplicationBootstrapper')
    @patch('main.error_logger')
    @pytest.mark.asyncio
    async def test_main_with_token_creates_bootstrapper(self, mock_error_logger, mock_bootstrapper_class, mock_config):
        """Test that main function creates ApplicationBootstrapper when token is present."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the ApplicationBootstrapper
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        mock_bootstrapper.start_application = AsyncMock()
        mock_bootstrapper.shutdown_application = AsyncMock()
        
        await main.main()
        
        # Verify bootstrapper was created and started
        mock_bootstrapper_class.assert_called_once()
        mock_bootstrapper.start_application.assert_called_once()
        mock_bootstrapper.shutdown_application.assert_called_once()

    @patch('main.Config')
    @patch('main.ApplicationBootstrapper')
    @patch('main.error_logger')
    @pytest.mark.asyncio
    async def test_main_handles_keyboard_interrupt(self, mock_error_logger, mock_bootstrapper_class, mock_config):
        """Test that main function handles KeyboardInterrupt properly."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the ApplicationBootstrapper to raise KeyboardInterrupt
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        mock_bootstrapper.start_application.side_effect = KeyboardInterrupt()
        mock_bootstrapper.shutdown_application = AsyncMock()
        
        await main.main()
        
        # Verify shutdown was still called
        mock_bootstrapper.shutdown_application.assert_called_once()

    @patch('main.Config')
    @patch('main.ApplicationBootstrapper')
    @patch('main.error_logger')
    @pytest.mark.asyncio
    async def test_main_handles_exception(self, mock_error_logger, mock_bootstrapper_class, mock_config):
        """Test that main function handles exceptions properly."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the ApplicationBootstrapper to raise an exception
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        test_exception = RuntimeError("Test error")
        mock_bootstrapper.start_application.side_effect = test_exception
        mock_bootstrapper.shutdown_application = AsyncMock()
        
        with pytest.raises(RuntimeError):
            await main.main()
        
        # Verify error was logged and shutdown was called
        mock_error_logger.error.assert_called_once()
        mock_bootstrapper.shutdown_application.assert_called_once()

    @patch('main.asyncio.run')
    @patch('main.logger')
    def test_run_bot_success(self, mock_logger, mock_asyncio_run):
        """Test that run_bot executes successfully."""
        mock_asyncio_run.return_value = None
        
        main.run_bot()
        
        # Verify asyncio.run was called with main
        mock_asyncio_run.assert_called_once()

    @patch('main.asyncio.run')
    @patch('main.logger')
    @patch('main.error_logger')
    def test_run_bot_handles_keyboard_interrupt(self, mock_error_logger, mock_logger, mock_asyncio_run):
        """Test that run_bot handles KeyboardInterrupt."""
        mock_asyncio_run.side_effect = KeyboardInterrupt()
        
        main.run_bot()
        
        # Verify the interrupt was logged and run finished was called
        mock_logger.info.assert_any_call("Bot stopped by user or system signal")
        mock_logger.info.assert_called_with("Bot run finished")

    @patch('main.asyncio.run')
    @patch('main.logger')
    @patch('main.error_logger')
    def test_run_bot_handles_exception(self, mock_error_logger, mock_logger, mock_asyncio_run):
        """Test that run_bot handles exceptions."""
        test_exception = RuntimeError("Test error")
        mock_asyncio_run.side_effect = test_exception
        
        with pytest.raises(SystemExit):
            main.run_bot()
        
        # Verify the error was logged
        mock_error_logger.error.assert_called_once()


class TestMainIntegration:
    """Test integration aspects of main module."""

    @patch('main.Config')
    @patch('main.ApplicationBootstrapper')
    @pytest.mark.asyncio
    async def test_main_integration_flow(self, mock_bootstrapper_class, mock_config):
        """Test the main integration flow."""
        mock_config.TELEGRAM_BOT_TOKEN = "test_token"
        
        # Mock the ApplicationBootstrapper
        mock_bootstrapper = AsyncMock()
        mock_bootstrapper_class.return_value = mock_bootstrapper
        mock_bootstrapper.start_application = AsyncMock()
        mock_bootstrapper.shutdown_application = AsyncMock()
        
        await main.main()
        
        # Verify the complete flow
        mock_bootstrapper_class.assert_called_once()
        mock_bootstrapper.start_application.assert_called_once()
        mock_bootstrapper.shutdown_application.assert_called_once()