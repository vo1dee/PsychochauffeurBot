import os
import sys
import logging
import asyncio
import html
from logging.handlers import RotatingFileHandler, BaseRotatingHandler
import threading
from typing import Set, Optional, Tuple, Dict, IO
from datetime import datetime, date
import pytz
import time
from modules.const import Config # Assuming Config.ERROR_CHANNEL_ID exists
from telegram import Bot
from telegram.ext import Application
from collections import deque # More efficient for fixed-size buffer than list

# --- Configuration (Placeholder - Ideally load from file/env) ---
# These should be loaded externally, e.g., from a config file or environment vars
LOG_LEVEL_CONSOLE = logging.INFO
LOG_LEVEL_GENERAL = logging.INFO
LOG_LEVEL_ANALYTICS = logging.INFO
LOG_LEVEL_CHAT = logging.INFO
LOG_LEVEL_ERROR = logging.ERROR
LOG_FILE_MAX_BYTES = 5 * 1024 * 1024 # 5 MB
LOG_FILE_BACKUP_COUNT = 3
TELEGRAM_ERROR_RATE_LIMIT = 2 # Seconds between messages
# ERROR_CHANNEL_ID should come from Config or environment

# --- Constants ---
KYIV_TZ = pytz.timezone('Europe/Kyiv')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')

# --- Utility Functions ---
def ensure_directories():
    """Ensure all required directories exist with proper permissions."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, 'logs')
    data_dir = os.path.join(project_root, 'data')
    analytics_dir = os.path.join(log_dir, 'analytics') # If needed elsewhere

    try:
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(analytics_dir, exist_ok=True) # Ensure analytics log dir exists too

        # Verify write permissions in log_dir
        test_log_path = os.path.join(log_dir, 'permission_test.log')
        with open(test_log_path, 'w') as f:
            f.write('Test log write\n')
        os.remove(test_log_path)
        print(f"Write permission verified for log directory: {log_dir}")
        return True
    except Exception as e:
        print(f"FATAL: Error setting up directories or checking permissions in {log_dir}: {e}", file=sys.stderr)
        return False

def get_chat_log_dir(chat_id: Optional[str]) -> str:
    """Gets the specific directory for a chat's logs."""
    safe_chat_id = str(chat_id) if chat_id is not None else "unknown_chat"
    # Basic sanitization to prevent path traversal issues with chat_id
    safe_chat_id = safe_chat_id.replace('/', '_').replace('\\', '_').replace('..', '')
    return os.path.join(LOG_DIR, f"chat_{safe_chat_id}")

def get_daily_log_path(chat_id: Optional[str], log_date: Optional[date] = None) -> str:
    """
    Generate the path for a daily log file for a specific chat.
    (No longer writes chat_name.txt)

    Args:
        chat_id: Chat ID (or None for general/unknown).
        log_date: Date for the log file, defaults to current date in Kyiv TZ.

    Returns:
        str: Path to the log file.
    """
    if log_date is None:
        log_date = datetime.now(KYIV_TZ).date()

    log_dir = get_chat_log_dir(chat_id)
    # Directory creation is handled by the DailyLogHandler now
    return os.path.join(log_dir, f"chat_{log_date.strftime('%Y-%m-%d')}.log")

def save_chat_title(chat_id: str, chat_title: str) -> None:
    """
    Saves or updates the chat title in a dedicated file within the chat's log directory.
    (Separated function for saving title)

    Args:
        chat_id: The chat ID.
        chat_title: The title of the chat.
    """
    if not chat_id or not chat_title:
        return # Don't save if info is missing

    try:
        log_dir = get_chat_log_dir(chat_id)
        os.makedirs(log_dir, exist_ok=True) # Ensure directory exists

        chat_name_file = os.path.join(log_dir, "chat_name.txt")
        # Check if file exists and content is the same to avoid unnecessary writes
        needs_write = True
        if os.path.exists(chat_name_file):
             try:
                 with open(chat_name_file, 'r', encoding='utf-8') as f:
                     if f.read() == chat_title:
                         needs_write = False
             except Exception:
                 # Ignore read errors, proceed to write
                 pass

        if needs_write:
            with open(chat_name_file, 'w', encoding='utf-8') as f:
                f.write(chat_title)
    except Exception as e:
        # Log this error using the error logger, but avoid infinite loops
        # if the error logger itself fails. Print as a fallback.
        print(f"ERROR: Could not save chat title for chat {chat_id}: {e}", file=sys.stderr)
        try:
            # Avoid using chat_logger here to prevent potential recursion
            logging.getLogger('error_logger').error(f"Could not save chat title for chat {chat_id}: {e}", exc_info=False)
        except Exception:
            pass # Fallback print already happened


