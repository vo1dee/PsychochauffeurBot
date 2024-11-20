import hashlib

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

from modules.file_manager import general_logger

"""
This module handles inline keyboard modifications for the Telegram bot's link transformation functionality.

The module provides a flexible system for modifying shared links (like Twitter/X posts) with additional
parameters through inline keyboard buttons. Each button can add specific modifications to the links
(e.g., adding language parameters or display preferences).

Features:
- Configurable button definitions through BUTTONS_CONFIG
- Dynamic button visibility based on link state
- Stateful link tracking using hashed references
- Automatic keyboard updates after modifications

Example of link modifications:
    Original:  https://x.com/user/status/123
    Modified:  https://fixupx.com/user/status/123
    + /ua:     https://fixupx.com/user/status/123/ua
    + d.:      https://d.fixupx.com/user/status/123

Button Configuration:
    Each button in BUTTONS_CONFIG defines:
    - action: Identifier for the modification type
    - text: Button label shown to users
    - check: Lambda function determining button visibility
    - modify: Lambda function implementing the link modification

Usage:
    from keyboards import create_link_keyboard, button_callback

    # Register the callback handler in your bot
    application.add_handler(CallbackQueryHandler(button_callback))

    # Create keyboard for a modified link
    keyboard = create_link_keyboard(modified_link)
    await bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

Note:
    The module uses bot_data to store link states using MD5 hashes as keys.
    This allows for stateful modifications while keeping callback data within
    Telegram's size limits.
"""

BUTTONS_CONFIG = [
    {
        'action': 'ua',
        'text': '🇺🇦 Перекласти українською',
        'check': lambda link: not link.endswith('/ua'),
        'modify': lambda link: f"{link}/ua"
    },
    {
        'action': 'd',
        'text': '📺 Прибрати опис',
        'check': lambda link: 'd.fixupx.com' not in link,
        'modify': lambda link: f"{link.split('://', 1)[0]}://d.{link.split('://', 1)[1]}"
    }
]

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    try:
        action, link_hash = query.data.split(':', 1)
        original_link = context.bot_data.get(link_hash)

        if not original_link:
            await query.message.edit_text("Sorry, this button has expired. Please generate a new link.")
            return

        # Find the corresponding button config and modify the link
        config = next((c for c in BUTTONS_CONFIG if c['action'] == action), None)
        if not config:
            return

        new_link = config['modify'](original_link)

        # Update the message text with new link
        message_parts = query.message.text.split('\n')
        for i, line in enumerate(message_parts):
            if original_link in line:
                message_parts[i] = new_link
        new_message = '\n'.join(message_parts)

        # Store the new link and create keyboard for remaining modifications
        context.bot_data[hashlib.md5(new_link.encode()).hexdigest()[:8]] = new_link
        reply_markup = create_link_keyboard(new_link)

        await query.message.edit_text(text=new_message, reply_markup=reply_markup)

    except Exception as e:
        general_logger.error(f"Error in button callback: {str(e)}")
        await query.message.edit_text("Sorry, an error occurred. Please try again.")

def create_link_keyboard(link):
    """Create keyboard with available modification buttons for a link"""
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    buttons = [
        InlineKeyboardButton(config['text'], callback_data=f"{config['action']}:{link_hash}")
        for config in BUTTONS_CONFIG
        if config['check'](link)
    ]
    return InlineKeyboardMarkup([buttons]) if buttons else None