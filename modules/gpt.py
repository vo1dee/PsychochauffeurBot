import openai
import logging
import os
import base64
from datetime import datetime, timedelta
import pytz
from typing import Optional
from modules.logger import general_logger, error_logger, get_daily_log_path, chat_logger
from modules.const import OPENAI_API_KEY
if os.getenv("USE_EMPTY_PROMPTS", "false").lower() == "true":
    from modules.prompts_empty import GPT_PROMPTS  # Use empty prompts in GitHub Actions
else:
    from modules.prompts import GPT_PROMPTS  # Use actual prompts on the server

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient
from io import BytesIO
from PIL import Image




client = AsyncClient(api_key=OPENAI_API_KEY)

KYIV_TZ = pytz.timezone('Europe/Kiev')

# (deprecated) GAME_STATE_FILE removed

async def analyze_image(image_bytes, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    """
    Analyze an image using GPT-4o-mini and log a brief description to chat logs without replying.
    """
    try:
        # Resize and compress image to optimize for API
        img = Image.open(BytesIO(image_bytes))
        max_size = 1024  # Max dimension
        
        # Resize if needed
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Save to BytesIO with compression
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        buffer.seek(0)
        
        # Encode image to base64
        base64_image = base64.b64encode(buffer.read()).decode('utf-8')
        
        # Call GPT-4o-mini with the image
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate a brief 2-3 sentence description of the image provided. Focus on main elements, objects, people, and context. Be concise and informative."},
                {"role": "user", "content": [
                    {"type": "text", "text": "What's in this image? Please describe briefly in 2-3 sentences."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            max_tokens=150,
            temperature=0.2
        )
        
        description = response.choices[0].message.content.strip()
        
        # Only log to chat log, don't reply to user
        if update and update.effective_chat:
            chat_id = update.effective_chat.id
            user_id = update.message.from_user.id if update.message.from_user else "unknown"
            username = update.message.from_user.username or f"ID:{user_id}" 
            
            # Add a prefix to make it clear this is an image description in the logs
            log_description = f"[IMAGE DESCRIPTION]: {description}"
            
            # Log to chat_logger so it appears in chat logs
            chat_logger.info(
                log_description,
                extra={'chat_id': chat_id, 'chattitle': update.effective_chat.title or f"Private_{chat_id}", 'username': username}
            )
            
            general_logger.info(f"Logged image description for user {username} in chat {chat_id}")
        
        # Still return the description if requested
        if return_text:
            return description
            
        return description
        
    except Exception as e:
        await handle_error(e, update, return_text)
        return "Error analyzing image."


async def gpt_response(prompt: str, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    try:
        chat_id = "unknown"
        last_messages = []
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            chat_id = update.effective_chat.id
            log_path = get_daily_log_path(chat_id)
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    last_messages = f.readlines()[-3:]

        context_prompt = ' '.join(last_messages)
        full_prompt = context_prompt + prompt

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": GPT_PROMPTS["gpt_response"] if not return_text else GPT_PROMPTS["gpt_response_return_text"]},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=666,
            temperature=0.6
        )

        response_text = response.choices[0].message.content.strip()
        if return_text:
            return response_text
        if update and hasattr(update, 'message') and update.message:
            await log_user_response(update, response_text)
        else:
            general_logger.warning("No valid update object; response not sent to chat.")
    except Exception as e:
        await handle_error(e, update, return_text)

async def ask_gpt_command(prompt: str, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    if isinstance(prompt, Update):
        update = prompt
        message_text = update.message.text
        command_parts = message_text.split(' ', 1)
        prompt = command_parts[1] if len(command_parts) > 1 else "Привіт!"
    return await gpt_response(prompt, update, context, return_text)

async def answer_from_gpt(prompt: str, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    """Ask GPT for a response."""
    return await gpt_response(prompt, update, context, return_text)

async def log_user_response(update, response_text):
    user_id = update.message.from_user.id if update.message.from_user else "unknown"
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    general_logger.info(f"Sending GPT response to user {user_id} in chat {chat_id}")
    await update.message.reply_text(response_text)

async def handle_error(e, update, return_text):
    from modules.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

    # Create context with relevant information
    context = {
        "function": "ask_gpt_command",
        "return_text": return_text,
        "user_id": update.effective_user.id if update and update.effective_user else None,
        "chat_id": update.effective_chat.id if update and update.effective_chat else None,
    }

    # Handle the error with our standardized system
    await ErrorHandler.handle_error(
        error=e,
        update=update,
        context=None,  # No need for context.bot in this case
        feedback_message="Вибачте, сталася помилка при зверненні до GPT.",
        propagate=True  # We still want to propagate this error
    )

async def gpt_summary_function(messages):
    try:
        # Join the messages into a single string
        messages_text = "\n".join(messages)

        # Create the prompt for GPT
        prompt = f"Підсумуйте наступні повідомлення:\n\n{messages_text}\n\nПідсумок:"

        # Call the OpenAI API to get the summary
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": GPT_PROMPTS["gpt_summary"]},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,  # Adjust the number of tokens for the summary as needed
            temperature=0.4  # Adjust the creativity of the response
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()  # Adjust based on actual response structure
        return summary
    except Exception as e:
        error_logger.error(f"Error in GPT summarization: {e}")
        return "Не вдалось згенерувати підсумок."


# Function to summarize the messages using GPT
async def summarize_messages(messages):
    try:
        summary = await gpt_summary_function(messages)
        return summary
    except Exception as e:
        error_logger.error(f"Error summarizing messages: {e}")
        return "Could not generate summary."

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    kyiv_tz = pytz.timezone('Europe/Kyiv')
    target_date = datetime.now(kyiv_tz)
    date_str = "сьогодні"

    if context.args and context.args[0].lower() == "yesterday":
        target_date -= timedelta(days=1)
        date_str = "вчора"

    log_path = get_daily_log_path(chat_id, target_date)
    if not os.path.exists(log_path):
        await context.bot.send_message(chat_id, f"Немає повідомлень для аналізу за {date_str}.")
        return

    messages_text = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(" - ", 6)  # Split up to 6 times, message is last
            if len(parts) == 7:
                messages_text.append(parts[6])
            else:
                general_logger.debug(f"Partial log line: {line}")
                if len(parts) > 3:  # At least timestamp, name, level, and some content
                    messages_text.append(" ".join(parts[3:]))  # Take whatever’s after level

    if not messages_text:
        await context.bot.send_message(chat_id, f"Не знайдено повідомлень для аналізу за {date_str}.")
        return

    summary = await gpt_summary_function(messages_text)
    await context.bot.send_message(
        chat_id,
        f"Підсумок повідомлень за {date_str} ({len(messages_text)} повідомлень):\n{summary}"
    )