# --- Custom Formatters ---

class KyivTimezoneFormatter(logging.Formatter):
    """Base formatter that uses Kyiv timezone for timestamps."""
    converter = lambda *args: datetime.fromtimestamp(args[1], KYIV_TZ).timetuple()

    def formatTime(self, record, datefmt=None):
        """Formats the timestamp to always include milliseconds."""
        dt = datetime.fromtimestamp(record.created, KYIV_TZ)
        if datefmt:
            return dt.strftime(datefmt.replace('%f', f'{dt.microsecond // 1000:03d}'))
        # Default format if none is provided
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')},{dt.microsecond // 1000:03d} {dt.strftime('%z')}"

class ChatContextFormatter(KyivTimezoneFormatter):
    """Formatter that includes Kyiv timezone AND chat context details."""
    def format(self, record):
        # Ensure chat attributes exist on the record, providing defaults
        record.chat_id = getattr(record, 'chat_id', 'N/A')
        record.chat_type = getattr(record, 'chat_type', 'N/A')
        record.chattitle = getattr(record, 'chattitle', 'Unknown')
        record.username = getattr(record, 'username', 'Unknown')
        # Let the parent class handle the actual formatting string
        return super().format(record)


# --- Custom Handlers ---

class DailyLogHandler(logging.Handler):
    """
    Logs messages to chat-specific daily files, managing file handles.
    (Manages file handles internally)
    """
    def __init__(self, encoding='utf-8'):
        super().__init__()
        self.encoding = encoding
        self._files: Dict[Tuple[Optional[str], date], IO] = {} # (chat_id, date) -> file handle
        self._lock = threading.Lock() # Protect access to self._files dict
        self._known_titles: Dict[str, str] = {} # Cache saved titles chat_id -> title

    def _get_file(self, record: logging.LogRecord) -> Optional[IO]:
        """Gets or creates the file handle for the record's chat and date."""
        try:
            record_time = datetime.fromtimestamp(record.created, KYIV_TZ)
            record_date = record_time.date()
            chat_id = getattr(record, 'chat_id', None) # Get chat_id, default to None
            chat_title = getattr(record, 'chattitle', None)

            # Use N/A for file system if chat_id attribute isn't set at all
            # Distinguish between chat_id=None and chat_id attribute missing
            if not hasattr(record, 'chat_id'):
                chat_id_for_path = 'N/A'
            else:
                chat_id_for_path = str(chat_id) if chat_id is not None else "unknown_chat"

            file_key = (chat_id_for_path, record_date)

            # Quick check without lock
            if file_key in self._files:
                return self._files[file_key]

            # Acquire lock for dictionary modification and file opening
            with self._lock:
                # Double check after acquiring lock
                if file_key in self._files:
                    return self._files[file_key]

                # --- File rotation logic (simplified: close old file for same chat_id if date changed) ---
                # Find and close any existing handle for the *same chat_id* but *different date*
                keys_to_remove = [
                    key for key in self._files
                    if key[0] == chat_id_for_path and key[1] != record_date
                ]
                for key in keys_to_remove:
                    handle = self._files.pop(key, None)
                    if handle:
                        handle.close()

                # --- Open new file ---
                log_path = get_daily_log_path(chat_id_for_path, record_date)
                log_dir = os.path.dirname(log_path)
                try:
                    os.makedirs(log_dir, exist_ok=True)
                    # Save chat title if it's new or changed for this chat
                    if chat_id and chat_title and self._known_titles.get(chat_id_for_path) != chat_title:
                         save_chat_title(chat_id_for_path, chat_title)
                         self._known_titles[chat_id_for_path] = chat_title # Update cache

                    # Open file in append mode with specified encoding
                    file_handle = open(log_path, 'a', encoding=self.encoding)
                    self._files[file_key] = file_handle
                    return file_handle

                except Exception as e:
                    print(f"ERROR: Failed to open daily log file {log_path}: {e}", file=sys.stderr)
                    self.handleError(record) # Use standard error handling
                    return None # Indicate failure

        except Exception as e:
            print(f"ERROR: Unexpected error in DailyLogHandler._get_file: {e}", file=sys.stderr)
            self.handleError(record)
            return None


    def emit(self, record: logging.LogRecord):
        """Emit a record."""
        try:
            # Add default attributes if missing BEFORE formatting
            if not hasattr(record, 'chat_id'): record.chat_id = 'N/A'
            if not hasattr(record, 'chattitle'): record.chattitle = 'Unknown'
            if not hasattr(record, 'username'): record.username = 'Unknown'

            msg = self.format(record)
            file_handle = self._get_file(record)

            if file_handle:
                try:
                    file_handle.write(msg + '\n')
                    file_handle.flush() # Ensure it's written promptly
                except Exception:
                    self.handleError(record)
        except Exception:
            self.handleError(record)

    def close(self):
        """Close all open file handles."""
        with self._lock:
            for handle in self._files.values():
                try:
                    handle.close()
                except Exception:
                    pass # Ignore errors during close
            self._files.clear()
        super().close()


