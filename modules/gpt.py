import openai
import os
import base64
import httpx
import asyncio
import pytz
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from io import BytesIO
from PIL import Image

from modules.diagnostics import run_api_diagnostics
from modules.logger import general_logger, error_logger, get_daily_log_path, chat_logger
from modules.const import OPENAI_API_KEY, OPENROUTER_BASE_URL
from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

# Import appropriate prompts based on environment
if os.getenv("USE_EMPTY_PROMPTS", "false").lower() == "true":
    from modules.prompts_empty import GPT_PROMPTS  # Use empty prompts in GitHub Actions
else:
    from modules.prompts import GPT_PROMPTS  # Use actual prompts on the server
from modules.const import OPENAI_API_KEY
from config.config_manager import ConfigManager

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient, APIStatusError

# Initialize ConfigManager
config_manager = ConfigManager()

# Constants
MAX_IMAGE_SIZE = 1024
IMAGE_COMPRESSION_QUALITY = 80
GPT_MODEL_IMAGE = "gpt-4.1-mini"  # From second implementation
GPT_MODEL_TEXT = "gpt-4.1-mini"       # From second implementation
KYIV_TZ = pytz.timezone('Europe/Kiev')
DEFAULT_MAX_TOKENS = 666
SUMMARY_MAX_TOKENS = 1000
MAX_RETRIES = 3
CONTEXT_MESSAGES_COUNT = 3  # Number of previous messages to include as context

# Configure timeouts and retries for API clients
TIMEOUT_CONFIG = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)

# OpenRouter specific settings (from first implementation)
USE_OPENROUTER = bool(OPENROUTER_BASE_URL)  # Only use if defined

# Initialize OpenAI client with proper configuration
client = AsyncClient(
    api_key=OPENAI_API_KEY, 
    base_url=OPENROUTER_BASE_URL if USE_OPENROUTER else None,
    timeout=TIMEOUT_CONFIG,
    max_retries=3,
)

# Add OpenRouter specific headers if using it
if USE_OPENROUTER:
    client.default_headers.update({
        "HTTP-Referer": "https://vo1dee.com", 
        "X-Title": "PsychochauffeurBot"     
    })

# Cache for network diagnostic results
last_diagnostic_result = None
last_diagnostic_time = datetime.min


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
        last_diagnostic_result in [
            "No internet connectivity", 
            "DNS resolution issues", 
            "API endpoint unreachable"
        ]
    )
    
    if needs_check:
        api_endpoint = OPENROUTER_BASE_URL if USE_OPENROUTER else "https://api.openai.com/v1"
        last_diagnostic_result = await run_api_diagnostics(api_endpoint)
        last_diagnostic_time = now
    
    return last_diagnostic_result


async def optimize_image(image_bytes: bytes) -> bytes:
    """
    Resize and compress an image to optimize for API calls.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        bytes: Optimized image bytes
    """
    # Open the image
    img = Image.open(BytesIO(image_bytes))
    
    # Resize if needed
    if max(img.size) > MAX_IMAGE_SIZE:
        ratio = MAX_IMAGE_SIZE / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    # Save with compression
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=IMAGE_COMPRESSION_QUALITY)
    buffer.seek(0)
    
    return buffer.getvalue()


