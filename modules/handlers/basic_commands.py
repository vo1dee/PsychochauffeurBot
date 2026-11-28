"""
Basic command handlers for the PsychoChauffeur bot.

Contains handlers for fundamental commands like start, help, and ping.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from modules.logger import general_logger

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.message:
        return

    welcome_text = (
        "👋 *Привіт! Я PsychoChauffeur* — бот, який живе у вашому чаті.\n\n"

        "🎥 *Кидайте посилання — я скачаю.*\n"
        "TikTok, Instagram, YouTube Shorts, X, Vimeo, Twitch: відео й фото "
        "прийдуть прямо в чат.\n\n"

        "🎵 *Музика.*\n"
        "Посилання Spotify, Deezer, Apple Music чи Shazam → готовий трек. "
        "Або `/song <назва>`.\n\n"

        "🧠 *Розумний співрозмовник.*\n"
        "• `/ask <питання>` — відповім, за потреби пошукаю в інтернеті\n"
        "• Тегніть мене або відповідайте на мої повідомлення — підтримаю розмову\n"
        "• `/tldr` — коротко про повідомлення чи статтю\n"
        "• `/analyze` — що сьогодні було в чаті\n\n"

        "🌤 *Погода й космос:* `/weather <місто>`, `/gm`, `/flares`, `/nasa`\n\n"

        "📜 *Для адмінів:* щоденний рекап `/recap on`, налаштування `/config`\n\n"

        "Усі команди: /help · Питання: @vo1dee"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    if update.effective_user:
        general_logger.info(f"Handled /start command for user {update.effective_user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    if not update.message:
        return
        
    help_text = (
        "🤖 **PsychoChauffeur Bot — Довідка**\n\n"

        "🤖 **AI / GPT:**\n"
        "• `/ask <питання>` — запитати GPT\n"
        "• `/analyze` — аналіз сьогоднішніх повідомлень\n"
        "• `/analyze last <N> messages` — останні N повідомлень\n"
        "• `/analyze last <N> days` — за останні N днів\n"
        "• `/analyze date <дата>` — за конкретну дату (DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY)\n"
        "• `/analyze period <дата1> <дата2>` — за період\n\n"

        "📊 **Статистика:**\n"
        "• `/stats` — статистика чату\n"
        "• `/mystats` — особиста статистика використання\n"
        "• `/count` — кількість повідомлень\n"

        "🌤 **Погода та космос:**\n"
        "• `/weather <місто>` — поточна погода\n"
        "• `/flares` — знімок сонячних спалахів\n"
        "• `/gm` — геомагнітна активність\n\n"

        "🎥 **Завантаження відео:**\n"
        "• Підтримка: TikTok, YouTube Shorts, Twitter, Vimeo, Twitch\n"
        "• Просто надішліть посилання\n\n"

        "🐱 **Розваги:**\n"
        "• `/cat` — випадкове фото кота\n\n"

        "🔗 **Обробка посилань:**\n"
        "• Оптимізація AliExpress\n"
        "• Модифікація для обмежених доменів\n\n"

        "📜 **Щоденний рекап чату (для адмінів):**\n"
        "• `/recap on [HH:MM]` — увімкнути рекап (за замовчуванням 09:30)\n"
        "• `/recap off` — вимкнути рекап\n"
        "• `/recap time HH:MM` — змінити час надсилання\n\n"

        "🔧 **Адмін команди (тільки для адміністраторів):**\n"
        "• `/mute <@user або id> <хвилини>` — заглушити користувача (макс. 1440 хв)\n"
        "• `/unmute <@user або id>` — розглушити користувача\n"
        "• `/speech on|off` — увімк./вимк. розпізнавання мовлення\n"
        "• `/random on|off` — увімк./вимк. випадкові відповіді\n"
        "• `/reaction on|off` — увімк./вимк. емодзі-реакції\n"
        "• `/error_report` — звіт про помилки\n\n"

        "🛠 **Інше:**\n"
        "• `/ping` — перевірка доступності бота\n"
        "• `/missing @user` — перевірка відсутності користувача\n\n"

        "❓ Питання або проблеми? @vo1dee"
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