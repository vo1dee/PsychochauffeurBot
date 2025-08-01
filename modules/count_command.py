from telegram import Update
from telegram.ext import ContextTypes
import re

async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Count the number of encounters of a word in the entire chat history.
    Usage: /count <word>
    """
    if not update.effective_chat:
        if update.message:
            await update.message.reply_text("❌ Помилка: не вдалося визначити чат.")
        return
    chat_id = update.effective_chat.id
    args = context.args if hasattr(context, 'args') else []
    
    if not args or len(args) != 1:
        if update.message:
            await update.message.reply_text(
            "❌ Будь ласка, вкажіть одне слово для підрахунку.\nПриклад: /count сонце"
        )
        return
    
    word = args[0].strip().lower()
    if not word.isalpha():
        if update.message:
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
            
        if update.message:
            await update.message.reply_text(msg)
        
    except Exception as e:
        from modules.logger import error_logger
        error_logger.error(f"Error in /count command: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(
                "❌ Виникла помилка при підрахунку. Спробуйте пізніше."
            )

async def missing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /missing @username
    Shows how long the user was missing, when was their last message, and what it was.
    """
    from modules.chat_analysis import get_last_message_for_user_in_chat
    from modules.database import Database
    from datetime import datetime
    import pytz

    if not update.effective_chat:
        if update.message:
            await update.message.reply_text("❌ Помилка: не вдалося визначити чат.")
        return
    chat_id = update.effective_chat.id
    args = context.args if hasattr(context, 'args') else []
    if not args or not args[0]:
        if update.message:
            await update.message.reply_text(
            "❌ Будь ласка, вкажіть username для перевірки.\nПриклад: /missing @username або /missing username"
        )
        return
    username = args[0].lstrip('@')
    
    # Enhanced user lookup with better error messages
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # Check if user exists
        user_rows = await conn.fetch("""
            SELECT user_id, username, first_name, last_name
            FROM users 
            WHERE username = $1
        """, username)
        
        if not user_rows:
            # Check for similar usernames
            similar_users = await conn.fetch("""
                SELECT username
                FROM users 
                WHERE username ILIKE $1
                ORDER BY username
                LIMIT 5
            """, f"%{username}%")
            
            if similar_users:
                similar_list = ", ".join([f"@{u['username']}" for u in similar_users])
                if update.message:
                    await update.message.reply_text(
                        f"❌ Користувача @{username} не знайдено.\n\n"
                        f"Можливо, ви мали на увазі одного з цих користувачів:\n{similar_list}"
                    )
            else:
                if update.message:
                    await update.message.reply_text(
                        f"❌ Користувача @{username} не знайдено в базі даних.\n"
                        f"Можливо, цей користувач ще не писав повідомлення в чатах з ботом."
                    )
            return
    
    # Try to get last message for this username
    last_message = await get_last_message_for_user_in_chat(chat_id, username=username)
    if not last_message:
        # Check if user has messages in other chats
        user_ids = [row['user_id'] for row in user_rows]
        total_messages = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE user_id = ANY($1::bigint[])
        """, user_ids)
        
        if total_messages > 0:
            if update.message:
                await update.message.reply_text(
                    f"❌ Не знайдено повідомлень від @{username} у цьому чаті.\n"
                    f"Але користувач має {total_messages} повідомлень в інших чатах."
                )
        else:
            if update.message:
                await update.message.reply_text(
                    f"❌ Не знайдено повідомлень від @{username} у цьому чаті.\n"
                    f"Користувач ще не писав повідомлень в жодному чаті."
                )
        return
    last_time = last_message['timestamp']
    last_username = last_message['username']
    last_text = last_message['text']
    # Fetch chat title
    chat_title = update.effective_chat.title or str(update.effective_chat.id)
    # Check if last message was a command
    command_used = None
    if last_text and last_text.startswith('/'):
        command_used = last_text.split()[0]
    now = datetime.now(pytz.timezone('Europe/Kyiv'))
    
    # Ensure last_time is a datetime object
    if isinstance(last_time, str):
        from dateutil import parser
        last_time_dt = parser.parse(last_time)
    else:
        last_time_dt = last_time
    
    if last_time_dt.tzinfo is None:
        last_time_dt = last_time_dt.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Europe/Kyiv'))
    delta = now - last_time_dt
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        ago_str = f"{days} дн. {hours} год. {minutes} хв."
    elif hours > 0:
        ago_str = f"{hours} год. {minutes} хв."
    else:
        ago_str = f"{minutes} хв."
    time_str = last_time_dt.strftime('%H:%M %d.%m.%Y')
    msg = (
        f"@{last_username} востаннє писав(ла) {ago_str} тому\n"
        f"Час: {time_str}\n"
        f"Останні слова: {last_text if last_text else '[без тексту]'}"
    )
    if command_used:
        msg += f"\nОстання команда: {command_used}"
    if update.message:
        await update.message.reply_text(msg)