async def analyze_image(
    image_bytes: bytes, 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext] = None, 
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
        system_prompt = GPT_PROMPTS["image_analysis"]  # Default fallback
        if update and update.effective_chat:
            chat_id = str(update.effective_chat.id)
            chat_type = "private" if update.effective_chat.type == "private" else "group"
            try:
                chat_config = await config_manager.get_config(chat_id, chat_type)
                gpt_settings = chat_config.get("gpt_settings", {})
                image_settings = gpt_settings.get("image_analysis", {})
                system_prompt = image_settings.get("system_prompt", system_prompt)
            except Exception as e:
                error_logger.error(f"Failed to load chat config for image analysis: {e}")
        
        # Call GPT with the image using image_analysis response type
        response = await client.chat.completions.create(
            model=GPT_MODEL_IMAGE,
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
        
        description = response.choices[0].message.content.strip()
        
        # Log the description if update is provided
        if update and update.effective_chat:
            chat_id = update.effective_chat.id
            user_id = update.message.from_user.id if update.message.from_user else "unknown"
            username = update.message.from_user.username or f"ID:{user_id}" 
            
            # Add a prefix to make it clear this is an image description in the logs
            log_description = f"[IMAGE DESCRIPTION]: {description}"
            
            # Log to chat_logger so it appears in chat logs
            chat_logger.info(
                log_description,
                extra={
                    'chat_id': chat_id, 
                    'chattitle': update.effective_chat.title or f"Private_{chat_id}", 
                    'username': username
                }
            )
            
            general_logger.info(f"Logged image description for user {username} in chat {chat_id}")
        
        return description
        
    except Exception as e:
        await handle_error(e, update, return_text)
        return "Error analyzing image."


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
    last_messages = []
    
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        chat_id = update.effective_chat.id
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
    if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"):
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
        api_endpoint = OPENROUTER_BASE_URL if USE_OPENROUTER else "https://api.openai.com/v1"
        health_endpoint = f"{api_endpoint}/health" if USE_OPENROUTER else f"{api_endpoint}/models"
        
        async with httpx.AsyncClient(timeout=TIMEOUT_CONFIG) as http_client:
            api_status_response = await http_client.get(
                health_endpoint,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
            )
            is_healthy = api_status_response.status_code == 200
            if not is_healthy:
                general_logger.warning(f"API status check failed: {api_status_response.status_code}")
            return is_healthy
    except Exception as e:
        general_logger.warning(f"API health check failed: {str(e)}")
        return False


async def gpt_response(
    prompt: str, 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext] = None, 
    return_text: bool = False,
    response_type: str = "regular",
    max_retries: int = MAX_RETRIES
) -> Optional[str]:
    """
    Get a response from GPT with robust error handling and retries.
    
    Args:
        prompt: User prompt
        update: Telegram update object
        context: Telegram callback context
        return_text: Whether to return the response text
        response_type: Type of response (regular, weather, analyze, image_analysis, summary)
        max_retries: Maximum number of retry attempts
        
    Returns:
        Optional[str]: GPT response text if return_text is True, otherwise None
    """
    retry_count = 0
    last_error = None
    
    # Get chat-specific configuration
    chat_config = {}
    if update and update.effective_chat:
        chat_id = str(update.effective_chat.id)
        chat_type = "private" if update.effective_chat.type == "private" else "group"
        chat_name = update.effective_chat.title or f"Private_{chat_id}"
        
        try:
            chat_config = await config_manager.get_config(
                chat_id=chat_id,
                chat_type=chat_type,
                chat_name=chat_name
            )
            general_logger.info(f"Loaded chat config for GPT response in {chat_type} chat {chat_id}")
        except Exception as e:
            error_logger.error(f"Failed to load chat config for GPT response: {e}")
            # Continue with default settings if config loading fails
    
    # Get response settings from chat config or use defaults
    gpt_settings = chat_config.get("gpt_settings", {})
    response_settings = gpt_settings.get(response_type, gpt_settings.get("regular", {}))
    
    # Extract settings with defaults
    max_tokens = response_settings.get("max_tokens", DEFAULT_MAX_TOKENS)
    temperature = response_settings.get("temperature", 0.6)
    presence_penalty = response_settings.get("presence_penalty", 0.0)
    frequency_penalty = response_settings.get("frequency_penalty", 0.0)
    model = response_settings.get("model", GPT_MODEL_TEXT)
    
    # Get system prompt from config or use default
    system_prompt = response_settings.get("system_prompt", "")
    if not system_prompt:
        # Fallback to default prompts if not in config
        if response_type == "regular":
            system_prompt = GPT_PROMPTS["gpt_response"]
        elif response_type == "image_analysis":
            system_prompt = GPT_PROMPTS["image_analysis"]
        elif response_type == "summary":
            system_prompt = GPT_PROMPTS["gpt_summary"]
        else:
            system_prompt = GPT_PROMPTS["gpt_response"]
    
    while retry_count < max_retries:
        try:
            # Get chat context
            context_prompt = await get_chat_context(update)
            full_prompt = context_prompt + prompt

            # Log connection attempt
            general_logger.info(f"Attempting to connect to API (attempt {retry_count+1}/{max_retries})")
            
            # Verify API key
            if not await verify_api_key():
                error_message = "Invalid or missing API key"
                if return_text:
                    return "Configuration error: API key issue."
                else:
                    if update and hasattr(update, 'message') and update.message:
                        await update.message.reply_text(
                            "Бот тимчасово недоступний через проблему з конфігурацією API."
                        )
                    return None
            
            # Verify connectivity
            connectivity = await verify_connectivity()
            if connectivity != "Connected":
                general_logger.warning("Proceeding with API call despite connectivity issues")
            
            # Check API health
            api_healthy = await check_api_health()
            if not api_healthy:
                general_logger.warning("Proceeding with API call despite health check failure")
            
            # Make the API call with chat-specific settings
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": full_prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty
            )
            
            # Process the response
            if hasattr(response, 'choices') and len(response.choices) > 0 and hasattr(response.choices[0], 'message'):
                response_text = response.choices[0].message.content.strip()
                
                if return_text:
                    return response_text
                    
                if update and hasattr(update, 'message') and update.message:
                    await log_user_response(update, response_text)
                else:
                    general_logger.warning("No valid update object; response not sent to chat.")
                
                return response_text if return_text else None
            else:
                error_message = f"Unexpected API response structure: {str(response)[:100]}..."
                general_logger.error(error_message)
                raise ValueError(error_message)
                
        except httpx.HTTPStatusError as http_err:
            error_message = f"HTTP error: {http_err.response.status_code} - {http_err.response.text[:200]}"
            general_logger.error(error_message)
            last_error = http_err
            
        except APIStatusError as e:
            # This captures all OpenAI status errors (4xx, 5xx)
            general_logger.error(f"OpenAI API returned error {e.status_code}: {e.body}")
            last_error = e
            
        except Exception as e:
            general_logger.error(f"Error in API request: {str(e)}")
            last_error = e
        
        # Handle retry logic
        retry_count += 1
        if retry_count < max_retries:
            wait_time = 2 ** retry_count  # Exponential backoff
            await asyncio.sleep(wait_time)
        else:
            await handle_error(last_error, update, return_text)
            if return_text:
                return "Error generating response after multiple retries. Please try again later."
            else:
                if update and hasattr(update, 'message') and update.message:
                    await update.message.reply_text(
                        "Вибачте, сталася помилка при зверненні до GPT. Перевірте конфігурацію API."
                    )
                return None
    
    # This should never be reached due to the else clause above, but included for safety
    return "Connection error after multiple retries." if return_text else None


