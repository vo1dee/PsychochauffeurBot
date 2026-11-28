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
        "🤖 *PsychoChauffeur — усі команди*\n\n"

        "🧠 *AI:*\n"
        "• `/ask <питання>` — запитати AI (за потреби шукає в інтернеті)\n"
        "• `/tldr` — у відповідь на повідомлення чи посилання: коротке резюме "
        "(`/tldr english`, `/tldr original` — інша мова)\n"
        "• `/analyze` — що сьогодні було в чаті\n"
        "• `/analyze last <N> messages` · `last <N> days` — останні N повідомлень / днів\n"
        "• `/analyze date <дата>` · `period <дата1> <дата2>` — за дату чи період\n\n"

        "🎥 *Завантаження:*\n"
        "• Надішліть посилання TikTok, Instagram, YouTube Shorts, X, Vimeo, Twitch — "
        "відео й фото прийдуть у чат\n"
        "• `/song <назва>` або посилання Spotify, Deezer, Apple Music, Shazam, YouTube — трек\n"
        "• `/short` — у відповідь на посилання YouTube Shorts: скачати відео\n\n"

        "🌤 *Погода й космос:*\n"
        "• `/weather <місто>` — поточна погода\n"
        "• `/gm` — прогноз геомагнітних бур\n"
        "• `/flares` — сонячні спалахи зараз\n"
        "• `/nasa` — астрономічне фото дня від NASA\n\n"

        "📊 *Статистика:*\n"
        "• `/stats [днів|all]` — активність чату\n"
        "• `/mystats` — ваша особиста статистика\n"
        "• `/count <слово>` — скільки разів слово згадували в чаті\n"
        "• `/missing @user` — коли користувач писав востаннє\n"
        "• `/report [днів]` — звіт про використання бота\n\n"

        "🐱 *Інше:*\n"
        "• `/cat` — випадкове фото кота\n"
        "• `/ping` — перевірити, чи бот онлайн\n\n"

        "🔧 *Для адмінів:*\n"
        "• `/config` — налаштування бота для цього чату\n"
        "• `/recap on [HH:MM]` · `off` · `time HH:MM` — щоденний рекап чату (типово 09:30)\n"
        "• `/speech on|off` — розпізнавання голосових\n"
        "• `/random on|off` — випадкові відповіді\n"
        "• `/reaction on|off` — емодзі-реакції\n"
        "• `/mute <@user|id> <хвилини>` або у відповідь `/mute <хвилини>` — заглушити (макс. 1440)\n"
        "• `/unmute <@user|id>` або у відповідь — розглушити\n\n"

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