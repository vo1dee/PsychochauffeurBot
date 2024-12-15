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
- Configurable button definitions through BUTTONS_CONFIG and LANGUAGE_OPTIONS_CONFIG
- Two different button menus (original and language)
- Dynamic button visibility based on link state
- Stateful link tracking using hashed references
- Automatic keyboard updates after modifications

Example of link modifications:
    Original:  https://x.com/user/status/123
    Modified:  https://fixupx.com/user/status/123
    + /ua:     https://fixupx.com/user/status/123/ua
    + /sk:     https://fixupx.com/user/status/123/sk
    + /en:     https://fixupx.com/user/status/123/en
    + d.:      https://d.fixupx.com/user/status/123

Button Configuration:
    Each button in BUTTONS_CONFIG/LANGUAGE_OPTIONS_CONFIG defines:
    - action: Identifier for the modification type
    - text: Button label shown to users
    - check: Lambda function determining button visibility
    - modify: Lambda function implementing the link modification

Menus:
    Original menu:
    - is visible when user shares a Twitter/X post
    - lets user select from different actions from BUTTONS_CONFIG
    - is called by default of when user has selected an option from the language menu
    
    Language menu:
    - is visible when user selects the "Translate" option from original menu
    - lets user select from different language options from LANGUAGE_OPTIONS_CONFIG

Usage:
    from keyboards import create_link_keyboard, button_callback

    # Register the callback handler in your bot
    application.add_handler(CallbackQueryHandler(button_callback))

    # Create keyboard for a modified link
    keyboard = create_link_keyboard(modified_link)
    await bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)

How To Add More Languages:
    To add another language option, simply add new element to field 
    "LANGUAGE_OPTIONS_CONFIG" with the correct two-letter language code
    in 'action', 'check' and 'modify' fields.
    For example 'fr' for French, 'ro' for Romanian or 'pl' for Polish.

Note:
    The module uses bot_data to store link states using MD5 hashes as keys.
    This allows for stateful modifications while keeping callback data within
    Telegram's size limits.
"""

BUTTONS_CONFIG = [
    {
        'action': 'translate',
        'text': '🌍 Translate',
        'check': lambda link: 'fixupx.com' in link,
        'modify': lambda link: link # No modification to link
    },
    {
        'action': 'translate_remove',
        'text': '❌ Remove Translation',
        'check': lambda link: 'fixupx.com' in link and any(link.endswith(f"/{option['action']}") for option in LANGUAGE_OPTIONS_CONFIG),
        'modify': lambda link: modify_language(link, 'none')
    },
    {
        'action': 'desc_remove',
        'text': '❌ Hide Description',
        'check': lambda link: 'd.fixupx.com' not in link and 'fixupx.com' in link,
        'modify': lambda link: f"{link.split('://', 1)[0]}://d.{link.split('://', 1)[1]}"
    },
    {
        'action': 'desc_add',
        'text': '📺 Add Description',
        'check': lambda link: 'd.fixupx.com' in link,
        'modify': lambda link: f"{link.split('://d.', 1)[0]}://{link.split('://d.', 1)[1]}"
    },
]

LANGUAGE_OPTIONS_CONFIG = [
    {
        'action': 'ua',
        'text': '🇺🇦 Перекласти українською',
        'check': lambda link: not link.endswith('/ua'),
        'modify': lambda link: modify_language(link, 'ua')
    },
    {
        'action': 'sk',
        'text': '🇸🇰 Preložiť do slovenčiny',
        'check': lambda link: not link.endswith('/sk'),
        'modify': lambda link: modify_language(link, 'sk')
    },
    {
        'action': 'en',
        'text': '🇬🇧 Translate to English',
        'check': lambda link: not link.endswith('/en'),
        'modify': lambda link: modify_language(link, 'en')
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

        if action == 'translate':
            # Show the language selection sub-menu
            reply_markup = create_language_menu(original_link)
            await query.message.edit_text(
                # Replacing the text with link fixes the issue of the link no longer working after
                # opening the language sub-menu
                text = original_link,
                reply_markup = reply_markup
            )
            return

        # Find the corresponding button config
        # First check if the action corresponds to a language option
        config = next((c for c in LANGUAGE_OPTIONS_CONFIG if c['action'] == action), None)
        if not config:
            # If not a language option, fallback to BUTTONS_CONFIG
            config = next((c for c in BUTTONS_CONFIG if c['action'] == action), None)
        if not config:
            return

        # Modify the link
        new_link = config['modify'](original_link)

        # Update the message text with the new link
        message_parts = query.message.text.split('\n')
        for i, line in enumerate(message_parts):
            if original_link in line:
                message_parts[i] = new_link
        new_message = '\n'.join(message_parts)

        # Store the new link and create the updated keyboard
        context.bot_data[hashlib.md5(new_link.encode()).hexdigest()[:8]] = new_link
        reply_markup = create_link_keyboard(new_link)

        await query.message.edit_text(text=new_message, reply_markup=reply_markup)

    except Exception as e:
        general_logger.error(f"Error in button callback: {str(e)}")
        await query.message.edit_text("Sorry, an error occurred. Please try again.")

def create_language_menu(link):
    """Create a sub-menu for language selection"""
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    buttons = [
        InlineKeyboardButton(config['text'], callback_data=f"{config['action']}:{link_hash}")
        for config in LANGUAGE_OPTIONS_CONFIG
        if config['check'](link)
    ]
    return InlineKeyboardMarkup([buttons]) if buttons else None

def create_link_keyboard(link):
    """Create keyboard with available modification buttons for a link"""
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    buttons = [
        InlineKeyboardButton(config['text'], callback_data=f"{config['action']}:{link_hash}")
        for config in BUTTONS_CONFIG
        if config['check'](link)
    ]
    return InlineKeyboardMarkup([buttons]) if buttons else None

def modify_language(link, lang):
    """Change X/Twitter link language modifier"""
    # Dynamically generate the list of language modifiers from LANGUAGE_OPTIONS
    languages = [option['action'] for option in LANGUAGE_OPTIONS_CONFIG]
    
    # Check if the link already ends with a language modifier and remove it
    for l in languages:
        if link.endswith(f"/{l}"):
            link = link.rsplit('/', 1)[0]
            break
    
    # Add the new language modifier if lang is not none else return link with no modifier
    if lang != 'none':
        return f"{link}/{lang}"
    else:
        return link