import os
import logging
import asyncio
from datetime import datetime
import pytz
from typing import Optional, Dict, Any, Tuple, cast, List
from telegram import Update, Chat, User
from telegram.ext import ContextTypes

from modules.const import KYIV_TZ
from modules.logger import get_chat_log_dir

class ChatStreamer:
    """
    Handles streaming chat messages to log files.
    Creates daily log files for each chat in the format:
    timestamp +0300 - chat - INFO - Ctx:[chat_id][chat_type][chat_name][username] - text
    """
    
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Get the main chat logger which handles both summary and daily logs
        self._chat_logger = logging.getLogger('chat')
        # Store original handlers to restore them in close()
        self._original_handlers = self._chat_logger.handlers[:]
    
    async def stream_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Stream a message to the appropriate log file.
        
        Args:
            update: Telegram update object
            context: Telegram callback context
        """
        try:
            if update.effective_chat is None:
                return
            chat_id = str(update.effective_chat.id)
            chat_type = update.effective_chat.type
            chat_name = update.effective_chat.title or f"Private_{chat_id}"
            
            if update.effective_user is None:
                username = "Unknown"
            else:
                username = update.effective_user.username or f"ID:{update.effective_user.id}"
            
            # Create log context first
            log_context = {
                'chat_id': chat_id,
                'chat_type': chat_type,
                'chattitle': chat_name,  # Changed from chat_name to chattitle to match formatter
                'username': username
            }
            
            # Handle different message types
            if update.message:
                if update.message.text:
                    message_text = update.message.text
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.sticker:
                    message_text = f"[STICKER] {update.message.sticker.emoji or 'No emoji'}"
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.photo:
                    # Log the photo first
                    message_text = "[PHOTO]"
                    self._chat_logger.info(message_text, extra=log_context)
                    
                    # If there's a caption, log it separately
                    if update.message.caption:
                        message_text = update.message.caption
                        self._chat_logger.info(message_text, extra=log_context)
                elif update.message.video:
                    message_text = "[VIDEO]"
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.voice:
                    message_text = "[VOICE]"
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.audio:
                    message_text = "[AUDIO]"
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.document:
                    message_text = f"[DOCUMENT] {update.message.document.file_name or 'Unnamed'}"
                    self._chat_logger.info(message_text, extra=log_context)
                elif update.message.animation:
                    message_text = "[ANIMATION]"
                    self._chat_logger.info(message_text, extra=log_context)
                else:
                    message_text = "[OTHER MEDIA]"
                    self._chat_logger.info(message_text, extra=log_context)
            else:
                message_text = "[UNKNOWN MESSAGE TYPE]"
                self._chat_logger.info(message_text, extra=log_context)
            
            # Ensure all handlers flush their output
            for handler in self._chat_logger.handlers:
                try:
                    handler.flush()
                except (BrokenPipeError, OSError) as e:
                    # Handle broken pipe errors gracefully (e.g., log rotation, closed files)
                    # Errno 32 is EPIPE (Broken pipe) - common during log rotation
                    # Don't log this as it's often expected and not critical
                    if hasattr(e, 'errno') and e.errno == 32:
                        # Broken pipe - silently ignore
                        pass
                    else:
                        # Other OSError - log at debug level
                        logging.debug(f"Handler flush OSError (non-critical): {e}")
                except Exception as e:
                    # Log other handler errors but don't crash
                    logging.debug(f"Handler flush error (non-critical): {e}")
            
        except (BrokenPipeError, OSError) as e:
            # Handle broken pipe errors gracefully - don't spam error logs
            if hasattr(e, 'errno') and e.errno == 32:
                # Broken pipe - silently ignore
                pass
            else:
                # Other OSError - log at debug level
                logging.debug(f"Error streaming message (non-critical): {e}")
        except Exception as e:
            # Log other errors
            logging.error(f"Error streaming message: {e}")
    
    async def close(self) -> None:
        """Close all file handlers."""
        # Remove all handlers from the chat logger
        for handler in self._chat_logger.handlers[:]:
            handler.close()
            self._chat_logger.removeHandler(handler)
        
        # Restore original handlers
        for handler in self._original_handlers:
            self._chat_logger.addHandler(handler)

# Create global instance
chat_streamer: ChatStreamer = ChatStreamer()