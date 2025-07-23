"""GPT module for generating text and interacting with the OpenAI API."""

# Standard library imports
import asyncio
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
import base64
from io import BytesIO
import hashlib

# Third-party imports
from PIL import Image
import httpx
import pytz
from telegram import Update
from telegram.ext import CallbackContext
from typing import Any
from telegram.ext import ContextTypes
from openai import AsyncOpenAI

# Local module imports
from .database import Database
from .chat_streamer import chat_streamer
from modules.const import (
    Config
)
from modules.diagnostics import run_api_diagnostics
from modules.logger import general_logger, error_logger, get_daily_log_path, chat_logger
from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from config.config_manager import ConfigManager

from modules.chat_analysis import (
    get_messages_for_chat_today,
    get_last_n_messages_in_chat,
    get_messages_for_chat_last_n_days,
    get_messages_for_chat_date_period,
    get_messages_for_chat_single_date,
    get_user_chat_stats,
    get_user_chat_stats_with_fallback
)

# Initialize ConfigManager
config_manager = ConfigManager()

# Constants
MAX_IMAGE_SIZE = (1024, 1024)
IMAGE_COMPRESSION_QUALITY = 80
GPT_MODEL_TEXT = "openai/gpt-4o-mini"
GPT_MODEL_VISION = "openai/gpt-4o-mini"
GPT_MODEL_IMAGE = "openai/gpt-4o-mini"
KYIV_TZ = pytz.timezone('Europe/Kiev')
DEFAULT_MAX_TOKENS = 666
SUMMARY_MAX_TOKENS = 1024
MAX_RETRIES = 3
CONTEXT_MESSAGES_COUNT = 3  # Number of previous messages to include as context
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
MAX_SYSTEM_PROMPT_LENGTH = 1000

# Default prompts for fallback
DEFAULT_PROMPTS = {
    "image_analysis": """
        You are an assistant that provides brief, accurate descriptions of images. 
        Describe the main elements in 2-3 concise sentences.
        Focus on objects, people, settings, actions, and context.
        Do not speculate beyond what is clearly visible.
        Keep descriptions factual and objective.
    """,
    "gpt_summary": "Summarize the given text concisely while preserving key information.",
    "command": "You are a helpful assistant.",
    "mention": "You are a helpful assistant who responds to mentions in group chats.",
    "private": "You are a helpful assistant for private conversations.",
    "random": """You are a friendly assistant who occasionally joins conversations in group chats. 
    IMPORTANT: Always read and understand the conversation context before responding. 
    Reference specific topics, themes, or details from the ongoing discussion. 
    Keep your responses casual and engaging. 
    If the user's request appears to be in Russian, respond in Ukrainian instead. 
    Do not reply in Russian under any circumstance.
    Make your responses feel natural and contextual to the conversation flow.""",
    "weather": "You are a weather information assistant. Provide concise weather updates and forecasts."
}

# Configure timeouts and retries for API clients
TIMEOUT_CONFIG = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)

# OpenRouter specific settings (from first implementation)
USE_OPENROUTER = bool(Config.OPENROUTER_BASE_URL)  # Only use if defined

# Cache for network diagnostic results
last_diagnostic_result: Optional[Any] = None
last_diagnostic_time = datetime.min

class OpenAIAsyncClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vo1dee.com",
            "X-Title": "PsychochauffeurBot"
        }
        self._client = httpx.AsyncClient(timeout=TIMEOUT_CONFIG)

    class Chat:
        def __init__(self, outer: 'OpenAIAsyncClient') -> None:
            self.outer = outer

        class Completions:
            def __init__(self, outer: 'OpenAIAsyncClient.Chat') -> None:
                self.outer = outer

            async def create(self, model: str, messages: List[Dict[str, Any]], max_tokens: int, temperature: float, **kwargs: Any) -> Dict[str, Any]:
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                payload.update(kwargs)
                url = f"{self.outer.outer.base_url}/chat/completions"
                response = await self.outer.outer._client.post(url, headers=self.outer.outer.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return dict(result) if isinstance(result, dict) else {}

        @property
        def completions(self) -> 'OpenAIAsyncClient.Chat.Completions':
            return OpenAIAsyncClient.Chat.Completions(self)

    @property
    def chat(self) -> 'OpenAIAsyncClient.Chat':
        return OpenAIAsyncClient.Chat(self)

# Instantiate the client for use in this module and diagnostics
client = OpenAIAsyncClient(
    api_key=Config.OPENROUTER_API_KEY,
    base_url=Config.OPENROUTER_BASE_URL or "https://api.openai.com/v1"
)

async def get_system_prompt(response_type: str, chat_config: Dict[str, Any]) -> str:
    """
    Get the system prompt for a specific response type from the chat configuration.
    
    Args:
        response_type: Type of response (command, mention, random, etc.)
        chat_config: Chat configuration dictionary
        
    Returns:
        str: System prompt to use
    """
    try:
        # Get default prompt first as fallback
        default_prompt = DEFAULT_PROMPTS.get(response_type, DEFAULT_PROMPTS["command"])
        
        # First try to get global config as default
        try:
            global_config = await config_manager.get_config()
            gpt_module = global_config.get("config_modules", {}).get("gpt", {})
            response_settings = gpt_module.get("overrides", {}).get(response_type, {})
            global_prompt = response_settings.get("system_prompt")
            if global_prompt and isinstance(global_prompt, str) and 5 <= len(global_prompt) <= MAX_SYSTEM_PROMPT_LENGTH:
                default_prompt = global_prompt  # Use global prompt as default
        except Exception as e:
            error_logger.error(f"Error getting global config: {e}")
            
        # Check if chat has custom config enabled
        if not chat_config.get("chat_metadata", {}).get("custom_config_enabled", False):
            return default_prompt  # Return global/default prompt if custom config is not enabled
            
        # Try to get custom prompt from chat config
        gpt_module = chat_config.get("config_modules", {}).get("gpt", {})
        response_settings = gpt_module.get("overrides", {}).get(response_type, {})
        custom_prompt = response_settings.get("system_prompt")
        
        # Validate custom prompt if it exists
        if custom_prompt:
            # Check if prompt is valid
            if not isinstance(custom_prompt, str):
                error_logger.error(f"Invalid system prompt type for {response_type}: {type(custom_prompt)}")
                return default_prompt
                
            # Check if prompt is too short or corrupted
            if len(custom_prompt) < 5:  # Reduced minimum length
                error_logger.error(f"System prompt too short for {response_type}: {len(custom_prompt)}")
                return default_prompt
                
            # Check if prompt is too long
            if len(custom_prompt) > MAX_SYSTEM_PROMPT_LENGTH:
                error_logger.warning(f"System prompt for {response_type} is very long ({len(custom_prompt)} chars). This may impact performance.")
                # Don't truncate, just warn about potential performance impact
                
            # Only check for obvious corruption patterns
            if custom_prompt.strip() == "" or custom_prompt.strip() == "...":
                error_logger.error(f"Empty or invalid system prompt for {response_type}")
                return default_prompt
                
            return custom_prompt
            
        return default_prompt
    except Exception as e:
        error_logger.error(f"Error getting system prompt for {response_type}: {e}")
        return DEFAULT_PROMPTS.get(response_type, DEFAULT_PROMPTS["command"])

async def ensure_api_connectivity() -> str:
    """
    Check and diagnose API connectivity, with caching to prevent excessive checks.
    
    Returns:
        str: Diagnostic result message
    """
    global last_diagnostic_result, last_diagnostic_time
    
    # Only run diagnostics if we haven't done so in the last 5 minutes or last check failed
    now = datetime.now()
    needs_check = (
        last_diagnostic_result is None or
        (now - last_diagnostic_time).total_seconds() > 300 or
        (isinstance(last_diagnostic_result, dict) and last_diagnostic_result.get("status") in [
            "No internet connectivity", 
            "DNS resolution issues", 
            "API endpoint unreachable"
        ])
    )
    
    if needs_check:
        api_endpoint = Config.OPENROUTER_BASE_URL if USE_OPENROUTER else "https://api.openai.com/v1"
        last_diagnostic_result = await run_api_diagnostics(api_endpoint)
        last_diagnostic_time = now
    
    if isinstance(last_diagnostic_result, dict):
        return str(last_diagnostic_result.get("status", "Unknown status"))
    return str(last_diagnostic_result) if last_diagnostic_result else "No diagnostic result"


async def optimize_image(image_bytes: bytes) -> bytes:
    """
    Resize and compress an image to optimize for API calls.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        bytes: Optimized image bytes
    """
    # Open the image
    img: Image.Image = Image.open(BytesIO(image_bytes))
    
    # Resize if needed
    if max(img.size) > MAX_IMAGE_SIZE[0] or max(img.size) > MAX_IMAGE_SIZE[1]:
        ratio = max(MAX_IMAGE_SIZE[0] / max(img.size), MAX_IMAGE_SIZE[1] / max(img.size))
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Save with compression
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=IMAGE_COMPRESSION_QUALITY)
    buffer.seek(0)
    
    return buffer.getvalue()