class TelegramErrorHandler(logging.Handler):
    """
    Sends error logs to a Telegram channel asynchronously using a queue.
    (Queue-based, non-blocking emit, inherent async safety)
    """
    def __init__(self, bot_token: str, channel_id: str, rate_limit: int = 2):
        super().__init__()
        # Parse channel_id to handle topic-based messages
        if ':' in channel_id:
            self.channel_id, self.message_thread_id = channel_id.split(':')
            self.message_thread_id = int(self.message_thread_id)
        else:
            self.channel_id = channel_id
            self.message_thread_id = None
        self.rate_limit = rate_limit
        self.bot_token = bot_token # Store token to create bot internally

        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._last_sent_time: float = 0
        self._buffer: deque = deque() # Use deque for efficient buffering if needed
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bot_instance: Optional[Bot] = None
        self._start_lock = asyncio.Lock() # Protect against concurrent start attempts

    async def _ensure_bot(self):
        """Creates the bot instance if it doesn't exist."""
        if self._bot_instance is None:
            self._bot_instance = Bot(token=self.bot_token)
            # Test bot connection (optional but recommended)
            try:
                await self._bot_instance.get_me()
                print(f"Telegram bot connected successfully for error reporting.")
            except Exception as e:
                print(f"ERROR: Failed to connect Telegram bot for error reporting: {e}", file=sys.stderr)
                self._bot_instance = None # Reset if connection failed

    async def _send_message_async(self, text: str):
        """Internal async sending logic with retries."""
        if not self._bot_instance:
            print(f"ERROR: Telegram bot not initialized. Cannot send error: {text[:100]}...", file=sys.stderr)
            return

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Ensure text is properly formatted and within limits
                if len(text) > 4090:
                    text = text[:4087] + "..."
                
                # Prepare message parameters
                message_params = {
                    'chat_id': self.channel_id,
                    'text': text,
                    'parse_mode': 'MarkdownV2'
                }
                
                # Add message_thread_id if it exists
                if self.message_thread_id is not None:
                    message_params['message_thread_id'] = self.message_thread_id

                await self._bot_instance.send_message(**message_params)
                return # Success
            except Exception as e:
                print(f"ERROR: Attempt {attempt + 1} failed to send error to Telegram: {e}", file=sys.stderr)
                if attempt == max_retries - 1:
                    # Last attempt failed, try sending plain text
                    try:
                        # Strip Markdown formatting and escape special characters
                        plain_text = text.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
                        message_params = {
                            'chat_id': self.channel_id,
                            'text': f"Fallback (Markdown failed):\n{plain_text[:3800]}", # Limit length
                            'parse_mode': None
                        }
                        if self.message_thread_id is not None:
                            message_params['message_thread_id'] = self.message_thread_id

                        await self._bot_instance.send_message(**message_params)
                    except Exception as final_e:
                        print(f"ERROR: Final fallback attempt to send error to Telegram failed: {final_e}", file=sys.stderr)
                else:
                    await asyncio.sleep(retry_delay * (attempt + 1)) # Exponential backoff

    def format_error_message(self, record: logging.LogRecord) -> str:
        """Formats the error message using Markdown V2."""
        # Ensure attributes exist
        chat_id = getattr(record, 'chat_id', 'N/A')
        username = getattr(record, 'username', 'N/A')
        chat_title = getattr(record, 'chattitle', 'N/A')

        # Use the handler's formatter for the main message part
        core_message = self.format(record) # Get formatted message string
        
        # Escape special characters for Markdown V2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        safe_message = core_message
        for char in special_chars:
            safe_message = safe_message.replace(char, f'\\{char}')

        # Format timestamp using KyivTimezoneFormatter logic if possible
        try:
            record_time_str = KyivTimezoneFormatter().formatTime(record)
        except Exception:
            record_time_str = datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')

        # Escape special characters in timestamp
        safe_time = record_time_str
        for char in special_chars:
            safe_time = safe_time.replace(char, f'\\{char}')

        # Format the error message with proper Markdown V2 escaping
        error_msg = (
            "🚨 *Error Report*\n\n"
            f"*Time:* `{safe_time}`\n"
            f"*Level:* `{record.levelname}`\n"
            f"*Logger:* `{record.name}`\n"
            f"*Location:* `{record.pathname}:{record.lineno}`\n"
            f"*Function:* `{record.funcName}`\n"
            f"*Chat ID:* `{chat_id}`\n"
            f"*Username:* `{username}`\n"
            f"*Chat Title:* `{chat_title}`\n"
            f"*Message:*\n`{safe_message}`"
        )
        return error_msg[:4090] # Ensure message fits Telegram limits

    async def _process_queue(self):
        """The core worker task that processes logs from the queue."""
        await self._ensure_bot() # Make sure bot is ready

        while True:
            try:
                record: logging.LogRecord = await self._queue.get()
                if record is None: # Sentinel value to stop
                    self._queue.task_done()
                    break

                formatted_msg = self.format_error_message(record)
                now = time.monotonic() # Use monotonic clock for intervals

                # Basic rate limiting
                if now - self._last_sent_time >= self.rate_limit:
                    await self._send_message_async(formatted_msg)
                    self._last_sent_time = now
                    # Optionally send buffered messages here if needed
                    # while self._buffer:
                    #     await self._send_message_async(self._buffer.popleft())
                    #     await asyncio.sleep(0.1) # Small delay between buffered msgs
                else:
                    # Buffering (optional, can be noisy)
                    # self._buffer.append(formatted_msg)
                    # print(f"DEBUG: Buffering Telegram error due to rate limit.", file=sys.stderr)
                    pass # Or just drop if buffering isn't desired

                self._queue.task_done()
            except asyncio.CancelledError:
                print("Telegram error handler task cancelled.", file=sys.stderr)
                break
            except Exception as e:
                # Log critical errors in the processor itself to stderr
                print(f"CRITICAL ERROR in TelegramErrorHandler _process_queue: {e}", file=sys.stderr)
                # Avoid infinite loops by not using the logger here
                # Maybe sleep briefly to prevent tight loop errors
                await asyncio.sleep(5)


    def emit(self, record: logging.LogRecord):
        """Puts the record onto the async queue. Non-blocking."""
        if self._worker_task is None or self._loop is None:
            # Handler not started or loop not available
            print(f"WARNING: TelegramErrorHandler not started. Dropping message: {record.getMessage()}", file=sys.stderr)
            return

        # Use call_soon_threadsafe to safely add from any thread
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, record)
        except Exception as e:
             # Handle queue full or other errors if necessary
             print(f"ERROR: Failed to queue log message for Telegram: {e}", file=sys.stderr)
             self.handleError(record)


    async def start(self):
        """Starts the background worker task."""
        async with self._start_lock:
            if self._worker_task is None:
                try:
                    self._loop = asyncio.get_running_loop()
                    self._worker_task = self._loop.create_task(self._process_queue())
                    print("Telegram error handler worker started.")
                except RuntimeError:
                    print("ERROR: Cannot start TelegramErrorHandler. No running asyncio event loop.", file=sys.stderr)
                except Exception as e:
                    print(f"ERROR: Failed to start TelegramErrorHandler: {e}", file=sys.stderr)

    async def stop(self):
        """Stops the background worker task gracefully."""
        async with self._start_lock: # Ensure stop doesn't race with start
            if self._worker_task is not None and self._loop is not None:
                print("Stopping Telegram error handler worker...")
                try:
                    # Send sentinel value to the queue
                    self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
                    # Wait for the task to finish processing with a shorter timeout
                    await asyncio.wait_for(self._worker_task, timeout=5)
                    print("Telegram error handler worker stopped.")
                except asyncio.TimeoutError:
                    print("WARNING: Timeout waiting for Telegram worker to stop. Cancelling task.", file=sys.stderr)
                    self._worker_task.cancel()
                    try:
                        await asyncio.wait_for(self._worker_task, timeout=2)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                except Exception as e:
                    print(f"ERROR during TelegramErrorHandler stop: {e}", file=sys.stderr)
                    if not self._worker_task.done():
                        self._worker_task.cancel()
                        try:
                            await asyncio.wait_for(self._worker_task, timeout=2)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass

                self._worker_task = None
                self._loop = None
                if self._bot_instance:
                    try:
                        await asyncio.wait_for(self._bot_instance.close(), timeout=2)
                    except (asyncio.TimeoutError, Exception) as e:
                        print(f"WARNING: Error closing bot instance: {e}", file=sys.stderr)
                    self._bot_instance = None


