"""
Unit tests for the BotApplication orchestrator.
"""

import pytest
import asyncio
import signal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Bot
from telegram.ext import Application

from modules.bot_application import BotApplication
from modules.service_registry import ServiceRegistry
from modules.const import Config


class TestBotApplication:
    """Test cases for BotApplication."""
    
    @pytest.fixture
    def mock_service_registry(self):
        """Create a mock service registry."""
        registry = Mock(spec=ServiceRegistry)
        registry.register_instance = Mock(return_value=registry)
        registry.initialize_services = AsyncMock()
        registry.shutdown_services = AsyncMock()
        registry.get_service = Mock()
        return registry
    
    @pytest.fixture
    def mock_telegram_app(self):
        """Create a mock Telegram application."""
        app = Mock(spec=Application)
        app.bot = Mock(spec=Bot)
        app.bot.send_message = AsyncMock()
        app.run_polling = AsyncMock()
        app.stop = AsyncMock()
        return app
    
    @pytest.fixture
    def bot_app(self, mock_service_registry):
        """Create a BotApplication instance."""
        return BotApplication(mock_service_registry)
    
    @pytest.mark.asyncio
    async def test_initialization_success(self, bot_app, mock_service_registry):
        """Test successful bot application initialization."""
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock(spec=Application)
            mock_app.bot = Mock(spec=Bot)
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            # Mock handler registry
            mock_handler_registry = Mock()
            mock_handler_registry.register_all_handlers = AsyncMock()
            mock_service_registry.get_service.return_value = mock_handler_registry
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                await bot_app.initialize()
            
            # Verify initialization steps
            assert bot_app.telegram_app is mock_app
            assert bot_app.bot is mock_app.bot
            mock_service_registry.register_instance.assert_any_call('telegram_bot', mock_app.bot)
            mock_service_registry.register_instance.assert_any_call('telegram_app', mock_app)
            mock_service_registry.initialize_services.assert_called_once()
            mock_handler_registry.register_all_handlers.assert_called_once_with(mock_app)
    
    @pytest.mark.asyncio
    async def test_initialization_missing_token(self, bot_app):
        """Test initialization failure when token is missing."""
        with patch.object(Config, 'TELEGRAM_BOT_TOKEN', ''):
            with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN is not set"):
                await bot_app.initialize()
    
    @pytest.mark.asyncio
    async def test_initialization_service_failure(self, bot_app, mock_service_registry):
        """Test initialization failure when service initialization fails."""
        mock_service_registry.initialize_services.side_effect = RuntimeError("Service init failed")
        
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock(spec=Application)
            mock_app.bot = Mock(spec=Bot)
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                with pytest.raises(RuntimeError, match="Service init failed"):
                    await bot_app.initialize()
    
    @pytest.mark.asyncio
    async def test_start_success(self, bot_app, mock_service_registry):
        """Test successful bot application start."""
        # Setup initialized bot
        mock_app = Mock(spec=Application)
        mock_app.bot = Mock(spec=Bot)
        mock_app.bot.send_message = AsyncMock()
        mock_app.run_polling = AsyncMock()
        bot_app.telegram_app = mock_app
        bot_app.bot = mock_app.bot
        
        with patch.object(bot_app, '_send_startup_notification', new_callable=AsyncMock) as mock_startup:
            with patch.object(bot_app, '_setup_signal_handlers') as mock_signals:
                await bot_app.start()
                
                mock_startup.assert_called_once()
                mock_signals.assert_called_once()
                mock_app.run_polling.assert_called_once()
                assert bot_app.is_running is False  # Set to False after run_polling completes
    
    @pytest.mark.asyncio
    async def test_start_already_running(self, bot_app):
        """Test starting bot when already running."""
        bot_app._running = True
        
        with patch('modules.bot_application.logger') as mock_logger:
            await bot_app.start()
            mock_logger.warning.assert_called_with("Bot Application is already running")
    
    @pytest.mark.asyncio
    async def test_start_polling_failure(self, bot_app):
        """Test start failure during polling."""
        mock_app = Mock(spec=Application)
        mock_app.run_polling = Mock(side_effect=RuntimeError("Polling failed"))
        bot_app.telegram_app = mock_app
        bot_app.bot = Mock()
        
        with patch.object(bot_app, '_send_startup_notification', new_callable=AsyncMock):
            with patch.object(bot_app, '_setup_signal_handlers'):
                with pytest.raises(RuntimeError, match="Polling failed"):
                    await bot_app.start()
                
                assert bot_app.is_running is False
    
    @pytest.mark.asyncio
    async def test_shutdown_success(self, bot_app, mock_service_registry):
        """Test successful bot application shutdown."""
        # Setup running bot
        mock_app = Mock(spec=Application)
        mock_app.stop = AsyncMock()
        bot_app.telegram_app = mock_app
        bot_app.bot = Mock()
        bot_app._running = True
        
        with patch.object(bot_app, '_send_shutdown_notification', new_callable=AsyncMock) as mock_shutdown:
            await bot_app.shutdown()
            
            mock_app.stop.assert_called_once()
            mock_service_registry.shutdown_services.assert_called_once()
            mock_shutdown.assert_called_once()
            assert bot_app.is_running is False
    
    @pytest.mark.asyncio
    async def test_shutdown_not_running(self, bot_app):
        """Test shutdown when bot is not running."""
        bot_app._running = False
        
        with patch('modules.bot_application.logger') as mock_logger:
            await bot_app.shutdown()
            mock_logger.info.assert_called_with("Bot Application is not running")
    
    @pytest.mark.asyncio
    async def test_shutdown_with_error(self, bot_app, mock_service_registry):
        """Test shutdown with error during process."""
        mock_service_registry.shutdown_services.side_effect = RuntimeError("Shutdown error")
        bot_app._running = True
        bot_app.telegram_app = Mock()
        bot_app.telegram_app.stop = AsyncMock()
        bot_app.bot = Mock()
        
        with patch('modules.bot_application.logger') as mock_logger:
            with patch.object(bot_app, '_send_shutdown_notification', new_callable=AsyncMock):
                await bot_app.shutdown()
                
                mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_send_startup_notification_success(self, bot_app):
        """Test successful startup notification."""
        mock_bot = Mock()
        mock_bot.send_message = AsyncMock()
        bot_app.bot = mock_bot
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', '-123456'):
            await bot_app._send_startup_notification()
            
            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == '-123456'
            assert 'Bot Started Successfully' in call_args[1]['text']
            assert call_args[1]['parse_mode'] == 'MarkdownV2'
    
    @pytest.mark.asyncio
    async def test_send_startup_notification_with_topic(self, bot_app):
        """Test startup notification with topic ID."""
        mock_bot = Mock()
        mock_bot.send_message = AsyncMock()
        bot_app.bot = mock_bot
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', '-123456:789'):
            await bot_app._send_startup_notification()
            
            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == '-123456'
            assert call_args[1]['message_thread_id'] == 789
    
    @pytest.mark.asyncio
    async def test_send_startup_notification_no_channel(self, bot_app):
        """Test startup notification when no error channel is configured."""
        bot_app.bot = Mock()
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', ''):
            await bot_app._send_startup_notification()
            # Should not raise any exceptions
    
    @pytest.mark.asyncio
    async def test_send_startup_notification_error(self, bot_app):
        """Test startup notification with send error."""
        mock_bot = Mock()
        mock_bot.send_message = AsyncMock(side_effect=RuntimeError("Send failed"))
        bot_app.bot = mock_bot
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', '-123456'):
            with patch('modules.bot_application.logger') as mock_logger:
                await bot_app._send_startup_notification()
                mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_send_shutdown_notification_success(self, bot_app):
        """Test successful shutdown notification."""
        mock_bot = Mock()
        mock_bot.send_message = AsyncMock()
        bot_app.bot = mock_bot
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', '-123456'):
            await bot_app._send_shutdown_notification()
            
            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == '-123456'
            assert 'Bot Shutdown' in call_args[1]['text']
    
    @pytest.mark.asyncio
    async def test_send_shutdown_notification_no_bot(self, bot_app):
        """Test shutdown notification when bot is None."""
        bot_app.bot = None
        
        with patch.object(Config, 'ERROR_CHANNEL_ID', '-123456'):
            await bot_app._send_shutdown_notification()
            # Should not raise any exceptions
    
    def test_setup_signal_handlers(self, bot_app):
        """Test signal handler setup."""
        with patch('signal.signal') as mock_signal:
            bot_app._setup_signal_handlers()
            
            # Verify signal handlers were registered
            assert mock_signal.call_count == 2
            mock_signal.assert_any_call(signal.SIGINT, mock_signal.call_args_list[0][0][1])
            mock_signal.assert_any_call(signal.SIGTERM, mock_signal.call_args_list[1][0][1])
    
    def test_signal_handler_functionality(self, bot_app):
        """Test signal handler functionality."""
        # Setup signal handler
        bot_app._setup_signal_handlers()
        
        # Simulate signal
        with patch('modules.bot_application.logger') as mock_logger:
            # Get the signal handler function
            with patch('signal.signal') as mock_signal:
                bot_app._setup_signal_handlers()
                signal_handler = mock_signal.call_args_list[0][0][1]
                
                # Call the signal handler
                signal_handler(signal.SIGINT, None)
                
                # Verify shutdown event is set
                assert bot_app._shutdown_event.is_set()
                mock_logger.info.assert_called()
    
    def test_is_running_property(self, bot_app):
        """Test is_running property."""
        assert bot_app.is_running is False
        
        bot_app._running = True
        assert bot_app.is_running is True
        
        bot_app._running = False
        assert bot_app.is_running is False
    
    @pytest.mark.asyncio
    async def test_register_handlers(self, bot_app, mock_service_registry):
        """Test handler registration."""
        mock_handler_registry = Mock()
        mock_handler_registry.register_all_handlers = AsyncMock()
        mock_service_registry.get_service.return_value = mock_handler_registry
        
        mock_app = Mock()
        bot_app.telegram_app = mock_app
        
        await bot_app._register_handlers()
        
        mock_service_registry.get_service.assert_called_once_with('handler_registry')
        mock_handler_registry.register_all_handlers.assert_called_once_with(mock_app)


