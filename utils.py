import re
import requests
import imgkit
import pytz
import os
import asyncio
from datetime import datetime, time as dt_time, timedelta
import glob

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes
from modules.file_manager import general_logger
from const import weather_emojis, city_translations, feels_like_emojis, SCREENSHOT_DIR
from modules.gpt import random_ukrainian_word_command, clear_used_words, get_used_words_count

game_state = {}

# Text processing utilities
def remove_links(text: str) -> str:
    """Remove all URLs from given text."""
    return re.sub(r'http[s]?://\S+', '', text).strip()

# Weather-related utilities
def country_code_to_emoji(country_code: str) -> str:
    """Convert country code to flag emoji."""
    return ''.join(chr(127397 + ord(c)) for c in country_code.upper())

def get_weather_emoji(weather_id: int) -> str:
    """Get weather emoji based on weather ID."""
    return next((emoji for id_range, emoji in weather_emojis.items() 
                if weather_id in id_range), '🌈')

def get_feels_like_emoji(feels_like: float) -> str:
    """Get emoji based on 'feels like' temperature."""
    for temp_range, emoji in feels_like_emojis.items():
        if feels_like >= temp_range.start and feels_like < temp_range.stop:
            return emoji
    return '🌈'

def get_city_translation(city: str) -> str:
    """Get city translation from dictionary."""
    normalized = city.lower().replace(" ", "")
    return city_translations.get(normalized, city)

# Cat API command
async def cat_command(update: Update, context: CallbackContext) -> None:
    """Send random cat image."""
    try:
        response = requests.get('https://api.thecatapi.com/v1/images/search')
        if response.status_code == 200:
            cat_image_url = response.json()[0]['url']
            await update.message.reply_photo(cat_image_url)
        else:
            await update.message.reply_text('Sorry, I could not fetch a cat image at the moment.')
    except Exception as e:
        general_logger.error(f"Error fetching cat image: {e}")

# Screenshot functionality
class ScreenshotManager:
    _instance = None  # Singleton instance
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.timezone = pytz.timezone('Europe/Kyiv')
            self.schedule_time = dt_time(1, 0)  # 1 AM Kyiv time
            config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
            self.options = {
                'quality': '100',
                'format': 'png',
                'width': '1920',  # Set a fixed width
                'enable-javascript': None,
                'javascript-delay': '1000',  # Wait 1 second for JavaScript
                'custom-header': [
                    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
                ]
            }
            self._initialized = True

    def get_screenshot_path(self) -> str:
        """Generate screenshot path for current date."""
        kyiv_time = datetime.now(self.timezone)
        date_str = kyiv_time.strftime('%Y-%m-%d')
        return os.path.join(SCREENSHOT_DIR, f'flares_{date_str}_kyiv.png')

    def get_latest_screenshot(self) -> str | None:
        """Get the path of today's screenshot if it exists."""
        kyiv_time = datetime.now(self.timezone)
        screenshot_path = self.get_screenshot_path()
        if os.path.exists(screenshot_path):
            return screenshot_path
        return None

    async def take_screenshot(self, url, output_path):
        try:
            options = {
                'quality': '100',
                'format': 'png',
                'width': '1024',  # Changed from 1920 to 1024 pixels
                'enable-javascript': None,
                'javascript-delay': '1000',
                'custom-header': [
                    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
                ]
            }
            
            config = imgkit.config(wkhtmltoimage='/usr/bin/wkhtmltoimage')
            imgkit.from_url(url, output_path, options=options, config=config)
            return output_path
        except Exception as e:
            general_logger.error(f"Error taking screenshot: {str(e)}")
            return False

    async def schedule_task(self) -> None:
        """Schedule daily screenshot task."""
        while True:
            # Get current time in Kyiv timezone
            kyiv_now = datetime.now(self.timezone)
            
            # Create target time for today at 1 AM Kyiv time
            target_time = self.timezone.localize(
                datetime.combine(kyiv_now.date(), self.schedule_time)
            )
            
            # If it's already past 1 AM Kyiv time today, schedule for tomorrow
            if kyiv_now > target_time:
                target_time += timedelta(days=1)
            
            # Convert target time to server's local time for sleep calculation
            server_now = datetime.now(pytz.UTC).astimezone()  # Get server's local time
            target_time_local = target_time.astimezone(server_now.tzinfo)
            
            # Calculate sleep duration based on server time
            sleep_seconds = (target_time_local - server_now).total_seconds()
            general_logger.info(f"Current server time: {server_now}")
            general_logger.info(f"Current Kyiv time: {kyiv_now}")
            general_logger.info(f"Next screenshot scheduled for: {target_time} (Kyiv time)")
            general_logger.info(f"Sleep duration: {sleep_seconds} seconds")
            
            # Sleep until next run
            await asyncio.sleep(sleep_seconds)
            await self.take_screenshot('https://api.meteoagent.com/widgets/v1/kindex', self.get_screenshot_path())

# Command handlers
async def screenshot_command(update: Update, context: CallbackContext) -> None:
    """Handle /screenshot command."""
    try:
        manager = ScreenshotManager()
        # Try to get today's existing screenshot first
        screenshot_path = manager.get_latest_screenshot()
        
        # If no screenshot exists for today, take a new one
        if not screenshot_path:
            screenshot_path = await manager.take_screenshot(
                'https://api.meteoagent.com/widgets/v1/kindex', 
                manager.get_screenshot_path()
            )
            
        if screenshot_path:
            with open(screenshot_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, 
                    photo=photo
                )
    except Exception as e:
        general_logger.error(f"Error in screenshot command: {e}")

# Keep only one version of schedule_task as a classmethod
@classmethod
async def schedule_task(cls):
    """Main scheduling task."""
    manager = cls()
    await manager.schedule_task()


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the word game by fetching a random Ukrainian word."""
    chat_id = update.effective_chat.id
    word = await random_ukrainian_word_command()
    if word:
        game_state[chat_id] = word
        await update.message.reply_text(f"Гра почалася! Вгадайте українське слово.")
        
        # Log the game start and print the game state for debugging
        general_logger.info(f"Game started for chat_id {chat_id} with word: {word}")
        general_logger.info(f"Game active in chat {chat_id}. Random word: {random_word}")
        # print(f"Current game state: {game_state}")  # Debug print
    else:
        await update.message.reply_text("На жаль, я не змогла запустити гру в цьому чаті.")
        general_logger.error(f"Failed to start game for chat_id {chat_id}")

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ends the current word game in the chat."""
    chat_id = update.effective_chat.id
    
    if chat_id in game_state:
        word = game_state[chat_id]
        del game_state[chat_id]
        await update.message.reply_text(f"Гру завершено! Слово було: '{word}'")
        general_logger.debug(f"Game manually ended in chat {chat_id}")
    else:
        await update.message.reply_text("В цьому чаті немає активної гри.")
        general_logger.debug(f"Attempted to end non-existent game in chat {chat_id}")

async def clear_words_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears the history of used words in the game."""
    if not await is_admin(update, context):
        await update.message.reply_text("Ця команда доступна тільки для адміністраторів.")
        return  
    
    current_count = get_used_words_count()
    clear_used_words()
    await update.message.reply_text(
        f"Історію використаних слів очищено. Було видалено {current_count} слів."
    )
