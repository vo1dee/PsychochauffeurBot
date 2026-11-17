import os
import sys
import logging
import asyncio
import contextvars
import re
import html
from logging.handlers import RotatingFileHandler, BaseRotatingHandler
import threading
from typing import Set, Optional, Tuple, Dict, IO, Any
from datetime import datetime, date
import pytz
import time
from modules.const import Config # Assuming Config.ERROR_CHANNEL_ID exists
from telegram import Bot
from telegram.ext import Application
from telegram.error import NetworkError, BadRequest
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

# --- Per-update log context ---
# Every incoming Telegram update sets this (see set_log_context_from_update), and
# because python-telegram-bot runs each update in its own asyncio task, the value
# is isolated per update and inherited by any task spawned while handling it.
# LogContextFilter copies it onto every record so errors show which chat/message
# triggered them even when the logging call itself passed no `extra`.
_LOG_CONTEXT: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "psychochauffeur_log_context", default=None
)
_MESSAGE_SNIPPET_LEN = 200


def get_log_context() -> Dict[str, Any]:
    """Return the chat/user/message context of the update being handled (may be empty)."""
    return dict(_LOG_CONTEXT.get() or {})


def set_log_context(**fields: Any) -> contextvars.Token[Optional[Dict[str, Any]]]:
    """Merge fields into the current log context; returns a token for reset_log_context."""
    merged = get_log_context()
    merged.update({k: v for k, v in fields.items() if v is not None})
    return _LOG_CONTEXT.set(merged)


def reset_log_context(token: contextvars.Token[Optional[Dict[str, Any]]]) -> None:
    """Restore the log context that was active before set_log_context()."""
    _LOG_CONTEXT.reset(token)


def build_log_context_from_update(update: Any) -> Dict[str, Any]:
    """Extract chat, user and message identifiers from a Telegram Update (duck-typed)."""
    ctx: Dict[str, Any] = {}
    try:
        chat = getattr(update, "effective_chat", None)
        user = getattr(update, "effective_user", None)
        message = getattr(update, "effective_message", None)
        if chat is not None:
            ctx["chat_id"] = chat.id
            ctx["chat_type"] = getattr(chat, "type", None)
            ctx["chattitle"] = (
                getattr(chat, "title", None)
                or getattr(chat, "full_name", None)
                or f"Private_{chat.id}"
            )
        if user is not None:
            ctx["user_id"] = user.id
            ctx["username"] = (
                f"@{user.username}" if getattr(user, "username", None)
                else (getattr(user, "full_name", None) or str(user.id))
            )
        if message is not None:
            ctx["message_id"] = getattr(message, "message_id", None)
            text = getattr(message, "text", None) or getattr(message, "caption", None)
            if isinstance(text, str) and text:
                ctx["message_text"] = text[:_MESSAGE_SNIPPET_LEN]
            elif getattr(message, "voice", None) is not None:
                ctx["message_text"] = "<voice>"
            elif getattr(message, "video_note", None) is not None:
                ctx["message_text"] = "<video note>"
            elif getattr(message, "photo", None):
                ctx["message_text"] = "<photo>"
        callback = getattr(update, "callback_query", None)
        if callback is not None and getattr(callback, "data", None):
            ctx["callback_data"] = str(callback.data)[:100]
    except Exception:
        # Context is best-effort; never let it break update handling.
        pass
    return {k: v for k, v in ctx.items() if v is not None}


def set_log_context_from_update(update: Any) -> None:
    """Replace the current log context with the identifiers of `update`."""
    _LOG_CONTEXT.set(build_log_context_from_update(update))


def message_link(chat_id: Any, message_id: Any) -> Optional[str]:
    """Return a t.me link to a supergroup/channel message, if one can be built."""
    try:
        cid = str(chat_id)
        if message_id is None or not cid.startswith("-100"):
            return None
        return f"https://t.me/c/{cid[4:]}/{int(message_id)}"
    except (TypeError, ValueError):
        return None


class LogContextFilter(logging.Filter):
    """Fill chat/user/message fields on a record from the per-update context.

    Fields passed explicitly via `extra=` win; the context only fills gaps.
    Attached to handlers (not loggers) so it also applies to records that
    propagate from third-party loggers to the root handlers.
    """

    FIELDS = ("chat_id", "chat_type", "chattitle", "username", "user_id",
              "message_id", "message_text", "callback_data")

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _LOG_CONTEXT.get()
        if ctx:
            for field in self.FIELDS:
                current = getattr(record, field, None)
                if (current is None or current in ("N/A", "Unknown", "-")) and field in ctx:
                    setattr(record, field, ctx[field])
        return True