# --- Logging System Initialization ---
_telegram_error_handler_instance: Optional[TelegramErrorHandler] = None

def initialize_logging() -> Tuple[logging.Logger, logging.Logger, logging.Logger, logging.Logger]:
    """Set up all loggers and handlers."""
    if not ensure_directories():
        print("FATAL: Logging directories could not be prepared. Exiting.", file=sys.stderr)
        sys.exit(1)

    # --- Formatters --- (Using the refined classes)
    # Define a unified format string that includes a placeholder for milliseconds
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_format_with_context = '%(asctime)s - %(name)s - %(levelname)s - Ctx:[%(chat_id)s][%(chat_type)s][%(chattitle)s][%(username)s] - %(message)s'
    time_format = '%Y-%m-%d %H:%M:%S,%f %z'

    # Basic formatter with Kyiv time
    kyiv_formatter = KyivTimezoneFormatter(
        log_format,
        datefmt=time_format
    )
    # Formatter with Kyiv time and chat context
    chat_context_formatter = ChatContextFormatter(
        log_format_with_context,
        datefmt=time_format
    )

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL_CONSOLE)
    console_handler.setFormatter(kyiv_formatter) # Use basic Kyiv formatter for console

    # --- General Logger ---
    general_logger = logging.getLogger('general') # Shorter name is fine
    general_logger.setLevel(LOG_LEVEL_GENERAL)
    general_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'general.log'),
        maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT, encoding='utf-8'
    )
    general_file_handler.setFormatter(chat_context_formatter) # General logs might have context
    general_logger.addHandler(console_handler)
    general_logger.addHandler(general_file_handler)
    general_logger.propagate = False

    # --- Analytics Logger ---
    analytics_logger = logging.getLogger('analytics')
    analytics_logger.setLevel(LOG_LEVEL_ANALYTICS)
    analytics_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'analytics', 'analytics.log'), # Put in subfolder
        maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT, encoding='utf-8'
    )
    analytics_file_handler.setFormatter(kyiv_formatter) # Analytics likely doesn't need chat context
    # analytics_logger.addHandler(console_handler) # Decide if analytics go to console
    analytics_logger.addHandler(analytics_file_handler)
    analytics_logger.propagate = False

    # --- Chat Logger ---
    chat_logger = logging.getLogger('chat')
    chat_logger.setLevel(LOG_LEVEL_CHAT)
    # Rotating main chat log (optional, DailyLogHandler might be sufficient)
    chat_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'chat_summary.log'), # Summary log
        maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT, encoding='utf-8'
    )
    chat_file_handler.setFormatter(chat_context_formatter)
    # Daily chat-specific handler
    daily_handler = DailyLogHandler(encoding='utf-8')
    daily_handler.setLevel(LOG_LEVEL_CHAT) # Ensure it logs chat level
    daily_handler.setFormatter(chat_context_formatter) # Use context formatter

    chat_logger.addHandler(console_handler) # Chat logs also to console
    chat_logger.addHandler(chat_file_handler) # Add summary rotating log
    chat_logger.addHandler(daily_handler) # Add daily specific log
    chat_logger.propagate = False

    # --- Error Logger ---
    error_logger = logging.getLogger('error')
    error_logger.setLevel(LOG_LEVEL_ERROR)
    error_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'error.log'),
        maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_FILE_BACKUP_COUNT, encoding='utf-8'
    )
    # Error logs might contain context, use chat_context_formatter
    error_file_handler.setFormatter(chat_context_formatter)
    # error_file_handler.setFormatter(kyiv_formatter) # Or use basic if context is less critical here

    error_logger.addHandler(console_handler) # Errors to console
    error_logger.addHandler(error_file_handler)
    # Telegram handler added later in init_telegram_error_handler
    error_logger.propagate = False

    # --- Suppress noisy library logs ---
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO) # Adjust as needed

    print(f"Logging system initialized. Log levels: Console={logging.getLevelName(LOG_LEVEL_CONSOLE)}, File={logging.getLevelName(LOG_LEVEL_GENERAL)} etc.")
    print(f"Log files base directory: {LOG_DIR}")

    # Add note about LoggerAdapter
    general_logger.info("Logging initialized. Use LoggerAdapter for adding context (chat_id, etc.) easily.")
    # Example usage comment (not runnable here):
    # '''
    # # Example Usage in your application code:
    # chat_id = update.effective_chat.id
    # username = update.effective_user.username or 'N/A'
    # chattitle = update.effective_chat.title or f'Private_{chat_id}'
    #
    # adapter = logging.LoggerAdapter(chat_logger, {'chat_id': chat_id, 'username': username, 'chattitle': chattitle})
    # adapter.info("User did something.")
    #
    # general_logger.info("General message without adapter context")
    # error_logger.error("An error occurred", exc_info=True, extra={'chat_id': chat_id}) # Can also use extra directly
    # '''

    return general_logger, chat_logger, error_logger, analytics_logger

