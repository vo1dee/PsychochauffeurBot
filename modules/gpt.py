import openai
import logging
import os
from datetime import datetime, timedelta
import pytz
from typing import Optional

from modules.file_manager import general_logger, chat_logger, read_last_n_lines, get_daily_log_path, load_used_words, save_used_words
from const import OPENAI_API_KEY, USED_WORDS_FILE

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient


# aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)
client = AsyncClient(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY

KYIV_TZ = pytz.timezone('Europe/Kiev')

GAME_STATE_FILE = 'data/game_state.json'



async def ask_gpt_command(prompt: str, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    """Ask GPT for a response."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "If the user's request appears to be in Russian, respond in Ukrainian instead."
                    "Do not reply in Russian in any circumstance."
                    "You answer like a crazy driver but stick to the point of the conversation."
                ) if not return_text else "You are a helpful assistant that generates single Ukrainian words."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        response_text = response.choices[0].message.content.strip()

        if return_text:
            return response_text

        if update and context:
            await update.message.reply_text(response_text)

    except Exception as e:
        general_logger.error(f"Error in ask_gpt_command: {e}")
        if not return_text and update:
            await update.message.reply_text("Вибачте, сталася помилка.")
        raise


async def answer_from_gpt(prompt: str, update: Update = None, context: CallbackContext = None, return_text: bool = False):
    """Ask GPT for a response."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "If the user's request appears to be in Russian, respond in Ukrainian instead."
                    "Do not reply in Russian in any circumstance."
                    "You answer like a crazy driver but stick to the point of the conversation."
                ) if not return_text else "You are a helpful assistant that generates single Ukrainian words."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        response_text = response.choices[0].message.content.strip()

        if return_text:
            return response_text

        if update and context:
            await update.message.reply_text(response_text)

    except Exception as e:
        general_logger.error(f"Error in ask_gpt_command: {e}")
        if not return_text and update:
            await update.message.reply_text("Вибачте, сталася помилка.")
        raise



async def gpt_summary_function(messages):
    try:
        # Join the messages into a single string
        messages_text = "\n".join(messages)

        # Create the prompt for GPT
        prompt = f"Підсумуйте наступні повідомлення:\n\n{messages_text}\n\nПідсумок:"

        # Call the OpenAI API to get the summary
        response = await client.chat.completions.create(  # Ensure this matches your library's documentation
            model="gpt-4o-mini",  # or any other model you prefer
            messages=[
                {"role": "system", "content": (
                    "Do not hallucinate."
                    "Do not made up information."
                    "If the user's request appears to be in Russian, respond in Ukrainian instead."
                    "Do not reply in Russian in any circumstance."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1750,  # Adjust the number of tokens for the summary as needed
            temperature=0.7  # Adjust the creativity of the response
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

# Command handler for /analyze
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyzes chat messages. By default analyzes today's messages."""
    chat_id = update.effective_chat.id
    
    # Default to today with Kyiv timezone
    target_date = datetime.now(KYIV_TZ)
    date_str = "сьогодні"

    # Check for "yesterday" argument
    if context.args and context.args[0].lower() == "yesterday":
        target_date = datetime.now(KYIV_TZ) - timedelta(days=1)
        date_str = "вчора"
        general_logger.debug(f"Yesterday date with timezone: {target_date}")

    log_path = get_daily_log_path(target_date)  # Pass the target_date parameter
    general_logger.debug(f"Looking for log file at: {log_path}")

    try:
        # Check if log file exists
        if not os.path.exists(log_path):
            general_logger.debug(f"Log file not found at: {log_path}")
            # List all files in logs directory for debugging
            log_dir = os.path.dirname(log_path)
            if os.path.exists(log_dir):
                files = os.listdir(log_dir)
                general_logger.debug(f"Files in log directory: {files}")
            
            await context.bot.send_message(
                chat_id, 
                f"Немає повідомлень для аналізу за {date_str}."
            )
            return

        # Read messages for the specified date
        with open(log_path, 'r', encoding='utf-8') as f:
            all_messages = f.readlines()
        general_logger.debug(f"Total messages in log: {len(all_messages)}")
        
        # Filter messages for the specific chat_id
        chat_messages = [
            line for line in all_messages 
            if f" - {chat_id} - " in line
        ]
        general_logger.debug(f"Messages filtered for chat_id {chat_id}: {len(chat_messages)}")

        if not chat_messages:
            general_logger.debug(f"No messages found for chat_id {chat_id}")
            await context.bot.send_message(
                chat_id, 
                f"Не знайдено повідомлень для аналізу за {date_str}."
            )
            return
        
        # Extract just the message text from the log lines
        messages_text = [line.split(" - ")[-1].strip() for line in chat_messages]
        general_logger.debug(f"Extracted {len(messages_text)} message texts")
        general_logger.debug(f"First message sample: {messages_text[0] if messages_text else 'No messages'}")

        # Summarize the messages in Ukrainian
        general_logger.debug("Calling GPT for summary")
        summary = await gpt_summary_function(messages_text)
        general_logger.debug(f"Received summary of length: {len(summary) if summary else 0}")

        # Send the summary back to the chat
        await context.bot.send_message(
            chat_id, 
            f"Підсумок повідомлень за {date_str} ({len(messages_text)} повідомлень):\n{summary}"
        )
    except Exception as e:
        general_logger.error(f"Error in /analyze command: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id, 
            "Виникла помилка при аналізі повідомлень."
        )



# Initialize used_words from file
used_words = load_used_words()

async def get_word_from_gpt(prompt: str) -> Optional[str]:
    """Get a single word response from GPT."""
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates single creative Ukrainian word. Respond only with the word itself, without any additional text or punctuation."},
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