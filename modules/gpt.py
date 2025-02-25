import openai
import logging
import os
from datetime import datetime, timedelta
import pytz
from typing import Optional
from modules.file_manager import get_daily_log_path, read_last_n_lines
from modules.logger import general_logger, chat_logger
from modules.helpers import get_daily_log_path
from const import OPENAI_API_KEY, USED_WORDS_FILE
if os.getenv("USE_EMPTY_PROMPTS", "false").lower() == "true":
    from modules.prompts_empty import GPT_PROMPTS  # Use empty prompts in GitHub Actions
else:
    from modules.prompts import GPT_PROMPTS  # Use actual prompts on the server

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient


# aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)
client = AsyncClient(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY

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
            max_tokens=500,
            temperature=0.7
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
    general_logger.error(f"Error in ask_gpt_command: {e}")
    if not return_text and update and update.message:
        await update.message.reply_text("Вибачте, сталася помилка.")
    raise

async def gpt_summary_function(messages):
    try:
        # Join the messages into a single string
        messages_text = "\n".join(messages)

        # Create the prompt for GPT
        prompt = f"Підсумуйте наступні повідомлення:\n\n{messages_text}\n\nПідсумок:"

        # Call the OpenAI API to get the summary
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GPT_PROMPTS["gpt_summary"]},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2750,  # Adjust the number of tokens for the summary as needed
            temperature=0.6  # Adjust the creativity of the response
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()  # Adjust based on actual response structure
        return summary
    except Exception as e:
        logging.error(f"Error in GPT summarization: {e}")
        return "Не вдалос згенерувати підсумок."
    

# Function to summarize the messages using GPT
async def summarize_messages(messages):
    try:
        summary = await gpt_summary_function(messages)
        return summary
    except Exception as e:
        logging.error(f"Error summarizing messages: {e}")
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
# Initialize used_words from file
used_words = load_used_words()

async def get_word_from_gpt(prompt: str) -> Optional[str]:
    """Get a single word response from GPT."""
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": GPT_PROMPTS["get_word_from_gpt"]},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error getting word from GPT: {e}")
        return None

async def random_ukrainian_word_command() -> Optional[str]:
    """Get a random Ukrainian word using GPT."""
    try:
        # Read used words
        with open(USED_WORDS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            used_words = set(word.strip() for word in content.split(',') if word.strip())
    except FileNotFoundError:
        used_words = set()

    # Include used words in the prompt
    used_words_str = ', '.join(used_words)
    prompt = f"""Згенеруй одне випадкове українське іменник в однині. 
    Дай тільки саме слово, без пояснень чи додаткового тексту.
    Слово має бути цікаве, креативне і незвичайне.
    
    Не використовуй ці слова: {used_words_str}"""

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            word = await get_word_from_gpt(prompt)
            if word:
                # Clean up the word
                word = word.strip().lower()
                
                # Validate word
                if (word not in used_words and 
                    3 <= len(word) <= 8 and 
                    word.isalpha()):
                    
                    # Add to used words
                    used_words.add(word)
                    with open(USED_WORDS_FILE, 'a', encoding='utf-8') as f:
                        f.write(f"{word},")
                    
                    return word
                else:
                    logging.debug(f"Word '{word}' already used or invalid, trying again. Attempt {attempt + 1}/{max_attempts}")
            
        except Exception as e:
            logging.error(f"Error getting word from GPT: {e}")
            continue

    return None

def clear_used_words():
    """Clears the history of used words."""
    global used_words
    used_words.clear()
    save_used_words(used_words)  # Save empty set to file
    general_logger.info("Used words history cleared manually")

def get_used_words_count() -> int:
    """Returns the number of used words."""
    return len(used_words)

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is an admin in the chat."""
    if not update.effective_chat:
        return False
    
    user_id = update.effective_user.id
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    return chat_member.status in ['creator', 'administrator']
