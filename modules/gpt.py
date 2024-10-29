import openai
import logging
import os

from modules.file_manager import general_logger, chat_logger, read_last_n_lines, get_daily_log_path, load_used_words, save_used_words
from const import OPENAI_API_KEY

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from openai import AsyncClient


# aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)
client = AsyncClient(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY



async def ask_gpt_command(context_text: str, update: Update, context: CallbackContext):
    """Handles the GPT query with conversation context."""
    if not context_text:
        await update.message.reply_text("Please provide a question or reply to my message.")
        return

    try:
        # Send the question to GPT
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Do not hallucinate."
                    "Do not make up fictional information."
                    "If the user's request appears to be in Russian, respond in Ukrainian instead."
                    "Do not reply in Russian in any circumstance."
                )},
                {"role": "user", "content": context_text}
            ],
            max_tokens=500,
            temperature=0.7
        )

        # Extract GPT's response
        gpt_reply = response.choices[0].message.content
        await update.message.reply_text(gpt_reply)

        # Log the interaction
        chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"
        user_name = update.message.from_user.username if update.message.from_user.username else "Unknown User"
        chat_id = update.message.chat_id if update.message.chat_id else "Unknown chat"
        
        # Improved logging for better clarity
        chat_logger.info(f"User {user_name} asked GPT: {context_text}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id})
        chat_logger.info(f"GPT's response: {gpt_reply}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id})

    except Exception as e:
        general_logger.error(f"Failed to communicate with GPT: {e}")
        await update.message.reply_text("Sorry, I couldn't get an answer right now.")




async def gpt_summary_function(messages):
    try:
        # Join the messages into a single string
        messages_text = "\n".join(messages)

        # Create the prompt for GPT
        prompt = f"Підсумуйте наступні повідомлення:\n\n{messages_text}\n\nПідсумок:"

        # Call the OpenAI API to get the summary
        response = await client.chat.completions.create(  # Ensure this matches your library's documentation
            model="gpt-4o",  # or any other model you prefer
            messages=[
                {"role": "system", "content": (
                    "Do not hallucinate."
                    "Do not made up information."
                    "If the user's request appears to be in Russian, respond in Ukrainian instead."
                    "Do not reply in Russian in any circumstance."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=750,  # Adjust the number of tokens for the summary as needed
            temperature=0.7  # Adjust the creativity of the response
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()  # Adjust based on actual response structure
        return summary
    except Exception as e:
        logging.error(f"Error in GPT summarization: {e}")
        return "Не вдалося згенерувати підсумок."
    

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
    chat_id = update.effective_chat.id
    today_log_path = get_daily_log_path()

    try:
        # Check if today's log file exists
        if not os.path.exists(today_log_path):
            await context.bot.send_message(chat_id, "Немає повідомлень для аналізу за сьогодні.")
            return

        # Read today's messages for the specific chat
        with open(today_log_path, 'r', encoding='utf-8') as f:
            all_messages = f.readlines()
        
        # Filter messages for the specific chat_id
        chat_messages = [
            line for line in all_messages 
            if f" - {chat_id} - " in line  # Adjust this based on your log format
        ]

        if not chat_messages:
            await context.bot.send_message(chat_id, "Не знайдено повідомлень для аналізу за сьогодні.")
            return
        
        # Extract just the message text from the log lines
        messages_text = [line.split(" - ")[-1].strip() for line in chat_messages]

        # Summarize the messages in Ukrainian
        summary = await gpt_summary_function(messages_text)

        # Send the summary back to the chat
        await context.bot.send_message(
            chat_id, 
            f"Підсумок повідомлень за сьогодні ({len(messages_text)} повідомлень):\n{summary}"
        )
    except Exception as e:
        logging.error(f"Error in /analyze command: {e}")
        await context.bot.send_message(chat_id, "Виникла помилка при аналізі повідомлень.")



# Initialize used_words from file
used_words = load_used_words()

async def random_ukrainian_word_command():
    """Fetches a random Ukrainian word from GPT that hasn't been used before."""
    global used_words
    
    MAX_ATTEMPTS = 5  # Maximum attempts to get a new word
    
    for attempt in range(MAX_ATTEMPTS):
        try:
            prompt = "Give me one random Ukrainian word that is common and easy to guess."
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Do not hallucinate."
                        "Do not make up fictional information."
                        "If the user's request appears to be in Russian, respond in Ukrainian instead."
                        "Do not reply in Russian in any circumstance."
                        "Respond with only one Ukrainian word, nothing else."
                    )},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3,
                temperature=0.9
            )
            word = response.choices[0].message.content.strip().lower()
            
            # Check if word is valid and not used before
            if word and word not in used_words:
                used_words.add(word)
                save_used_words(used_words)  # Save after adding new word
                general_logger.debug(f"New word added: {word}. Total used: {len(used_words)}")
                return word
            
            general_logger.debug(f"Word '{word}' already used or invalid, trying again. Attempt {attempt + 1}/{MAX_ATTEMPTS}")
            
        except Exception as e:
            general_logger.error(f"Error fetching random Ukrainian word: {e}")
    
    # If we've exhausted attempts or have too many used words, clear history and try once more
    if len(used_words) > 1000:  # Arbitrary limit
        clear_used_words()
        general_logger.info("Used words history cleared due to size limit")
    
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