class TestBotApplicationIntegration:
    """Integration tests for BotApplication."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle_simulation(self):
        """Test complete bot lifecycle simulation."""
        # Create real service registry
        service_registry = ServiceRegistry()
        
        # Mock handler registry service
        mock_handler_registry = Mock()
        mock_handler_registry.register_all_handlers = AsyncMock()
        service_registry.register_instance('handler_registry', mock_handler_registry)
        
        bot_app = BotApplication(service_registry)
        
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock(spec=Application)
            mock_app.bot = Mock(spec=Bot)
            mock_app.bot.send_message = AsyncMock()
            mock_app.run_polling = AsyncMock()
            mock_app.stop = AsyncMock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                with patch.object(Config, 'ERROR_CHANNEL_ID', ''):
                    # Initialize
                    await bot_app.initialize()
                    assert bot_app.telegram_app is mock_app
                    
                    # Start (simulate quick completion)
                    await bot_app.start()
                    
                    # Shutdown
                    bot_app._running = True  # Simulate running state
                    await bot_app.shutdown()
                    
                    # Verify shutdown was called
                    mock_app.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_recovery_during_initialization(self):
        """Test error recovery during initialization."""
        service_registry = ServiceRegistry()
        bot_app = BotApplication(service_registry)
        
        # First attempt fails
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_builder.side_effect = RuntimeError("Network error")
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                with pytest.raises(RuntimeError):
                    await bot_app.initialize()
        
        # Second attempt succeeds
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock(spec=Application)
            mock_app.bot = Mock(spec=Bot)
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            # Mock handler registry
            mock_handler_registry = Mock()
            mock_handler_registry.register_all_handlers = AsyncMock()
            service_registry.register_instance('handler_registry', mock_handler_registry)
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                await bot_app.initialize()
                assert bot_app.telegram_app is mock_app
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent initialization and shutdown operations."""
        service_registry = ServiceRegistry()
        bot_app = BotApplication(service_registry)
        
        with patch('modules.bot_application.ApplicationBuilder') as mock_builder:
            mock_app = Mock(spec=Application)
            mock_app.bot = Mock(spec=Bot)
            mock_app.bot.send_message = AsyncMock()
            mock_app.stop = AsyncMock()
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            
            # Mock handler registry
            mock_handler_registry = Mock()
            mock_handler_registry.register_all_handlers = AsyncMock()
            service_registry.register_instance('handler_registry', mock_handler_registry)
            
            with patch.object(Config, 'TELEGRAM_BOT_TOKEN', 'test_token'):
                with patch.object(Config, 'ERROR_CHANNEL_ID', ''):
                    # Initialize
                    await bot_app.initialize()
                    
                    # Simulate concurrent shutdown attempts
                    bot_app._running = True
                    
                    shutdown_tasks = [
                        bot_app.shutdown(),
                        bot_app.shutdown(),
                        bot_app.shutdown()
                    ]
                    
                    await asyncio.gather(*shutdown_tasks)
                    
                    # Should handle concurrent shutdowns gracefully
                    assert not bot_app.is_running