async def ask_gpt_command(
    prompt: Union[str, Update], 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext] = None, 
    return_text: bool = False
) -> Optional[str]:
    """
    Process a GPT command from either a string prompt or an Update object.
    
    Args:
        prompt: String prompt or Update object
        update: Telegram update object if prompt is a string
        context: Telegram callback context
        return_text: Whether to return the response text
        
    Returns:
        Optional[str]: GPT response if return_text is True, otherwise None
    """
    if isinstance(prompt, Update):
        update = prompt
        message_text = update.message.text
        command_parts = message_text.split(' ', 1)
        prompt = command_parts[1] if len(command_parts) > 1 else "Привіт!"
    
    return await gpt_response(prompt, update, context, return_text, response_type="regular")


async def answer_from_gpt(
    prompt: str, 
    update: Optional[Update] = None, 
    context: Optional[CallbackContext] = None, 
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
    return await gpt_response(prompt, update, context, return_text)


async def log_user_response(update: Update, response_text: str) -> None:
    """
    Send a GPT response to the user and log it.
    
    Args:
        update: Telegram update object
        response_text: Response text to send
    """
    user_id = update.message.from_user.id if update.message.from_user else "unknown"
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    general_logger.info(f"Sending GPT response to user {user_id} in chat {chat_id}")
    await update.message.reply_text(response_text)


async def handle_error(
    e: Exception, 
    update: Optional[Update], 
    return_text: bool
) -> None:
    """
    Handle errors with appropriate diagnosis and feedback.
    
    Args:
        e: Exception that occurred
        update: Telegram update object
        return_text: Whether the calling function returns text
    """
    # Determine the error type and severity
    error_category = ErrorCategory.GENERAL
    error_severity = ErrorSeverity.MEDIUM
    feedback_message = "Вибачте, сталася помилка при зверненні до GPT."
    diagnosis = None
    
    # Check for connection-related errors
    if isinstance(e, (openai.APIConnectionError, httpx.ConnectError)):
        error_category = ErrorCategory.NETWORK
        # Run diagnostics to get more specific information
        api_endpoint = OPENROUTER_BASE_URL if USE_OPENROUTER else "https://api.openai.com/v1"
        diagnosis = await run_api_diagnostics(api_endpoint)
        
        if diagnosis == "No internet connectivity":
            feedback_message = "Вибачте, відсутнє з'єднання з Інтернетом. Спробуйте пізніше."
        elif diagnosis == "DNS resolution issues":
            feedback_message = "Вибачте, проблема з DNS-розпізнаванням. Спробуйте пізніше."
        elif diagnosis == "API endpoint unreachable":
            feedback_message = "Вибачте, сервіс GPT тимчасово недоступний. Спробуйте пізніше."
        else:
            feedback_message = "Вибачте, помилка з'єднання з сервісом GPT. Спробуйте пізніше."
    
    # Create context with relevant information
    context = {
        "function": "gpt_response",
        "return_text": return_text,
        "user_id": update.effective_user.id if update and update.effective_user else None,
        "chat_id": update.effective_chat.id if update and update.effective_chat else None,
        "error_diagnostic": diagnosis,
    }

    # Handle the error with our standardized system
    await ErrorHandler.handle_error(
        error=e,
        update=update,
        context=None,
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
        system_prompt = GPT_PROMPTS["gpt_summary"]  # Default fallback
        try:
            chat_config = await config_manager.get_config()
            gpt_settings = chat_config.get("gpt_settings", {})
            summary_settings = gpt_settings.get("summary", {})
            system_prompt = summary_settings.get("system_prompt", system_prompt)
        except Exception as e:
            error_logger.error(f"Failed to load config for summary: {e}")

        # Call the API to get the summary
        response = await client.chat.completions.create(
            model=GPT_MODEL_TEXT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.4
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()
        return summary
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
    Analyze chat messages for a specific day and provide a summary.
    
    Args:
        update: Telegram update object
        context: Telegram callback context
    """
    chat_id = str(update.effective_chat.id)
    kyiv_tz = KYIV_TZ
    target_date = datetime.now(kyiv_tz)
    date_str = "сьогодні"

    # Check if we're analyzing yesterday's messages
    if context.args and context.args[0].lower() == "yesterday":
        target_date -= timedelta(days=1)
        date_str = "вчора"

    # Get the log path for the target date
    log_path = get_daily_log_path(chat_id, target_date)
    
    # Check if log file exists
    if not os.path.exists(log_path):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📊 Немає логів для аналізу за {date_str}. Спробуйте /analyze yesterday для аналізу вчорашніх повідомлень."
        )
        return

    # Extract messages from the log file
    messages_text = []
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(" - ", 6)  # Split up to 6 times, message is last
                if len(parts) == 7:
                    messages_text.append(parts[6])
                else:
                    general_logger.debug(f"Partial log line: {line}")
                    if len(parts) > 3:  # At least timestamp, name, level, and some content
                        messages_text.append(" ".join(parts[3:]))  # Take whatever's after level
    except Exception as e:
        error_logger.error(f"Error reading log file {log_path}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Помилка при читанні логів. Спробуйте пізніше."
        )
        return

    if not messages_text:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📊 Лог-файл за {date_str} порожній. Немає повідомлень для аналізу."
        )
        return

    # Send initial message
    status_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 Аналізую {len(messages_text)} повідомлень за {date_str}..."
    )

    try:
        # Generate and send summary using analyze response type
        summary = await gpt_response(
            "\n".join(messages_text),
            update,
            context,
            return_text=True,
            response_type="analyze"
        )
        
        # Update the status message with the summary
        await status_message.edit_text(
            text=f"📊 Аналіз повідомлень за {date_str} ({len(messages_text)} повідомлень):\n\n{summary}"
        )
    except Exception as e:
        error_logger.error(f"Error generating analysis: {e}")
        await status_message.edit_text(
            text="❌ Помилка при генерації аналізу. Спробуйте пізніше."
        )