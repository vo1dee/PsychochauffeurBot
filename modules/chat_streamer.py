import os
import logging
import asyncio
from datetime import datetime
import pytz
from typing import Optional, Dict, Any, Tuple
from telegram import Update
from telegram.ext import ContextTypes

from modules.const import KYIV_TZ
from modules.logger import get_chat_log_dir

class ChatStreamer:
    """
    Handles streaming chat messages to log files.
    Creates daily log files for each chat in the format:
    timestamp +0300 - chat - INFO - Ctx:[chat_id][chat_type][chat_name][username] - text
    """
    
    def __init__(self):
        self._loggers: Dict[str, Tuple[logging.Logger, logging.FileHandler]] = {}
        self._lock = asyncio.Lock()
    
    def _get_logger(self, chat_id: str) -> logging.Logger:
        """Get or create a logger for a specific chat."""
        if chat_id not in self._loggers:
            # Create chat-specific logger
            logger = logging.getLogger(f'chat_stream_{chat_id}')
            logger.setLevel(logging.INFO)
            
            # Create chat-specific log directory
            log_dir = get_chat_log_dir(chat_id)
            os.makedirs(log_dir, exist_ok=True)
            
            # Create daily log file handler
            today = datetime.now(KYIV_TZ).strftime('%Y-%m-%d')
            log_file = os.path.join(log_dir, f'{today}.log')
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s +0300 - chat - INFO - Ctx:[%(chat_id)s][%(chat_type)s][%(chat_name)s][%(username)s] - %(message)s'
            )
            
            # Create file handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Store both logger and handler
            self._loggers[chat_id] = (logger, file_handler)
        
        return self._loggers[chat_id][0]
    
    async def stream_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Stream a message to the appropriate log file.
        
        Args:
            update: Telegram update object
            context: Telegram callback context
        """
        try:
            chat_id = str(update.effective_chat.id)
            chat_type = update.effective_chat.type
            chat_name = update.effective_chat.title or f"Private_{chat_id}"
            username = update.effective_user.username or f"ID:{update.effective_user.id}"
            
            # Get logger for this chat
            logger = self._get_logger(chat_id)
            
            # Handle different message types
            if update.message:
                if update.message.text:
                    message_text = update.message.text
                elif update.message.sticker:
                    message_text = f"[STICKER] {update.message.sticker.emoji or 'No emoji'}"
                elif update.message.photo:
                    message_text = "[PHOTO]"
                elif update.message.video:
                    message_text = "[VIDEO]"
                elif update.message.voice:
                    message_text = "[VOICE]"
                elif update.message.audio:
                    message_text = "[AUDIO]"
                elif update.message.document:
                    message_text = f"[DOCUMENT] {update.message.document.file_name or 'Unnamed'}"
                elif update.message.animation:
                    message_text = "[ANIMATION]"
                else:
                    message_text = "[OTHER MEDIA]"
            else:
                message_text = "[UNKNOWN MESSAGE TYPE]"
            
            # Log the message with context
            logger.info(
                message_text,
                extra={
                    'chat_id': chat_id,
                    'chat_type': chat_type,
                    'chat_name': chat_name,
                    'username': username
                }
            )
            
            # Ensure the message is written to disk
            logger.handlers[0].flush()
            
        except Exception as e:
            logging.error(f"Error streaming message: {e}")
    
    async def close(self) -> None:
        """Close all file handlers."""
        for logger, handler in self._loggers.values():
            handler.flush()
            handler.close()
            logger.removeHandler(handler)
        self._loggers.clear()

# Create global instance
chat_streamer = ChatStreamer() 