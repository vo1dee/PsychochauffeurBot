from telegram import Update
from telegram.ext import ContextTypes
import re

async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Count the number of encounters of a word in the entire chat history.
    Usage: /count <word>
    """
    chat_id = update.effective_chat.id
    args = context.args if hasattr(context, 'args') else []
    
    if not args or len(args) != 1:
        await update.message.reply_text(
            "❌ Будь ласка, вкажіть одне слово для підрахунку.\nПриклад: /count сонце"
        )
        return
    
    word = args[0].strip().lower()
    if not word.isalpha():
        await update.message.reply_text(
            "❌ Слово повинно містити лише літери."
        )
        return
    
    try:
        from modules.database import Database
        from modules.logger import general_logger

        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Use PostgreSQL regex to count ALL occurrences (not just messages containing word)
            query = """
            SELECT COALESCE(SUM(
                (LENGTH(text) - LENGTH(REGEXP_REPLACE(text, $1, '', 'gi'))) 
                / LENGTH($2)
            ), 0)::INTEGER as total_count
            FROM messages 
            WHERE chat_id = $3 
              AND text IS NOT NULL 
              AND text ~* $1
            """
            
            # Use a simpler pattern that matches the word as a whole word
            word_pattern = rf'\m{re.escape(word)}\M'
            
            count = await conn.fetchval(query, word_pattern, word, chat_id)
            
            general_logger.info(f"Word count for '{word}' in chat {chat_id}: {count}")
        
        # Format response (same as original)
        if count == 0:
            msg = f"📊 Слово '{word}' не зустрічалося в історії цього чату."
        elif count == 1:
            msg = f"📊 Слово '{word}' зустрілося 1 раз в історії цього чату."
        else:
            msg = f"📊 Слово '{word}' зустрілося {count} разів в історії цього чату."
            
        await update.message.reply_text(msg)
        
    except Exception as e:
        from modules.logger import error_logger
        error_logger.error(f"Error in /count command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Виникла помилка при підрахунку. Спробуйте пізніше."
        )

async def missing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /missing @username
    Shows how long the user was missing, when was their last message, and what it was.
    """
    from modules.chat_analysis import get_last_message_for_user_in_chat
    from datetime import datetime
    import pytz

    chat_id = update.effective_chat.id
    args = context.args if hasattr(context, 'args') else []
    if not args or not args[0]:
        await update.message.reply_text(
            "❌ Будь ласка, вкажіть username для перевірки.\nПриклад: /missing @username або /missing username"
        )
        return
    username = args[0].lstrip('@')
    # Try to get last message for this username
    last_message = await get_last_message_for_user_in_chat(chat_id, username=username)
    if not last_message:
        await update.message.reply_text(f"❌ Не знайдено повідомлень від @{username} у цьому чаті.")
        return
    last_time, last_username, last_text = last_message
    # Fetch chat title
    chat_title = update.effective_chat.title or str(update.effective_chat.id)
    # Check if last message was a command
    command_used = None
    if last_text and last_text.startswith('/'):
        command_used = last_text.split()[0]
    now = datetime.now(pytz.timezone('Europe/Kyiv'))
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Europe/Kyiv'))
    delta = now - last_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        ago_str = f"{days} дн. {hours} год. {minutes} хв."
    elif hours > 0:
        ago_str = f"{hours} год. {minutes} хв."
    else:
        ago_str = f"{minutes} хв."
    time_str = last_time.strftime('%H:%M %d.%m.%Y')
    msg = (
        f"@{last_username} востаннє писав(ла) {ago_str} тому\n"
        f"Час: {time_str}\n"
        f"Останні слова: {last_text if last_text else '[без тексту]'}"
    )
    if command_used:
        msg += f"\nОстання команда: {command_used}"
    await update.message.reply_text(msg)