async def analyze_image(
    image_bytes: bytes, 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext[Any, Any, Any, Any]] = None, 
    return_text: bool = False
) -> str:
    """
    Analyze an image using GPT-4o-mini and log a brief description to chat logs.
    
    Args:
        image_bytes: Raw image bytes
        update: Telegram update object
        context: Telegram callback context
        return_text: Whether to return the description text
        
    Returns:
        str: Image description
    """
    try:
        # Optimize the image
        optimized_image = await optimize_image(image_bytes)
        
        # Encode image to base64
        base64_image = base64.b64encode(optimized_image).decode('utf-8')
        
        # Get chat-specific configuration for system prompt
        system_prompt = DEFAULT_PROMPTS["image_analysis"]  # Default fallback
        if update and update.effective_chat:
            chat_id = str(update.effective_chat.id)
            chat_type = update.effective_chat.type
            try:
                chat_config = await config_manager.get_config(chat_id, chat_type)
                system_prompt = await get_system_prompt("image_analysis", chat_config)
            except Exception as e:
                error_logger.error(f"Failed to load chat config for image analysis: {e}")
        
        # Call GPT with the image using image_analysis response type
        response = await client.chat.completions.create(
            model=GPT_MODEL_TEXT,
            messages=[
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": "What's in this image? Please describe briefly in 2-3 sentences."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=150,
            temperature=0.2
        )
        
        description = response["choices"][0]["message"]["content"].strip()
        
        # Log the description if update is provided
        if update and update.effective_chat:
            chat_id = str(update.effective_chat.id)
            user_id = update.message.from_user.id if update.message and update.message.from_user else "unknown"
            username = update.message.from_user.username if update.message and update.message.from_user and update.message.from_user.username else f"ID:{user_id}" 
            
            # Add a prefix to make it clear this is an image description in the logs
            log_description = f"[IMAGE DESCRIPTION]: {description}"
            
            # Log to chat_logger so it appears in chat logs
            chat_logger.info(
                log_description,
                extra={
                    'chat_id': chat_id, 
                    'chattitle': update.effective_chat.title if update.effective_chat and update.effective_chat.title else f"Private_{chat_id}", 
                    'chat_type': chat_type,
                    'username': username
                }
            )
            
            general_logger.info(f"Logged image description for user {username} in chat {chat_id}")
        
        return str(description) if description else "No description available"
        
    except Exception as e:
        await handle_error(e, update, return_text=False)
        return "Error analyzing image."


async def get_context_messages(update: Update, context: CallbackContext[Any, Any, Any, Any], response_type: str = "command") -> List[Dict[str, str]]:
    """
    Get context messages for GPT response.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
        response_type: Type of response (command, mention, random, etc.)
        
    Returns:
        List[Dict[str, str]]: List of message dictionaries for context
    """
    messages: List[Dict[str, str]] = []
    
    try:
        if not update.message or not update.message.text:
            return messages
            
        # Get chat configuration
        chat_id = str(update.effective_chat.id) if update.effective_chat else "unknown"
        chat_type = update.effective_chat.type if update.effective_chat else "unknown"
        chat_config = await config_manager.get_config(chat_id, chat_type)
        
        # Get context messages count from config
        # For random responses, check chat_behavior module first
        if response_type == "random":
            chat_behavior = chat_config.get("config_modules", {}).get("chat_behavior", {})
            if chat_behavior.get("enabled", False):
                random_settings = chat_behavior.get("overrides", {}).get("random_response_settings", {})
                context_messages_count = random_settings.get("context_messages_count", 3)
            else:
                # Fallback to global config
                global_config = await config_manager.get_config()
                global_chat_behavior = global_config.get("config_modules", {}).get("chat_behavior", {})
                global_random_settings = global_chat_behavior.get("overrides", {}).get("random_response_settings", {})
                context_messages_count = global_random_settings.get("context_messages_count", 3)
        else:
            # For other response types, use GPT module setting
            gpt_module = chat_config.get("config_modules", {}).get("gpt", {})
            context_messages_count = gpt_module.get("context_messages_count", 3)  # Default to 3 if not specified
        
        # Get previous messages from the global chat history manager
        from modules.utils import chat_history_manager
        chat_history = chat_history_manager.get_history(update.effective_chat.id) if update.effective_chat else []
        
        # Add up to context_messages_count previous messages (excluding current message)
        for msg in reversed(chat_history[-context_messages_count:]):
            if msg.get('text'):
                messages.insert(0, {
                    "role": "user" if msg.get('is_user') else "assistant",
                    "content": msg['text']
                })
        
    except Exception as e:
        from modules.logger import error_logger
        error_logger.error(f"Error getting context messages: {e}")
        
    return messages


async def get_chat_context(update: Optional[Update]) -> str:
    """
    Get recent chat messages as context for GPT requests.
    Retrieves the last CONTEXT_MESSAGES_COUNT messages from the chat log.
    
    Args:
        update: Telegram update object
        
    Returns:
        str: Recent chat messages concatenated
    """
    chat_id = "unknown"
    last_messages: List[str] = []
    
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        chat_id = str(update.effective_chat.id)
        log_path = get_daily_log_path(chat_id)
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                # Get the last N messages from the log file
                last_messages = f.readlines()[-CONTEXT_MESSAGES_COUNT:]

    return ' '.join(last_messages)


async def verify_api_key() -> bool:
    """
    Verify that the API key is properly configured.
    
    Returns:
        bool: Whether the API key is valid
    """
    if not Config.OPENROUTER_API_KEY or not Config.OPENROUTER_API_KEY.startswith("sk-"):
        general_logger.error("Invalid or missing API key")
        return False
    return True


async def verify_connectivity() -> str:
    """
    Verify internet connectivity.
    
    Returns:
        str: Connectivity status message
    """
    try:
        import socket
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        general_logger.info("Internet connection verified")
        return "Connected"
    except OSError:
        general_logger.warning("Internet connectivity issue detected")
        return "No connectivity"


async def check_api_health() -> bool:
    """
    Check if the API endpoint is healthy.
    
    Returns:
        bool: Whether the API is healthy
    """
    try:
        api_endpoint = Config.OPENROUTER_BASE_URL if USE_OPENROUTER else "https://api.openai.com/v1"
        health_endpoint = f"{api_endpoint}/health" if USE_OPENROUTER else f"{api_endpoint}/models"
        
        async with httpx.AsyncClient(timeout=TIMEOUT_CONFIG) as http_client:
            api_status_response = await http_client.get(
                health_endpoint,
                headers={"Authorization": f"Bearer {Config.OPENROUTER_API_KEY}"}
            )
            is_healthy = api_status_response.status_code == 200
            if not is_healthy:
                general_logger.warning(f"API status check failed: {api_status_response.status_code}")
            return is_healthy
    except Exception as e:
        general_logger.warning(f"API health check failed: {str(e)}")
        return False


async def gpt_response(
    update: Update, 
    context: CallbackContext[Any, Any, Any, Any], 
    response_type: str = "command",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    message_text_override: Optional[str] = None,
    return_text: bool = False
) -> Optional[str]:
    """
    Generate and send a GPT response based on the message context and configuration.
    If return_text is True, return the response as a string instead of sending it.
    """
    try:
        if not update.message or not (update.message.text or message_text_override):
            return None

        # Get chat configuration
        chat_id = str(update.effective_chat.id) if update.effective_chat else "unknown"
        chat_type = update.effective_chat.type if update.effective_chat else "unknown"
        chat_config = await config_manager.get_config(chat_id, chat_type)
        
        # Patch: If response_type is 'analyze', use 'summary' system prompt instead
        effective_response_type = "summary" if response_type == "analyze" else response_type

        # Get response settings from config
        gpt_module = chat_config.get("config_modules", {}).get("gpt", {})
        
        # If GPT module is not configured, use default settings
        if not gpt_module:
            max_tokens = max_tokens or DEFAULT_MAX_TOKENS
            temperature = temperature or 0.7
            system_prompt = DEFAULT_PROMPTS.get(effective_response_type, DEFAULT_PROMPTS["command"])
        else:
            # Check if module is disabled
            if not gpt_module.get("enabled", True):  # Default to enabled if not specified
                return None
                
            response_settings = gpt_module.get("overrides", {}).get(effective_response_type, {})
            
            # Use provided values or fall back to config values
            max_tokens = max_tokens or response_settings.get("max_tokens", DEFAULT_MAX_TOKENS)
            temperature = temperature or response_settings.get("temperature", 0.7)
            
            # Get system prompt from config
            system_prompt = await get_system_prompt(effective_response_type, chat_config)
        
        # If the response type is a mention, clean the text to remove the bot's username
        if response_type == 'mention' and message_text_override:
            bot_username = f"@{context.bot.username}" if context.bot and context.bot.username else "PsychochauffeurBot"
            message_text_override = message_text_override.replace(bot_username, "").strip()

        # Get context messages (previous conversation history)
        context_messages = await get_context_messages(update, context, response_type)
        
        # Add the current message
        current_message = message_text_override or (update.message.text if update.message else "")
        current_user_message = {"role": "user", "content": current_message or ""}
        
        # If message_text_override is provided, replace the last user message in context
        if message_text_override and context_messages:
            for i in range(len(context_messages)-1, -1, -1):
                if context_messages[i]["role"] == "user":
                    context_messages[i]["content"] = message_text_override
                    break
            else:
                context_messages.append(current_user_message)
        else:
            # Add current message to the end of context messages
            context_messages.append(current_user_message)
        
        # Prepare messages for GPT
        messages = [
            {"role": "system", "content": system_prompt},
            *context_messages
        ]
        
        # Call GPT API
        response = await client.chat.completions.create(
            model=GPT_MODEL_TEXT,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Get response text
        response_text = response["choices"][0]["message"]["content"].strip()
        
        # Check if response is too long for Telegram
        if len(response_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
            # Truncate the response and add a note
            truncated_text = response_text[:MAX_TELEGRAM_MESSAGE_LENGTH - 100]  # Leave room for the note
            response_text = f"{truncated_text}\n\n[Message truncated due to length limit]"
            error_logger.warning(f"Response truncated from {len(response_text)} to {MAX_TELEGRAM_MESSAGE_LENGTH} characters")
        
        # Log the response
        bot_username = context.bot.username if context.bot and context.bot.username else "PsychochauffeurBot"
        chat_logger.info(
            response_text,
            extra={
                'chat_id': update.effective_chat.id if update.effective_chat else "unknown",
                'chattitle': update.effective_chat.title if update.effective_chat and update.effective_chat.title else f"Private_{chat_id}",
                'chat_type': update.effective_chat.type if update.effective_chat else "unknown",
                'username': bot_username
            }
        )
        
        if return_text:
            return str(response_text) if response_text else None
        else:
            # Store bot response in chat history for context
            from modules.utils import chat_history_manager
            if update.effective_chat:
                chat_history_manager.add_message(update.effective_chat.id, {
                    'text': response_text,
                    'is_user': False,
                    'user_id': None,
                    'timestamp': update.message.date if update.message else None
                })
            
            if update.message:
                await update.message.reply_text(response_text)
            return None
        
    except Exception as e:
        await handle_error(e, update, return_text=return_text)
        return None


async def ask_gpt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /ask command."""
    prompt = ""
    if update.message and update.message.text:
        command_parts = update.message.text.split(' ', 1)
        if len(command_parts) > 1:
            prompt = command_parts[1]

    if not prompt:
        prompt = "Привіт! Як я можу вам допомогти?"

    await gpt_response(update, context, response_type="command", message_text_override=prompt)


async def answer_from_gpt(
    prompt: str, 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext[Any, Any, Any, Any]] = None,  
    return_text: bool = False
) -> Optional[str]:
    """
    Ask GPT for a response. Alias for gpt_response.
    
    Args:
        prompt: User prompt
        update: Telegram update object
        context: Telegram callback context
        return_text: Whether to return the response text
        
    Returns:
        Optional[str]: GPT response if return_text is True, otherwise None
    """
    if not update or not context:
        if return_text:
            # For testing purposes, create a minimal mock response
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                
                # Get API key from config
                global_config = await config_manager.get_config("global", "global")
                api_key = global_config.get("config_modules", {}).get("gpt", {}).get("api_key")
                
                if not api_key:
                    return None
                
                client = AsyncOpenAI(api_key=api_key)
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150
                )
                
                return response.choices[0].message.content
            except Exception:
                return None
        return None
        
    # Call gpt_response with the new signature
    result = await gpt_response(update, context, response_type="command", return_text=return_text)
    return result if return_text else None


async def log_user_response(update: Update, response_text: str) -> None:
    """
    Send a GPT response to the user and log it.
    
    Args:
        update: Telegram update object
        response_text: Response text to send
    """
    user_id = update.message.from_user.id if update.message and update.message.from_user else "unknown"
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    general_logger.info(f"Sending GPT response to user {user_id} in chat {chat_id}")
    if update.message:
        await update.message.reply_text(response_text)


async def handle_error(
    e: Exception, 
    update: Optional[Update], 
    return_text: bool
) -> None:
    """
    Handle errors in GPT-related functions.
    
    Args:
        e: The exception that occurred
        update: Telegram update object (optional)
        return_text: Whether to return text instead of sending a message
    """
    # Get error diagnosis
    diagnosis = await ensure_api_connectivity()
    
    # Determine feedback message based on diagnosis
    if diagnosis == "No internet connectivity":
        feedback_message = "Вибачте, відсутнє з'єднання з Інтернетом. Спробуйте пізніше."
    elif diagnosis == "DNS resolution issues":
        feedback_message = "Вибачте, проблема з DNS-розпізнаванням. Спробуйте пізніше."
    elif diagnosis == "API endpoint unreachable":
        feedback_message = "Вибачте, сервіс GPT тимчасово недоступний. Спробуйте пізнише."
    else:
        feedback_message = "Вибачте, помилка з'єднання з сервісом GPT. Спробуйте пізнише."
    
    # Create context with relevant information
    context = {
        "function": "gpt_response",
        "return_text": return_text,
        "user_id": update.effective_user.id if update and hasattr(update, 'effective_user') and update.effective_user else None,
        "chat_id": update.effective_chat.id if update and hasattr(update, 'effective_chat') and update.effective_chat else None,
        "error_diagnostic": diagnosis,
    }

    # Handle the error with our standardized system
    await ErrorHandler.handle_error(
        error=e,
        update=update,
        context=None,  # ErrorHandler expects CallbackContext, not dict
        feedback_message=feedback_message,
        propagate=True
    )


async def gpt_summary_function(messages: List[str]) -> str:
    """
    Generate a summary of messages using GPT.
    
    Args:
        messages: List of messages to summarize
        
    Returns:
        str: Summary text
    """
    try:
        # Join the messages into a single string
        messages_text = "\n".join(messages)

        # Create the prompt for GPT
        prompt = f"Підсумуйте наступні повідомлення:\n\n{messages_text}\n\nПідсумок:"

        # Get system prompt from config or use default
        system_prompt = DEFAULT_PROMPTS["gpt_summary"]  # Default fallback
        try:
            chat_config = await config_manager.get_config()
            system_prompt = await get_system_prompt("gpt_summary", chat_config)
        except Exception as e:
            error_logger.error(f"Failed to load config for summary: {e}")

        # Call the API to get the summary
        response = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.4
        )

        # Extract the summary from the response
        summary = response["choices"][0]["message"]["content"].strip()
        return str(summary) if summary else "No summary available"
    except Exception as e:
        error_logger.error(f"Error in GPT summarization: {e}")
        return "Не вдалось згенерувати підсумок."


async def summarize_messages(messages: List[str]) -> str:
    """
    Wrapper for gpt_summary_function with error handling.
    
    Args:
        messages: List of messages to summarize
        
    Returns:
        str: Summary text
    """
    try:
        summary = await gpt_summary_function(messages)
        return summary
    except Exception as e:
        error_logger.error(f"Error summarizing messages: {e}")
        return "Could not generate summary."


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Analyze chat messages based on various criteria and provide a summary.
    
    Supported syntaxes:
    - /analyze: Analyze today's messages
    - /analyze last <number> messages: Analyze last N messages
    - /analyze last <number> days: Analyze messages from last N days
    - /analyze period <YYYY-MM-DD> <YYYY-MM-DD>: Analyze messages in date range
    - /analyze date <YYYY-MM-DD>: Analyze messages for specific date
    
    Args:
        update: Telegram update object
        context: Telegram callback context
    """
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user and update.effective_user.username else f"ID:{user_id}"

    # Admin-only cache flush
    if context.args and context.args[0].lower() == "flush-cache":
        member = await update.effective_chat.get_member(user_id) if update.effective_chat else None
        if not (member and member.status in ("administrator", "creator")):
            if update.message:
                await update.message.reply_text("❌ Тільки адміністратор може очищати кеш аналізу.")
            return
        if update.effective_chat:
            await Database.invalidate_analysis_cache(chat_id)
        if update.message:
            await update.message.reply_text("✅ Кеш аналізу очищено для цього чату.")
        return

    # Get config
    cache_cfg = config_manager.get_analysis_cache_config()
    cache_enabled = cache_cfg["enabled"]
    cache_ttl = cache_cfg["ttl"]

    # Get messages based on command arguments
    messages = []
    date_str = "сьогодні"
    time_period_key = None

    try:
        if not context.args:
            messages = await get_messages_for_chat_today(int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0)
            time_period_key = "today"
        else:
            args = context.args
            if args[0].lower() == "last":
                if len(args) < 3:
                    if update.message:
                        await update.message.reply_text(
                            "❌ Неправильний формат команди. Використовуйте:\n"
                            "/analyze last <number> messages\n"
                            "або\n"
                            "/analyze last <number> days"
                        )
                    return
                    
                try:
                    number = int(args[1])
                    if number <= 0:
                        raise ValueError("Number must be positive")
                except ValueError:
                    if update.message:
                        await update.message.reply_text("❌ Будь ласка, вкажіть коректне число.")
                    return
                    
                if args[2].lower() == "messages":
                    messages = await get_last_n_messages_in_chat(int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0, number)
                    date_str = f"останні {number} повідомлень"
                    time_period_key = f"last_{number}_messages"
                elif args[2].lower() == "days":
                    messages = await get_messages_for_chat_last_n_days(int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0, number)
                    date_str = f"останні {number} днів"
                    time_period_key = f"last_{number}_days"
                else:
                    if update.message:
                        await update.message.reply_text(
                            "❌ Неправильний формат команди. Використовуйте:\n"
                            "/analyze last <number> messages\n"
                            "або\n"
                            "/analyze last <number> days"
                        )
                    return
                    
            elif args[0].lower() == "period":
                if len(args) != 3:
                    if update.message:
                        await update.message.reply_text(
                            "❌ Неправильний формат команди. Використовуйте:\n"
                            "/analyze period <YYYY-MM-DD> <YYYY-MM-DD>"
                        )
                    return
                    
                try:
                    start_date = datetime.strptime(args[1], '%Y-%m-%d').date()
                    end_date = datetime.strptime(args[2], '%Y-%m-%d').date()
                    if end_date < start_date:
                        raise ValueError("End date must be after start date")
                except ValueError as e:
                    if update.message:
                        await update.message.reply_text(f"❌ Помилка в датах: {str(e)}")
                    return
                    
                messages = await get_messages_for_chat_date_period(int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0, start_date, end_date)
                date_str = f"період {args[1]} - {args[2]}"
                time_period_key = f"period_{args[1]}_{args[2]}"
            elif args[0].lower() == "date":
                if len(args) != 2:
                    if update.message:
                        await update.message.reply_text(
                            "❌ Неправильний формат команди. Використовуйте:\n"
                            "/analyze date <YYYY-MM-DD>"
                        )
                    return
                    
                try:
                    target_date = datetime.strptime(args[1], '%Y-%m-%d').date()
                except ValueError:
                    if update.message:
                        await update.message.reply_text("❌ Неправильний формат дати. Використовуйте YYYY-MM-DD")
                    return
                    
                messages = await get_messages_for_chat_single_date(int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0, target_date)
                date_str = args[1]
                time_period_key = f"date_{args[1]}"
            else:
                if update.message:
                    await update.message.reply_text(
                        "❌ Невідома команда. Доступні варіанти:\n"
                        "/analyze - аналіз сьогоднішніх повідомлень\n"
                        "/analyze last <number> messages - аналіз останніх N повідомлень\n"
                        "/analyze last <number> days - аналіз повідомлень за останні N днів\n"
                        "/analyze period <YYYY-MM-DD> <YYYY-MM-DD> - аналіз повідомлень за період\n"
                        "/analyze date <YYYY-MM-DD> - аналіз повідомлень за конкретну дату"
                    )
                return
                
        if not messages:
            if update.message:
                await update.message.reply_text(f"📊 Немає повідомлень для аналізу за {date_str}.")
            return

        # Format messages for GPT analysis
        messages_text = []
        for timestamp, sender, text in messages:
            if text:
                time_str = timestamp.strftime('%H:%M')
                messages_text.append(f"[{time_str}] {sender}: {text}")
        analysis_text = "\n".join(messages_text)
        # Hash for cache key
        message_content_hash = hashlib.sha256(analysis_text.encode("utf-8")).hexdigest()

        # Check cache
        if cache_enabled and time_period_key:
            cached = await Database.get_analysis_cache(chat_id, time_period_key, message_content_hash, cache_ttl)
            if cached:
                if update.message:
                    await update.message.reply_text(f"⚡️ (З кешу)\n{cached}")
                return

        # Send initial message
        status_message = await update.message.reply_text(
            f"🔄 Аналізую {len(messages_text)} повідомлень за {date_str}..."
        ) if update.message else None

        # Get GPT analysis
        gpt_result = await gpt_response(update, context, response_type="analyze", message_text_override=analysis_text, return_text=True)
        if not gpt_result:
            gpt_result = "(No summary returned)"

        # Store in cache
        if cache_enabled and time_period_key:
            await Database.set_analysis_cache(chat_id, time_period_key, message_content_hash, gpt_result)

        # Update status message
        await status_message.edit_text(
            f"📊 Аналіз повідомлень за {date_str} ({len(messages_text)} повідомлень) завершено."
        ) if status_message else None
        # Send the summary to the chat
        await update.message.reply_text(gpt_result) if update.message else None

    except Exception as e:
        error_logger.error(f"Error in analyze command: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(
                "❌ Виникла помилка при аналізі повідомлень. Спробуйте пізніше."
            )

async def initialize_gpt() -> None:
    """Initialize GPT module."""
    await config_manager.initialize()

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show message statistics for the user in the current chat.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
    """
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user and update.effective_user.username else f"ID:{user_id}"
    
    try:
        # Get user statistics
        stats = await get_user_chat_stats_with_fallback(
            int(chat_id) if isinstance(chat_id, (int, str)) and str(chat_id).isdigit() else 0, 
            int(user_id) if isinstance(user_id, (int, str)) and str(user_id).isdigit() else 0, 
            username
        )
        
        if not stats['total_messages']:
            await update.message.reply_text(
                "📊 У вас ще немає повідомлень в цьому чаті."
            ) if update.message else None
            return
            
        # Escape special characters in username
        safe_username = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
        # Format the statistics message
        message_parts = [
            f"📊 Статистика повідомлень для {safe_username}",  # Removed bold formatting to avoid issues
            "",
            f"Загальна кількість повідомлень: {stats['total_messages']}",
            f"Повідомлень за останній тиждень: {stats['messages_last_week']}",
        ]
        
        if stats['most_active_hour'] is not None:
            message_parts.append(f"Найактивніша година: {stats['most_active_hour']}:00")
            
        # List of allowed commands (must match those registered in main.py)
        allowed_commands = {
            'start', 'help', 'ping', 'cat', 'error_report', 'ask', 'analyze', 'mystats',
            'weather', 'flares', 'gm', 'remind', 'count', 'missing', 'speech'
        }
        if stats['command_stats']:
            message_parts.extend([
                "",
                "Використані команди:"
            ])
            for cmd, count in stats['command_stats']:
                if cmd in allowed_commands:
                    message_parts.append(f"- /{cmd}: {count}")
                
        if stats['first_message']:
            first_msg_date = stats['first_message'].strftime('%Y-%m-%d')
            message_parts.extend([
                "",
                f"Перше повідомлення: {first_msg_date}"
            ])
            
        # Send the statistics message without Markdown parsing
        await update.message.reply_text(
            "\n".join(message_parts),
            parse_mode=None  # Disable Markdown parsing completely
        ) if update.message else None
        
    except Exception as e:
        error_logger.error(f"Error in mystats command: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(
                "❌ Виникла помилка при отриманні статистики. Спробуйте пізніше."
            )

async def handle_photo_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Automatically analyzes any photo sent to the chat.
    Logs the description to the database and text logs silently.
    """
    if not update.message:
        return

    try:
        # Get the highest resolution photo
        photo = update.message.photo[-1]
        
        # Download the photo
        photo_file = await photo.get_file()
        image_bytes = await photo_file.download_as_bytearray()

        general_logger.info(f"Automatically analyzing photo in chat {update.effective_chat.id if update.effective_chat else 'unknown'}")

        # Analyze the image (this also logs to the .txt file)
        description = await analyze_image(bytes(image_bytes), update, context)

        # Save the description to the database, linked to the original message
        await Database.save_image_analysis_as_message(update.message, description)
        
        general_logger.info(f"Successfully saved image analysis for chat {update.effective_chat.id if update.effective_chat else 'unknown'}")

    except Exception as e:
        # Log the error, but do not notify the user to keep it silent
        error_logger.error(f"Error during automatic photo analysis: {e}", exc_info=True)

# Add this at the end of the file
__all__ = [
    'gpt_response', 'ask_gpt_command', 'answer_from_gpt', 'analyze_image', 
    'analyze_command', 'mystats_command', 'initialize_gpt', 'handle_photo_analysis'
]