async def init_telegram_error_handler(bot_token: str, error_channel_id: str):
    """Initializes and starts the Telegram error handler."""
    global _telegram_error_handler_instance
    error_logger = logging.getLogger('error')
    general_logger = logging.getLogger('general') # For logging init status

    if not bot_token:
        error_logger.error("Telegram Bot Token is not configured. Cannot initialize Telegram error handler.")
        return
    if not error_channel_id:
         error_logger.error("Telegram Error Channel ID is not configured. Cannot initialize Telegram error handler.")
         return

    if _telegram_error_handler_instance is not None:
         general_logger.warning("Telegram error handler already initialized.")
         return

    try:
        # Use the detailed formatter for the *content* of the Telegram message
        formatter = ChatContextFormatter( # Using ChatContextFormatter for detail in the <pre> block
            '%(asctime)s - %(name)s - %(levelname)s\n'
            'File: %(pathname)s:%(lineno)d\n'
            'Function: %(funcName)s\n'
            # Context handled by format_error_message, base message here:
            'Message: %(message)s'
        )
        handler = TelegramErrorHandler(
            bot_token=bot_token,
            channel_id=error_channel_id,
            rate_limit=TELEGRAM_ERROR_RATE_LIMIT
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.ERROR) # Ensure it only handles errors

        await handler.start() # Start the background task

        if handler._worker_task is not None: # Check if start was successful
             error_logger.addHandler(handler)
             _telegram_error_handler_instance = handler # Store instance
             general_logger.info(f"Telegram error handler initialized successfully for channel ID: {error_channel_id}")
        else:
             error_logger.error("Telegram error handler started, but worker task is missing.")

    except Exception as e:
        error_logger.error(f"Failed to initialize Telegram error handler: {e}", exc_info=True)


