from telegram import Update
from telegram.ext import ContextTypes

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
        from modules.chat_analysis import get_last_n_messages_in_chat
        # Use a very large number to fetch all messages (e.g., 1_000_000)
        messages = await get_last_n_messages_in_chat(chat_id, 1_000_000)
        count = 0
        for _, _, text in messages:
            if not text:
                continue
            # Whole word, case-insensitive match
            import re
            count += len(re.findall(rf'\\b{re.escape(word)}\\b', text, flags=re.IGNORECASE))
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