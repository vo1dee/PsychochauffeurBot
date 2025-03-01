import hashlib
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from modules.logger import general_logger,error_logger



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
        'check': lambda link: 'fixupx.com' in link and not any(link.endswith(f"/{lang['action']}") for lang in LANGUAGE_OPTIONS_CONFIG),
        'modify': lambda link: link
    },
    {
        'action': 'translate_remove',
        'text': '❌ Remove Translation',
        'check': lambda link: 'fixupx.com' in link and any(link.endswith(f"/{lang['action']}") for lang in LANGUAGE_OPTIONS_CONFIG),
        'modify': lambda link: modify_language(link, 'none')
    },
    {
        'action': 'desc_remove',
        'text': '❌ Hide Description',
        'check': lambda link: 'fixupx.com' in link and not link.startswith('https://d.'),
        'modify': lambda link: link.replace('https://', 'https://d.')
    },
    {
        'action': 'desc_add',
        'text': '📺 Add Description',
        'check': lambda link: link.startswith('https://d.'),
        'modify': lambda link: link.replace('https://d.', 'https://')
    },
    {
        'action': 'download_video',
        'text': '⬇️ Download Video',
        'check': lambda link: 'x.com' in link or 'fixupx.com' in link,
        'modify': lambda link: link
    },
    {
        'action': 'download_instagram_video',
        'text': '⬇️ Download Instagram Video',
        'check': lambda link: 'instagram.com' in link,
        'modify': lambda link: link
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
    """Handle button callbacks for link modifications and video downloads."""
    query = update.callback_query
    await query.answer()
    
    try:
        general_logger.info(f"Received callback data: {query.data}")
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        
        # Split action and hash from callback data
        action, link_hash = query.data.split(':', 1)
        original_link = context.bot_data.get(link_hash)
        
        general_logger.info(f"Action: {action}, Hash: {link_hash}, Original link: {original_link}")
        
        if not original_link:
            await query.message.edit_text("Sorry, this button has expired. Please generate a new link.")
            return
        
        # Handle video download action first
        if action == 'download_video':
            video_downloader = context.bot_data.get('video_downloader')
            if not video_downloader:
                await query.message.edit_text("❌ Video downloader not initialized.")
                return
                
            try:
                await query.message.edit_text("🔄 Downloading video...")
                filename, title = await video_downloader.download_video(original_link)
                
                if filename and os.path.exists(filename):
                    with open(filename, 'rb') as video_file:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            caption=f"📹 {title or 'Downloaded Video'}"
                        )
                    os.remove(filename)
                    await query.message.edit_text("✅ Download complete!")
                else:
                    await query.message.edit_text("❌ Video download failed. Check the link and try again.")
                return
            except Exception as e:
                error_logger.error(f"Error in video download: {str(e)}")
                await query.message.edit_text("❌ An error occurred while downloading the video.")
                return
            
        # Handle Instagram video download action
        if action == 'download_instagram_video':
            video_downloader = context.bot_data.get('video_downloader')
            if not video_downloader:
                await query.message.edit_text("❌ Video downloader not initialized.")
                return
                
            try:
                await query.message.edit_text("🔄 Downloading Instagram video...")
                filename, title = await video_downloader.download_video(original_link)
                
                if filename and os.path.exists(filename):
                    with open(filename, 'rb') as video_file:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            caption=f"📹 {title or 'Downloaded Video'}"
                        )
                    os.remove(filename)
                    await query.message.edit_text("✅ Download complete!")
                else:
                    await query.message.edit_text("❌ Video download failed. Check the link and try again.")
                return
            except Exception as e:
                error_logger.error(f"Error in Instagram video download: {str(e)}")
                await query.message.edit_text("❌ An error occurred while downloading the video.")
                return
        
        # Convert x.com to fixupx.com if needed (only once)
        if 'x.com' in original_link and 'fixupx.com' not in original_link:
            original_link = original_link.replace('x.com', 'fixupx.com')

        # Handle translate action (language menu)
        if action == 'translate':
            general_logger.info("Creating language menu")
            keyboard = create_language_menu(original_link, link_hash)  # Pass both arguments
            await query.message.edit_text(
                text=query.message.text,
                reply_markup=keyboard
            )
            return

        # Handle all other link modifications
        new_link = None
        
        # Handle language selection
        if action in ['ua', 'sk', 'en']:
            new_link = modify_language(original_link, action)
            general_logger.info(f"Modified link with language {action}: {new_link}")
        
        # Handle description toggle
        elif action in ['desc_remove', 'desc_add']:
            config = next((c for c in BUTTONS_CONFIG if c['action'] == action), None)
            if config:
                new_link = config['modify'](original_link)
                general_logger.info(f"Modified link with {action}: {new_link}")
        
        # Handle translation removal
        elif action == 'translate_remove':
            new_link = modify_language(original_link, 'none')
            general_logger.info(f"Removed translation: {new_link}")

        if new_link:
            # Update message with new link
            new_message = query.message.text.replace(original_link, new_link)
            
            # Store new link hash
            new_hash = hashlib.md5(new_link.encode()).hexdigest()[:8]
            context.bot_data[new_hash] = new_link
            
            # Create updated keyboard
            keyboard = create_link_keyboard(new_link)
            
            await query.message.edit_text(
                text=new_message,
                reply_markup=keyboard
            )
        else:
            error_logger.error(f"No modification performed for action: {action}")
            await query.message.edit_text("❌ Invalid action")

    except Exception as e:
        error_logger.error(f"Error in button callback: {str(e)}", exc_info=True)
        await query.message.edit_text(f"❌ Error: {str(e)}")



def create_link_keyboard(link):
    """Create keyboard with available modification buttons"""
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    buttons = []
    
    # Ensure link is using fixupx.com domain
    if 'x.com' in link:
        link = link.replace('x.com', 'fixupx.com')
    
    general_logger.info(f"Creating keyboard for link: {link}")
    
    for config in BUTTONS_CONFIG:
        if config['check'](link):
            callback_data = f"{config['action']}:{link_hash}"
            general_logger.info(f"Adding button: {config['text']} with callback_data: {callback_data}")
            buttons.append(
                InlineKeyboardButton(
                    config['text'],
                    callback_data=callback_data
                )
            )
    
    return InlineKeyboardMarkup([buttons]) if buttons else None


def create_language_menu(link, link_hash):
    """Create language selection menu"""
    buttons = []
    
    general_logger.info(f"Creating language menu for link: {link}")
    
    for config in LANGUAGE_OPTIONS_CONFIG:
        if config['check'](link):
            callback_data = f"{config['action']}:{link_hash}"
            general_logger.info(f"Adding language button: {config['text']} with callback_data: {callback_data}")
            buttons.append(
                InlineKeyboardButton(
                    config['text'],
                    callback_data=callback_data
                )
            )
    
    return InlineKeyboardMarkup([buttons]) if buttons else None




def modify_language(link, lang):
    """Modify link language"""
    base_link = link
    
    # Remove any existing language suffix
    for option in LANGUAGE_OPTIONS_CONFIG:
        lang_suffix = f"/{option['action']}"
        if base_link.endswith(lang_suffix):
            base_link = base_link[:-len(lang_suffix)]
            break
    
    # Add new language if not 'none'
    if lang != 'none':
        return f"{base_link}/{lang}"
    return base_link

