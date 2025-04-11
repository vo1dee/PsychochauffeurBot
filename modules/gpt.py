import openai
import logging
import os
from datetime import datetime, timedelta
import pytz
from typing import Optional
from modules.logger import general_logger, error_logger, get_daily_log_path
from modules.const import OPENAI_API_KEY, USED_WORDS_FILE
if os.getenv("USE_EMPTY_PROMPTS", "false").lower() == "true":
    from modules.prompts_empty import GPT_PROMPTS  # Use empty prompts in GitHub Actions
else:
    from modules.prompts import GPT_PROMPTS  # Use actual prompts on the server

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient


client = AsyncClient(api_key=OPENAI_API_KEY)

KYIV_TZ = pytz.timezone('Europe/Kiev')

GAME_STATE_FILE = 'data/game_state.json'



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
            model="gpt-4o-mini",
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
            model="gpt-4o",
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