# --- Utility Functions ---
def ensure_directories() -> bool:
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
    # The base expects converter: Callable[[Optional[float]], struct_time]
    @staticmethod
    def converter(timestamp: Optional[float]) -> time.struct_time:
        if timestamp is None:
            timestamp = time.time()
        return datetime.fromtimestamp(timestamp, KYIV_TZ).timetuple()

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Formats the timestamp to always include milliseconds."""
        dt = datetime.fromtimestamp(record.created, KYIV_TZ)
        if datefmt:
            return dt.strftime(datefmt.replace('%f', f'{dt.microsecond // 1000:03d}'))
        # Default format if none is provided
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')},{dt.microsecond // 1000:03d} {dt.strftime('%z')}"

class ChatContextFormatter(KyivTimezoneFormatter):
    """Formatter that includes Kyiv timezone AND chat context details."""
    def format(self, record: logging.LogRecord) -> str:
        # Ensure chat attributes exist on the record, providing defaults
        record.chat_id = getattr(record, 'chat_id', 'N/A')
        record.chat_type = getattr(record, 'chat_type', 'N/A')
        record.chattitle = getattr(record, 'chattitle', 'Unknown')
        record.username = getattr(record, 'username', 'Unknown')
        record.message_id = getattr(record, 'message_id', '-')
        # Let the parent class handle the actual formatting string
        return super().format(record)


# --- Custom Handlers ---

class DailyLogHandler(logging.Handler):
    """
    Logs messages to chat-specific daily files, managing file handles.
    (Manages file handles internally)
    """
    _files: Dict[Tuple[Optional[str], date], IO[str]]
    _lock: threading.Lock
    _known_titles: Dict[str, str]
    def __init__(self, encoding: str = 'utf-8') -> None:
        super().__init__()
        self.encoding = encoding
        self._files: Dict[Tuple[Optional[str], date], IO[str]] = {} # (chat_id, date) -> file handle
        self._lock = threading.Lock() # Protect access to self._files dict
        self._known_titles: Dict[str, str] = {} # Cache saved titles chat_id -> title

    def _get_file(self, record: logging.LogRecord) -> Optional[IO[str]]:
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


    def emit(self, record: logging.LogRecord) -> None:
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

    def close(self) -> None:
        """Close all open file handles."""
        with self._lock:
            for handle in self._files.values():
                try:
                    handle.close()
                except Exception:
                    pass # Ignore errors during close
            self._files.clear()
        super().close()


class TransientNetworkErrorFilter(logging.Filter):
    """
    Filters out transient network errors from Telegram polling.

    These errors occur during normal operation when Telegram's servers briefly
    disconnect.  python-telegram-bot retries them automatically; they are not
    actionable and should never reach the error channel.

    Primary check: PTB wraps every transport error as telegram.error.NetworkError
    before default_error_callback sees it (httpcore.ReadError → httpx.ReadError →
    telegram.error.NetworkError), so a single isinstance() call covers all variants.
    BadRequest is a NetworkError subclass but IS actionable (HTTP 400), so it is
    explicitly kept.

    Secondary fallback: substring patterns cover transient errors that are logged
    inline in the message string rather than via exc_info.

    Only suppresses errors from telegram.ext loggers.
    All other errors (download failures, bot logic, database, etc.) pass through.
    """

    # Secondary fallback: transient error substrings that appear inline in message text.
    # The primary path (exc_info type check) handles polling errors; these cover edge cases.
    TRANSIENT_PATTERNS = (
        'httpx.RemoteProtocolError',
        'httpx.ReadError',
        'httpx.ReadTimeout',
        'httpx.ConnectError',
        'Server disconnected without sending a response',
        'All connection attempts failed',
        'httpcore.RemoteProtocolError',
        'httpcore.ConnectError',
        'httpcore.ReadError',
        'httpcore.ReadTimeout',
    )

    def filter(self, record: logging.LogRecord) -> bool:
        # Only apply to telegram.ext loggers (Updater, Application, etc.)
        if not record.name.startswith('telegram.ext'):
            return True  # Keep all non-telegram errors

        # Primary check: transient errors are wrapped by PTB as NetworkError.
        # Exclude BadRequest (a NetworkError subclass) so actionable HTTP 400s
        # are still reported.
        exc = record.exc_info[1] if record.exc_info else None
        if isinstance(exc, NetworkError) and not isinstance(exc, BadRequest):
            return False  # Suppress this transient error

        # Secondary fallback: substring match for transient errors logged without exc_info.
        message = record.getMessage()
        for pattern in self.TRANSIENT_PATTERNS:
            if pattern in message:
                return False  # Suppress this transient error

        return True  # Keep all other telegram.ext errors


class TelegramErrorHandler(logging.Handler):
    """
    Sends error logs to a Telegram channel asynchronously using a queue.
    (Queue-based, non-blocking emit, inherent async safety)
    """
    channel_id: str
    message_thread_id: Optional[int]
    rate_limit: int
    bot_token: str
    _queue: asyncio.Queue[Optional[logging.LogRecord]]
    _worker_task: Optional[asyncio.Task[Any]]
    _last_sent_time: float
    _buffer: deque[str]
    _loop: Optional[asyncio.AbstractEventLoop]
    _bot_instance: Optional[Bot]
    _start_lock: asyncio.Lock
    DEDUP_WINDOW = 600.0  # seconds: identical errors inside this window are reported once

    def __init__(self, bot_token: str, channel_id: str, rate_limit: int = 2) -> None:
        super().__init__()
        # Parse channel_id to handle topic-based messages
        if ':' in channel_id:
            self.channel_id, thread_id = channel_id.split(':')
            self.message_thread_id = int(thread_id)
        else:
            self.channel_id = channel_id
            self.message_thread_id = None
        self.rate_limit = rate_limit
        self.bot_token = bot_token # Store token to create bot internally

        self._queue: asyncio.Queue[Optional[logging.LogRecord]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[Any]] = None
        self._last_sent_time: float = 0
        self._buffer: deque[str] = deque() # Use deque for efficient buffering if needed
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bot_instance: Optional[Bot] = None
        self._start_lock = asyncio.Lock() # Protect against concurrent start attempts
        # Duplicate suppression: key -> (first_seen_monotonic, suppressed_count)
        self._recent: Dict[Tuple[str, int, str], Tuple[float, int]] = {}
        self._suppressed_totals: Dict[Tuple[str, int, str], int] = {}

    async def _ensure_bot(self) -> None:
        """Creates the bot instance if it doesn't exist."""
        if self._bot_instance is None:
            self._bot_instance = Bot(token=self.bot_token)
            try:
                await self._bot_instance.get_me()
                print(f"Telegram bot connected successfully for error reporting.")
            except Exception as e:
                print(f"ERROR: Failed to connect Telegram bot for error reporting: {e}", file=sys.stderr)
                self._bot_instance = None

    async def _send(self, text: str, parse_mode: Optional[str]) -> None:
        assert self._bot_instance is not None
        kwargs: Dict[str, Any] = {
            "chat_id": self.channel_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if self.message_thread_id is not None:
            kwargs["message_thread_id"] = self.message_thread_id
        await self._bot_instance.send_message(**kwargs)

    async def _send_message_async(self, text: str, plain_text: Optional[str] = None) -> None:
        """Send an HTML report with retries; fall back to the untouched plain text."""
        # Re-create bot instance if it was lost (e.g. failed at startup)
        if not self._bot_instance:
            await self._ensure_bot()
        if not self._bot_instance:
            print(f"ERROR: Telegram bot not available. Cannot send error: {text[:100]}...", file=sys.stderr)
            return

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                await self._send(text, 'HTML')
                return  # Success
            except BadRequest as e:
                # A formatting problem will not fix itself on retry; go straight to plain text.
                print(f"ERROR: Telegram rejected HTML error report: {e}", file=sys.stderr)
                break
            except Exception as e:
                error_msg = str(e).lower()
                if "chat not found" in error_msg:
                    print("ERROR: Telegram error channel not accessible. Disabling error notifications.", file=sys.stderr)
                    self._bot_instance = None
                    return
                print(f"ERROR: Attempt {attempt + 1} failed to send error to Telegram: {e}", file=sys.stderr)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        try:
            fallback = plain_text if plain_text is not None else re.sub(r"<[^>]+>", "", html.unescape(text))
            await self._send(fallback[:4000], None)
        except Exception as final_e:
            print(f"ERROR: Final fallback attempt to send error to Telegram failed: {final_e}", file=sys.stderr)

    # --- Report content ---

    @staticmethod
    def _context_lines(record: logging.LogRecord) -> list[Tuple[str, str]]:
        """Return (label, value) pairs describing the chat/message behind the error."""
        def present(value: Any) -> bool:
            return value not in (None, "", "-", "N/A", "Unknown")

        chat_id = getattr(record, 'chat_id', None)
        title = getattr(record, 'chattitle', None)
        chat_type = getattr(record, 'chat_type', None)
        user = getattr(record, 'username', None)
        user_id = getattr(record, 'user_id', None)
        message_id = getattr(record, 'message_id', None)
        text = getattr(record, 'message_text', None)
        callback = getattr(record, 'callback_data', None)

        lines: list[Tuple[str, str]] = []
        if present(chat_id) or present(title):
            chat = str(title) if present(title) else ""
            details = ", ".join(str(v) for v in (chat_id, chat_type) if present(v))
            lines.append(("Chat", f"{chat} ({details})".strip() if details else chat))
        if present(user) or present(user_id):
            who = str(user) if present(user) else ""
            if present(user_id) and str(user_id) not in who:
                who = f"{who} ({user_id})".strip()
            lines.append(("User", who))
        if present(message_id):
            link = message_link(chat_id, message_id)
            lines.append(("Message", f"{message_id} {link}" if link else str(message_id)))
        if present(text):
            lines.append(("Text", str(text)))
        if present(callback):
            lines.append(("Callback", str(callback)))
        return lines

    def _record_time(self, record: logging.LogRecord) -> str:
        try:
            return KyivTimezoneFormatter().formatTime(record)
        except Exception:
            return datetime.now(KYIV_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')

    def format_plain_message(self, record: logging.LogRecord, suppressed: int = 0) -> str:
        """Plain-text version of the report, used when HTML is rejected."""
        lines = [
            "🚨 Error Report",
            f"Time: {self._record_time(record)}",
            f"Level: {record.levelname}",
            f"Logger: {record.name}",
            f"Location: {record.pathname}:{record.lineno} ({record.funcName})",
        ]
        context = self._context_lines(record)
        lines += [f"{label}: {value}" for label, value in context] or ["Context: none (not tied to an update)"]
        if suppressed:
            lines.append(f"Similar errors suppressed since last report: {suppressed}")
        lines += ["", self.format(record)]
        return "\n".join(lines)[:4000]

    def format_error_message(self, record: logging.LogRecord, suppressed: int = 0) -> str:
        """Format the report as Telegram HTML (only <, > and & need escaping)."""
        esc = html.escape
        context = self._context_lines(record)
        parts = [
            "🚨 <b>Error Report</b>",
            "",
            f"<b>Time:</b> <code>{esc(self._record_time(record))}</code>",
            f"<b>Level:</b> <code>{esc(record.levelname)}</code>",
            f"<b>Logger:</b> <code>{esc(record.name)}</code>",
            f"<b>Location:</b> <code>{esc(f'{record.pathname}:{record.lineno}')}</code> "
            f"(<code>{esc(record.funcName or '')}</code>)",
        ]
        if context:
            for label, value in context:
                parts.append(f"<b>{esc(label)}:</b> {esc(value)}")
        else:
            parts.append("<b>Context:</b> <i>none (not tied to an update)</i>")
        if suppressed:
            parts.append(f"<b>Similar errors suppressed since last report:</b> {suppressed}")

        header = "\n".join(parts)
        budget = 4000 - len(header) - 40
        body = self.format(record)
        if len(body) > budget:
            # Keep the end of tracebacks: the actual exception is at the bottom.
            body = "…" + body[-max(budget, 200):]
        return f"{header}\n<b>Error:</b>\n<pre>{esc(body)}</pre>"

    # --- Duplicate suppression ---

    _NORMALIZE_RE = re.compile(r"https?://\S+|\d+")

    def _dedup_key(self, record: logging.LogRecord) -> Tuple[str, int, str]:
        exc = record.exc_info[1] if record.exc_info else None
        exc_name = type(exc).__name__ if exc else ""
        msg = self._NORMALIZE_RE.sub("#", record.getMessage().split("\n", 1)[0])[:120]
        return (f"{record.name}:{exc_name}", record.lineno, msg)

    def _should_send(self, record: logging.LogRecord) -> Tuple[bool, int]:
        """Return (send?, suppressed_count) for identical errors within DEDUP_WINDOW."""
        key = self._dedup_key(record)
        now = time.monotonic()
        # Drop stale entries so the dict cannot grow without bound.
        for stale in [k for k, (ts, _) in self._recent.items() if now - ts > self.DEDUP_WINDOW]:
            _, count = self._recent.pop(stale)
            if count:
                self._suppressed_totals[stale] = self._suppressed_totals.get(stale, 0) + count
        if len(self._suppressed_totals) > 500:
            self._suppressed_totals.clear()
        if key in self._recent:
            ts, count = self._recent[key]
            self._recent[key] = (ts, count + 1)
            return False, 0
        self._recent[key] = (now, 0)
        suppressed = self._suppressed_totals.pop(key, 0)
        return True, suppressed

    async def _process_queue(self) -> None:
        """The core worker task that processes logs from the queue."""
        await self._ensure_bot() # Make sure bot is ready

        while True:
            try:
                record: Optional[logging.LogRecord] = await self._queue.get()
                if record is None: # Sentinel value to stop
                    self._queue.task_done()
                    break

                send, suppressed = self._should_send(record)
                if not send:
                    self._queue.task_done()
                    continue

                formatted_msg = self.format_error_message(record, suppressed)
                plain_msg = self.format_plain_message(record, suppressed)

                # Rate limiting: wait until enough time has passed since last send
                now = time.monotonic()
                elapsed = now - self._last_sent_time
                if elapsed < self.rate_limit:
                    await asyncio.sleep(self.rate_limit - elapsed)

                await self._send_message_async(formatted_msg, plain_msg)
                self._last_sent_time = time.monotonic()

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


    def emit(self, record: logging.LogRecord) -> None:
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


    async def start(self) -> None:
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

    async def stop(self) -> None:
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
    log_format_with_context = '%(asctime)s - %(name)s - %(levelname)s - Ctx:[%(chat_id)s][%(chat_type)s][%(chattitle)s][%(username)s][msg:%(message_id)s] - %(message)s'
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

    # Fill chat/user/message fields from the per-update context on every handler.
    context_filter = LogContextFilter()
    context_handlers: Tuple[logging.Handler, ...] = (
        console_handler, general_file_handler, analytics_file_handler,
        chat_file_handler, daily_handler, error_file_handler,
    )
    for handler in context_handlers:
        handler.addFilter(context_filter)

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

async def init_telegram_error_handler(bot: Bot, error_channel_id: Optional[str] = None) -> None:
    """
    Initializes and starts the Telegram error handler.

    This function should be called once at application startup.

    Args:
        bot (Bot): The bot instance to use for sending messages.
        error_channel_id (str): The channel ID to send error messages to.
    """
    if not error_channel_id:
        general_logger.warning("No error_channel_id provided; Telegram error handler will not be started.")
        return

    global _telegram_error_handler_instance
    if _telegram_error_handler_instance is not None:
        general_logger.warning("Telegram error handler is already initialized.")
        return

    try:
        # Create and start the handler
        telegram_handler = TelegramErrorHandler(
            bot_token=bot.token, # Get token from bot instance
            channel_id=error_channel_id
        )
        telegram_handler.setLevel(logging.ERROR)  # Only send ERROR and above
        telegram_handler.addFilter(LogContextFilter())
        telegram_handler.addFilter(TransientNetworkErrorFilter())
        await telegram_handler.start()

        # Add the handler to the root logger to catch all errors
        logging.getLogger().addHandler(telegram_handler)
        # Also add directly to error_logger since it has propagate=False
        logging.getLogger('error').addHandler(telegram_handler)
        general_logger.info("Telegram error handler initialized and attached to root logger.")

        # Store reference for graceful shutdown
        # This might be better handled in a more structured application context
        _telegram_error_handler_instance = telegram_handler

    except Exception as e:
        general_logger.error(f"Failed to initialize Telegram error handler: {e}", exc_info=True)


async def shutdown_logging() -> None:
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