async def shutdown_logging():
    """Gracefully shuts down logging handlers, especially the Telegram one."""
    general_logger = logging.getLogger('general')
    general_logger.info("Shutting down logging system...")

    # Stop Telegram handler first
    if _telegram_error_handler_instance:
        await _telegram_error_handler_instance.stop()
        # Remove handler after stopping
        error_logger = logging.getLogger('error')
        error_logger.removeHandler(_telegram_error_handler_instance)


    # Close DailyLogHandler files
    chat_logger = logging.getLogger('chat')
    for handler in chat_logger.handlers:
        if isinstance(handler, DailyLogHandler):
             handler.close()

    # Standard logging shutdown
    logging.shutdown()
    print("Logging system shut down.")


# --- Initialize logging when this module is imported ---
# Note: Telegram handler requires async context and config, so it's initialized separately later.
general_logger, chat_logger, error_logger, analytics_logger = initialize_logging()

# --- Example of how to call the async init and shutdown ---
# async def main():
#     # ... your application setup ...
#     BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
#     ERROR_CHANNEL_ID = Config.ERROR_CHANNEL_ID # Or os.environ.get("ERROR_CHANNEL_ID")
#
#     await init_telegram_error_handler(BOT_TOKEN, ERROR_CHANNEL_ID)
#
#     # ... run your application ...
#     try:
#         # application.run_polling() or similar
#         # Keep main task running
#          while True:
#             await asyncio.sleep(3600)
#     except KeyboardInterrupt:
#         print("Shutdown signal received.")
#     finally:
#        # ... other cleanup ...
#        await shutdown_logging() # Gracefully stop logging
#
# if __name__ == "__main__":
#      # Make sure to run within an asyncio event loop
#      # asyncio.run(main()) # Python 3.7+
#      pass # Don't run main automatically when module is imported