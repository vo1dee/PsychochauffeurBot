"""
Logging configuration module for the PsychoChauffeur bot.
"""
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import html
from datetime import datetime
from typing import Optional
from telegram.ext import Application
from telegram.error import TelegramError

from const import LOG_DIR, KYIV_TZ
from modules.helpers import ensure_directory, get_daily_log_path

def init_error_handler():
    """Initialize the error handler and ensure log directory exists."""
    ensure_directory(LOG_DIR)

def setup_loggers() -> None:
    """Initialize and configure all loggers."""
    init_error_handler()
    
    # Configure log handlers
    handlers = {
        'general': RotatingFileHandler(f'{LOG_DIR}/general_log.log', maxBytes=2000, backupCount=10),
        'chat': RotatingFileHandler(f'{LOG_DIR}/chat_log.log', maxBytes=2000, backupCount=10),
        'error': RotatingFileHandler(f'{LOG_DIR}/error_log.log', maxBytes=2000, backupCount=10)
    }
    
    # Configure formatters
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    for handler in handlers.values():
        handler.setFormatter(formatter)
    
    # Set up general logger
    general_logger = logging.getLogger('general_logger')
    general_logger.setLevel(logging.INFO)
    general_logger.addHandler(handlers['general'])
    
    # Set up chat logger
    chat_logger = logging.getLogger('chat_logger')
    chat_logger.setLevel(logging.INFO)
    chat_logger.addHandler(handlers['chat'])
    
    # Set up error logger
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    error_logger.addHandler(handlers['error'])

# Create global logger instances
general_logger = logging.getLogger('general_logger')
chat_logger = logging.getLogger('chat_logger')
error_logger = logging.getLogger('error_logger')

class TelegramErrorHandler(logging.Handler):
    """Custom handler for sending error logs to Telegram channel."""
    
    def __init__(self, bot: Application, channel_id: str, rate_limit: int = 1):
        """
        Initialize the Telegram error handler.
        
        Args:
            bot: Telegram bot application instance
            channel_id: Telegram channel ID to send errors to
            rate_limit: Minimum seconds between consecutive messages
        """
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self.buffer = []
        self.last_sent = 0
        self.rate_limit = rate_limit
        
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def send_message(self, error_msg: str) -> None:
        """
        Send message to Telegram with retry logic.
        
        Args:
            error_msg: Error message to send
        """
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                escaped_msg = error_msg.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
                await self.bot.bot.send_message(
                    chat_id=self.channel_id,
                    text=escaped_msg,
                    parse_mode='MarkdownV2'
                )
                return
            except TelegramError as e:
                if attempt == max_retries - 1:
                    general_logger.error(f"Failed to send error message to Telegram after {max_retries} attempts: {e}")
                    try:
                        await self.bot.bot.send_message(
                            chat_id=self.channel_id,
                            text=html.escape(error_msg),
                            parse_mode=None
                        )
                    except TelegramError as final_e:
                        general_logger.error(f"Final attempt to send message failed: {final_e}")
                await asyncio.sleep(retry_delay * (attempt + 1))

    def format_error_message(self, record: logging.LogRecord) -> str:
        """
        Format the error message with all relevant information.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted error message
        """
        current_time = datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        chat_id = getattr(record, 'chat_id', 'N/A')
        username = getattr(record, 'username', 'N/A')
        chat_title = getattr(record, 'chattitle', 'N/A')
        
        error_msg = (
            f"🚨 *Error Report*\n"
            f"*Time:* {current_time}\n"
            f"*Level:* {record.levelname}\n"
            f"*Location:* {record.pathname}:{record.lineno}\n"
            f"*Function:* {record.funcName}\n"
            f"*Chat ID:* {chat_id}\n"
            f"*Username:* {username}\n"
            f"*Chat Title:* {chat_title}\n"
            f"*Message:*\n"
            f"```\n{self.format(record)}\n```"
        )
        return error_msg

    def emit(self, record: logging.LogRecord) -> None:
        """
        Override emit to handle the log record.
        
        Args:
            record: Log record to emit
        """
        try:
            error_msg = self.format_error_message(record)
            coroutine = self.send_message(error_msg)
            try:
                asyncio.create_task(coroutine)
            except RuntimeError:
                self.loop.run_until_complete(coroutine)
        except Exception as e:
            general_logger.error(f"Error in TelegramErrorHandler.emit: {e}")
            self.handleError(record)

# Initialize loggers on module import
setup_loggers()