"""
Basic command handlers for the PsychoChauffeur bot.

Contains handlers for fundamental commands like start, help, and ping.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from modules.logger import general_logger

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.message:
        return
        
    welcome_text = (
        "🤖 **PsychoChauffeur Bot**\n\n"
        
        "📊 **Аналіз повідомлень:**\n"
        "• `/analyze` - аналіз сьогоднішніх повідомлень\n"
        "• `/analyze last 50 messages` - останні повідомлення\n"
        "• `/analyze date 15-01-2024` - за конкретну дату\n"
        "• Підтримка форматів: DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY\n\n"
        
        "🌞 **Космічна погода:**\n"
        "• `/flares` - актуальний знімок сонячних спалахів\n"
        "• `/gm` - геомагнітна активність\n\n"
        
        "🎥 **Завантаження відео:**\n"
        "• TikTok, YouTube Shorts, Twitter, Vimeo, Reddit, Twitch\n"
        "• Просто надішліть посилання на відео\n\n"
        
        "🔗 **Обробка посилань:**\n"
        "• Оптимізація посилань AliExpress\n"
        "• Модифікація для обмежених доменів\n\n"
        
        "🌤️ **Інші функції:**\n"
        "• `/weather [місто]` - прогноз погоди\n"
        "• `/cat` - випадкове фото котика\n"
        "• `/remind` - нагадування\n"
        "• `/mute @username` - заборонити писати користувачу (тільки для адмінів)\n"
        "• `/unmute @username` - дозволити писати користувачу (тільки для адмінів)\n"
        "• `/help` - детальна довідка\n\n"
        
        "❓ **Питання або проблеми?**\n"
        "Зверніться до @vo1dee"
    )
    await update.message.reply_text(welcome_text)
    
    # Add a static test button for callback debugging
    await update.message.reply_text(
        "Test callback button:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Test Callback", callback_data="test_callback")]
        ])
    )
    
    if update.effective_user:
        general_logger.info(f"Handled /start command for user {update.effective_user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    if not update.message:
        return
        
    help_text = (
        "🤖 **PsychoChauffeur Bot - Довідка**\n\n"
        
        "📊 **Команди аналізу повідомлень:**\n"
        "• `/analyze` - аналіз сьогоднішніх повідомлень\n"
        "• `/analyze last <число> messages` - останні N повідомлень\n"
        "• `/analyze last <число> days` - повідомлення за останні N днів\n"
        "• `/analyze date <дата>` - повідомлення за конкретну дату\n"
        "• `/analyze period <дата1> <дата2>` - повідомлення за період\n\n"
        
        "📅 **Підтримувані формати дат:**\n"
        "• `YYYY-MM-DD` (наприклад: 2024-01-15)\n"
        "• `DD-MM-YYYY` (наприклад: 15-01-2024)\n"
        "• `DD/MM/YYYY` (наприклад: 15/01/2024)\n\n"
        
        "💡 **Приклади команд аналізу:**\n"
        "• `/analyze last 50 messages`\n"
        "• `/analyze date 15-01-2024`\n"
        "• `/analyze period 01-01-2024 31-01-2024`\n"
        "• `/analyze last 7 days`\n\n"
        
        "🌞 **Команди космічної погоди:**\n"
        "• `/flares` - актуальний знімок сонячних спалахів\n"
        "• `/gm` - геомагнітна активність\n\n"
        
        "🎥 **Завантаження відео:**\n"
        "• Підтримка TikTok, YouTube Shorts, Twitter, Vimeo, Reddit, Twitch\n"
        "• Просто надішліть посилання на відео\n\n"
        
        "🌤️ **Інші команди:**\n"
        "• `/weather [місто]` - прогноз погоди\n"
        "• `/cat` - випадкове фото котика\n"
        "• `/remind` - нагадування\n"
        "• `/ping` - перевірка роботи бота\n\n"
        "🔧 **Адмін команди (тільки для адміністраторів):**\n"
        "• `/mute <@username або user_id> <хвилини>` - заборонити писати користувачу\n"
        "• `/unmute <@username або user_id>` - дозволити писати користувачу\n"
        "• Відповідайте на повідомлення з `/mute <хвилини>` або `/unmute`\n\n"
        
        "❓ **Питання або проблеми?**\n"
        "Зверніться до @vo1dee"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')
    
    if update.effective_user:
        general_logger.info(f"Handled /help command for user {update.effective_user.id}")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ping command."""
    if not update.message:
        return
        
    await update.message.reply_text("Pong! 🏓")
    
    if update.effective_user:
        general_logger.info(f"Handled /ping command for user {update.effective_user.id}")