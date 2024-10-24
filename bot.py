import asyncio
import os
import logging
import nest_asyncio
import random
import pytz
import requests
import imgkit
import csv
import openai




#import schedule
#import time
#import subprocess

from utils import remove_links, country_code_to_emoji, get_weather_emoji, get_city_translation, get_feels_like_emoji
from const import city_translations, domain_modifications, OPENWEATHER_API_KEY, DISCORD_WEBHOOK_URL, TOKEN, \
    SCREENSHOT_DIR, ALIEXPRESS_STICKER_ID
from openai import OpenAI, AsyncClient
from datetime import datetime, timedelta, time as dt_time
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ContextTypes
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Apply the patch to allow nested event loops
nest_asyncio.apply()


CSV_FILE = "user_locations.csv"



log_file_path = '/var/log/psychochauffeurbot/bot.log'
chatlog_file_path = '/var/log/psychochauffeurbot/bot_chat.log'

# Set up a rotating file handler for general logs
handler1 = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3)  # 5 MB per log file
handler1.setLevel(logging.INFO)
formatter1 = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler1.setFormatter(formatter1)

# Set up a rotating file handler for chat logs
handler2 = RotatingFileHandler(chatlog_file_path, maxBytes=5*1024*1024, backupCount=3)  # 5 MB per log file
handler2.setLevel(logging.INFO)
formatter2 = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(chat_id)s -  %(chattitle)s - %(username)s - %(message)s')
handler2.setFormatter(formatter2)

# Configure the logger for general logs
general_logger = logging.getLogger('bot_logger')
general_logger.setLevel(logging.INFO)
general_logger.addHandler(handler1)

# Configure a separate logger for chat logs
chat_logger = logging.getLogger('bot_chat_logger')
chat_logger.setLevel(logging.INFO)
chat_logger.addHandler(handler2)


# Set a higher logging level for the 'httpx' logger to avoid logging all requests
logging.getLogger("httpx").setLevel(logging.WARNING)


# Load environment variables from .env file
load_dotenv()

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Load the OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


# aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)
client = AsyncClient(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY

bot = ApplicationBuilder().token(TOKEN).build()

# Set local timezone
LOCAL_TZ = pytz.timezone('Europe/Kyiv')



async def start(update: Update, context: CallbackContext):
    general_logger.info(f"Processing /start command from user {update.message.from_user.id} in chat {update.effective_chat.id}")
    await update.message.reply_text("Hello! Send me TikTok, Twitter, or Instagram links, and I will modify them for you!")

# Function to fetch weather data from OpenWeatherMap
async def get_weather(city: str) -> str:
    # Same as before, fetching weather data from OpenWeatherMap API
    city = get_city_translation(city)
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "uk"
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("cod") != 200:
            general_logger.error(f"Weather API error response: {data}")
            return f"Error: {data.get('message', 'Unknown error')}"

        weather = data.get("weather")
        if not weather:
            return "Failed to retrieve weather data: Weather data not available"

        city_name = data.get("name", "Unknown city")
        country_code = data["sys"].get("country", "Unknown country")
        weather_id = weather[0].get("id", 0)
        weather_description = weather[0].get("description", "No description")
        temp = round(data["main"].get("temp", "N/A"))
        feels_like = round(data["main"].get("feels_like", "N/A"))

        weather_emoji = get_weather_emoji(weather_id)
        country_flag = country_code_to_emoji(country_code)
        feels_like_emoji = get_feels_like_emoji(feels_like)

        return (f"Погода в {city_name}, {country_code} {country_flag}:\n"
                f"{weather_emoji} {weather_description.capitalize()}\n"
                f"🌡 Температура: {temp}°C\n"
                f"{feels_like_emoji} Відчувається як: {feels_like}°C")
    except Exception as e:
        general_logger.error(f"Error fetching weather data: {e}")
        return f"Failed to retrieve weather data: {str(e)}"


def save_user_location(user_id: int, city: str):
    """Save the user's last used city to a CSV file."""
    rows = []
    updated = False
    try:
        # Read existing data
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            rows = list(reader)

        # Update if user exists
        for row in rows:
            if int(row[0]) == user_id:
                row[1] = city
                row[2] = datetime.now().isoformat()
                updated = True

        # Add new entry if user doesn't exist
        if not updated:
            rows.append([user_id, city, datetime.now().isoformat()])

        # Write back to CSV
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(rows)
    except FileNotFoundError:
        # If CSV doesn't exist, create it and add the user's data
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([user_id, city, datetime.now().isoformat()])

def get_last_used_city(user_id: int) -> str:
    """Retrieve the last used city for the user from the CSV file."""
    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if int(row[0]) == user_id:
                    return row[1]
    except FileNotFoundError:
        # If the CSV file doesn't exist, return None
        return None
    return None

async def cat_command(update: Update, context: CallbackContext):
    try:
        response = requests.get('https://api.thecatapi.com/v1/images/search')
        if response.status_code == 200:
            cat_data = response.json()
            cat_image_url = cat_data[0]['url']
            await update.message.reply_photo(cat_image_url)
        else:
            await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        general_logger.error(f"Error fetching cat image: {e}")


def contains_trigger_words(message_text):
    triggers = ["5€", "€5", "5 євро", "5 єуро", "5 €", "Ы", "ы", "ъ", "Ъ", "Э", "э", "Ё", "ё"]
    return any(trigger in message_text for trigger in triggers)

async def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.text:
        message_text = update.message.text
        chat_id = update.message.chat_id
        username = update.message.from_user.username
        chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"
        user_name = update.message.from_user.username if update.message.from_user.username else "Unknown User"


        chat_logger.info(f"{message_text}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id} )

        # Check for trigger words in the message
        if contains_trigger_words(message_text):
            await restrict_user(update, context)
            return

        if any(domain in message_text for domain in ["aliexpress.com/item/", "a.aliexpress.com/"]):
            # Reply to the message containing the link by sending a sticker
            await update.message.reply_sticker(sticker=ALIEXPRESS_STICKER_ID)

        # Initialize modified_links list
        modified_links = []

        # Check for specific domain links and modify them
        if any(domain in message_text for domain in ["tiktok.com", "twitter.com", "x.com", "instagram.com"]):
            links = message_text.split()  # This initializes 'links' only if the condition is true
            for link in links:
                # Check if the link is already modified (exists in the modified domains)
                if any(modified_domain in link for modified_domain in domain_modifications.values()):
                    break
                # Otherwise, proceed to modify the link
                for domain, modified_domain in domain_modifications.items():
                    if domain in link:
                        modified_link = link.replace(domain, modified_domain)
                        modified_links.append(modified_link)
                        break

        # If there are modified links, send the modified message
        if modified_links:
            cleaned_message_text = remove_links(message_text)
            modified_message = "\n".join(modified_links)
            final_message = f"@{username}💬: {cleaned_message_text}\n\nModified links:\n{modified_message}"

            # Check if the original message is a reply
            if update.message.reply_to_message:
                original_message_id = update.message.reply_to_message.message_id
                # Send the modified message as a reply to the original message
                await context.bot.send_message(chat_id=chat_id, text=final_message, reply_to_message_id=original_message_id)
            else:
                # If not a reply, send the modified message normally
                await context.bot.send_message(chat_id=chat_id, text=final_message)

            general_logger.info(f"Sent modified message: {final_message}")

            # Delete the original message (your message containing the link)
            await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            general_logger.info("Deleted the original message containing the link.")

async def restrict_user(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user_id = update.message.from_user.id
    username = update.message.from_user.username  # Get the username for the reply message

    # Check if the user is the chat owner or an admin
    chat_member = await context.bot.get_chat_member(chat.id, user_id)
    if chat_member.status in ["administrator", "creator"]:
        general_logger.info("Cannot restrict an admin or chat owner.")
        return

    if chat.type == "supergroup":
        try:
            restrict_duration = random.randint(1, 15)  # Restriction duration in minutes
            permissions = ChatPermissions(can_send_messages=False)

            # Get current time in EEST
            until_date = datetime.now(LOCAL_TZ) + timedelta(minutes=restrict_duration)

            # Restrict user in the chat
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )

            # Notify user with a custom sticker
            sticker_id = "CAACAgQAAxkBAAEt8tNm9Wc6jYEQdAgQzvC917u3e8EKPgAC9hQAAtMUCVP4rJSNEWepBzYE"
            await update.message.reply_text(f"Вас запсихопаркували на {restrict_duration} хвилин. Ви не можете надсилати повідомлення.")
            await context.bot.send_sticker(chat_id=chat.id, sticker=sticker_id)
            general_logger.info(f"Restricted user {user_id} for {restrict_duration} minutes.")

        except Exception as e:
            general_logger.error(f"Failed to restrict user: {e}")
    else:
        await update.message.reply_text("This command is only available in supergroups.")

async def handle_sticker(update: Update, context: CallbackContext):
    # Get unique ID of the sticker
    sticker_id = update.message.sticker.file_unique_id
    username = update.message.from_user.username  # Getting the sender's username

    general_logger.debug(f"Received sticker with file_unique_id: {sticker_id}")

    # Check if the sticker ID matches the specific stickers you want to react to
    if sticker_id == "AgAD6BQAAh-z-FM":  # Replace with your actual unique sticker ID
        logging.info(f"Matched specific sticker from {username}, restricting user.")
        await restrict_user(update, context)
    else:
        general_logger.info(f"Sticker ID {sticker_id} does not match the trigger sticker.")


# Command handler for /weather <city>
async def weather(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if context.args:
        city = " ".join(context.args)
        # Save the user's location to the CSV file
        save_user_location(user_id, city)
        weather_info = await get_weather(city)
        if update.message:
            await update.message.reply_text(weather_info)
    else:
        # Try to get the last saved city for the user
        city = get_last_used_city(user_id)
        if city:
            weather_info = await get_weather(city)
            if update.message:
                await update.message.reply_text(weather_info)
        else:
            await update.message.reply_text("Будь ласка, вкажіть назву міста або задайте його спочатку.")

# Define the log rotation function
def rotate_words(message: str, num_words: int = 6) -> str:
    """Rotate a specified number of words in the message."""
    words = message.split()
    if len(words) < num_words:
        num_words = len(words)

    # Select random indices to rotate
    indices = random.sample(range(len(words)), num_words)
    selected_words = [words[i] for i in indices]

    # Shuffle the selected words
    random.shuffle(selected_words)

    # Update the original list with shuffled words
    for idx, original_idx in enumerate(indices):
        words[original_idx] = selected_words[idx]

    return ' '.join(words)

# Function to rotate chat logs daily
def rotate_chat_logs():
    """Rotate words in chat logs daily."""
    try:
        # Open the chat log file for reading
        with open(chatlog_file_path, 'r') as file:
            lines = file.readlines()

        # Rotate words in each log entry
        rotated_lines = []
        for line in lines:
            # Example: Extract the message from the log and rotate words
            # Assume the format is: '2023-10-14 - chat_name - user_name - message'
            parts = line.strip().split(' - ')
            if len(parts) >= 4:
                message = parts[-1]
                rotated_message = rotate_words(message)
                parts[-1] = rotated_message
                rotated_lines.append(' - '.join(parts))

        # Write the rotated entries back to the log file
        with open(chatlog_file_path, 'w') as file:
            file.writelines(rotated_lines)

        general_logger.info("Chat logs rotated successfully.")
    except Exception as e:
        general_logger.error(f"Error rotating chat logs: {e}")

# Function to schedule the daily log rotation
async def schedule_log_rotation():
    """Schedules the log rotation to occur at midnight each day."""
    local_tz = pytz.timezone('Europe/Kyiv')
    now = datetime.now(local_tz)
    next_rotation = datetime.combine(now.date() + timedelta(days=1), dt_time.min, tzinfo=local_tz)

    # Calculate the time until the next rotation
    time_until_rotation = (next_rotation - now).total_seconds()

    # Schedule the rotation task
    await asyncio.sleep(time_until_rotation)
    rotate_chat_logs()

    # Reschedule the rotation for the next day
    await schedule_log_rotation()

# Screenshot command to capture the current state of a webpage
async def screenshot_command(update, context):
    try:
        # Make sure to await the coroutine and get the file path
        screenshot_path = await take_screenshot()

        # Open the file path correctly
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)
    except Exception as e:
        # Log the error or send a message indicating the issue
        general_logger.info(f"Screenshot taken at {datetime.now()}")


async def ask_gpt_command(update: Update, context: CallbackContext):
    """Handles the /gpt command to query GPT with a question."""
    if not context.args:
        await update.message.reply_text("Please provide a question, e.g., /gpt What is the weather?")
        return

    question = " ".join(context.args)
    try:
        # Send the question to GPT
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "system", "content": (
                    "If the user's request appears to be in Russian, respond in Ukrainian instead. "
                    "Do not reply in Russian in any circumstance."
                )},
                {"role": "user", "content": question}
            ],
            max_tokens=700,
            temperature=0.7
        )

        # Extract GPT's response
        gpt_reply = response.choices[0].message.content
        await update.message.reply_text(gpt_reply)

        # Log the interaction
        chat_title = update.message.chat.title if update.message.chat.title else "Private Chat"
        user_name = update.message.from_user.username if update.message.from_user.username else "Unknown User"
        chat_id = update.message.chat_id if update.message.chat_id else "Unknown chat"
        chat_logger.info(f"User {update.message.from_user.username} asked GPT: {question}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id})
        chat_logger.info(f"GPT's response: {gpt_reply}", extra={'chattitle': chat_title, 'username': user_name, 'chat_id': chat_id})

    except Exception as e:
        general_logger.error(f"Failed to communicate with GPT: {e}")
        await update.message.reply_text("Sorry, I couldn't get an answer right now.")

# Define your screenshot function
async def take_screenshot():
    adjusted_time = datetime.now(pytz.timezone('Europe/Kyiv'))
    date_str = adjusted_time.strftime('%Y-%m-%d')
    screenshot_path = os.path.join(SCREENSHOT_DIR, f'flares_{date_str}.png')

    # Check if the screenshot for the adjusted date already exists
    if os.path.exists(screenshot_path):
        general_logger.info(f"Screenshot for today already exists: {screenshot_path}")
        return screenshot_path

    config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
    print(f"Screenshot taken at {datetime.now()}")
    try:
        # Run from_url in a non-blocking way using asyncio.to_thread
        await asyncio.to_thread(imgkit.from_url, 'https://api.meteoagent.com/widgets/v1/kindex', screenshot_path, config=config)
        general_logger.info(f"Screenshot taken and saved to: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        general_logger.error(f"Error taking screenshot: {e}")
        return None



# Function to read the last n lines of the chat log for a specific chat ID
def read_last_n_lines(file_path, chat_id, n=100):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        
        # Filter lines by chat_id (converting chat_id to str as it appears in the log)
        filtered_lines = [line for line in lines if f' {chat_id} ' in line]

        # Debugging output to verify filtering
        print(f"Total lines read: {len(lines)}")  # Total lines in log
        print(f"Filtered lines count for chat_id {chat_id}: {len(filtered_lines)}")  # Filtered lines

        # Return the last n messages for the specific chat
        return filtered_lines[-n:] if len(filtered_lines) >= n else filtered_lines



# Function to summarize the messages using GPT
async def summarize_messages(messages):
    try:
        summary = await gpt_summary_function(messages)
        return summary
    except Exception as e:
        logging.error(f"Error summarizing messages: {e}")
        return "Could not generate summary."



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
                {"role": "user", "content": prompt}
            ],
            max_tokens=700,  # Adjust the number of tokens for the summary as needed
            temperature=0.7  # Adjust the creativity of the response
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()  # Adjust based on actual response structure
        return summary
    except Exception as e:
        logging.error(f"Error in GPT summarization: {e}")
        return "Не вдалося згенерувати підсумок."



# Command handler for /analyze
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    n = 250  # Change this to 500 if you want to read 500 lines
    log_file_path = '/var/log/psychochauffeurbot/bot_chat.log'  # Update this path

    try:
        # Read the last n lines specific to the chat ID
        messages = read_last_n_lines(log_file_path, chat_id, n)

        # Debugging output
        print(f"Messages to summarize: {messages}")

        if not messages:
            await context.bot.send_message(chat_id, "Не знайдено повідомлень для аналізу.")
            return
        
        # Extract just the message text from the log lines
        messages_text = [line.split(" - ")[-1].strip() for line in messages]

        # Summarize the messages in Ukrainian
        summary = await gpt_summary_function(messages_text)

        # Send the summary back to the chat
        await context.bot.send_message(chat_id, f"Підсумок останніх {n} повідомлень:\n{summary}")
    except Exception as e:
        logging.error(f"Error in /analyze command: {e}")
        await context.bot.send_message(chat_id, "Виникла помилка при аналізі повідомлень.")




def schedule_screenshot():
    # Schedule the coroutine using `asyncio.create_task`.
    asyncio.create_task(take_screenshot())

async def schedule_task():
    # Set the time for 01:00 Kyiv time every day
    kyiv_time = pytz.timezone('Europe/Kyiv')
    schedule_time = dt_time(1, 0)  # 1 AM Kyiv time
    last_run_date = None  # To keep track of the last run date

    while True:
        # Get the current time in Kyiv timezone
        now = datetime.now(kyiv_time)

        # Check if it's past 1 AM and the task hasn't been run today
        if now.time() >= schedule_time and last_run_date != now.date():
            await take_screenshot()
            last_run_date = now.date()  # Update the last run date to today

        # Sleep for an hour before checking again
        await asyncio.sleep(3600)

# Main function to initialize and run the bot
async def main():
    # Add handlers outside the reminders loop
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message_for_links))
    bot.add_handler(CommandHandler('flares', screenshot_command))
    bot.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))  # Add sticker handler
    weather_handler = CommandHandler("weather", weather)
    bot.add_handler(weather_handler)
    bot.add_handler(CommandHandler('cat', cat_command))
    bot.add_handler(CommandHandler("gpt", ask_gpt_command))
    bot.add_handler(CommandHandler("analyze", analyze_command))


    asyncio.create_task(schedule_task())
    asyncio.create_task(schedule_log_rotation())


    # Start the bot
    await bot.run_polling()
    await bot.idle()
    # await schedule_task()  # Await the coroutine

# Function to run the bot, handles event loop issues
async def run_bot():
    await main()

if __name__ == '__main__':
    # Create a new event loop
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(main())