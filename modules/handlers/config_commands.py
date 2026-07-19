"""
/config (/settings) — Telegram-native settings menu.

Schema-driven: the menu is generated from config_v2 schema metadata
(telegram exposure flags, Ukrainian labels, ge/le bounds). See
docs/adr/0001-schema-driven-curated-telegram-config-ui.md.

Callback data format (stateless, absolute targets, <= 64 bytes):
    cfg:m                 root menu
    cfg:c:<module>        category screen
    cfg:s:<fhash>:<value> set a field to an absolute value
    cfg:r:<fhash>         reset a field override (follow global default)
    cfg:x                 close the menu
    cfg:n                 no-op (label rows)

<fhash> is a stable 8-hex digest of "module:path", so buttons survive bot
restarts; if the schema changes, stale buttons answer "menu outdated".
"""

import hashlib
from typing import Any, Dict, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config_v2.manager import config_manager, telegram_actor
from config_v2.schema import (
    TelegramField,
    get_module_description,
    get_module_label,
    module_has_advanced_fields,
    telegram_fields,
    telegram_modules,
)
from modules.logger import general_logger, error_logger

CB_PREFIX = "cfg"

MSG_ADMINS_ONLY = "⛔ Налаштування можуть змінювати лише адміністратори."
MSG_STALE_MENU = "Меню застаріло. Відкрийте /config ще раз."
MSG_SAVED = "✅ Збережено"
MSG_RESET = "↺ Скинуто до типового"
ADVANCED_FOOTER = "Більше налаштувань — напишіть @vo1dee."

ROOT_TEXT = (
    "⚙️ <b>Налаштування бота</b>\n\n"
    "Тут можна змінити налаштування бота для цього чату. "
    "Оберіть розділ, щоб побачити доступні параметри.\n\n"
    "Позначка ✏️ означає, що значення змінено саме для цього чату; "
    "кнопка ↺ повертає типове значення."
)

INT_STEPS = (-10, -1, 1, 10)
FLOAT_STEPS = (-0.05, -0.01, 0.01, 0.05)


def _field_hash(module: str, path: str) -> str:
    return hashlib.sha1(f"{module}:{path}".encode()).hexdigest()[:8]


def _fields_by_hash(chat_type: str) -> Dict[str, TelegramField]:
    return {
        _field_hash(f.module, f.path): f
        for module in telegram_modules(chat_type)
        for f in telegram_fields(module, chat_type)
    }


def _normalize_chat_type(chat_type: str) -> str:
    return "group" if chat_type == "supergroup" else chat_type


def _walk(data: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def _has_override(chat_rows: Dict[str, Any], path: str) -> bool:
    head, _, rest = path.partition(".")
    if head not in chat_rows:
        return False
    if not rest:
        return True
    current: Any = chat_rows[head]
    for part in rest.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _format_value(field: TelegramField, value: Any) -> str:
    if field.value_type is bool:
        return "увімкнено" if value else "вимкнено"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


async def _is_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Private chats: anyone (it's their own config). Groups: admins only."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    if chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        general_logger.warning(
            f"Failed admin check for user {user.id} in chat {chat.id}: {e}"
        )
        return False


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _build_root(chat_type: str) -> Tuple[str, InlineKeyboardMarkup]:
    text = ROOT_TEXT
    if chat_type == "group":
        text += "\n\nЗмінювати налаштування можуть лише адміністратори."
    rows = [
        [
            InlineKeyboardButton(
                get_module_label(module, "uk"), callback_data=f"{CB_PREFIX}:c:{module}"
            )
        ]
        for module in telegram_modules(chat_type)
    ]
    rows.append([InlineKeyboardButton("❌ Закрити", callback_data=f"{CB_PREFIX}:x")])
    return text, InlineKeyboardMarkup(rows)


def _stepper_row(field: TelegramField, current: Any, fhash: str) -> List[InlineKeyboardButton]:
    steps = FLOAT_STEPS if field.value_type is float else INT_STEPS
    buttons: List[InlineKeyboardButton] = []
    for step in steps:
        target = current + step
        if field.ge is not None:
            target = max(target, field.ge)
        if field.le is not None:
            target = min(target, field.le)
        if field.value_type is int:
            target = int(target)
        else:
            target = round(target, 4)
        if target == current:
            continue
        label = f"{'+' if step > 0 else '−'}{abs(step):g}"
        buttons.append(
            InlineKeyboardButton(
                label, callback_data=f"{CB_PREFIX}:s:{fhash}:{target:g}"
            )
        )
    return buttons


async def _build_category(
    chat_id: str, chat_type: str, module: str
) -> Tuple[str, InlineKeyboardMarkup]:
    mgr = config_manager()
    resolved = await mgr.get_resolved_raw(chat_id, module)
    chat_rows = await mgr.db.get_module_config(chat_id, module)
    fields = telegram_fields(module, chat_type)

    lines = [f"⚙️ <b>{get_module_label(module, 'uk')}</b>"]
    description = get_module_description(module)
    if description:
        lines.append(description)
    lines.append("")

    rows: List[List[InlineKeyboardButton]] = []
    for field in fields:
        fhash = _field_hash(field.module, field.path)
        value = _walk(resolved, field.path)
        if value is None:
            value = field.default
        overridden = _has_override(chat_rows, field.path)
        mark = " ✏️" if overridden else ""

        lines.append(f"• <b>{field.label}</b>: {_format_value(field, value)}{mark}")
        if field.description:
            lines.append(f"  {field.description}")

        reset_btn = (
            [InlineKeyboardButton("↺", callback_data=f"{CB_PREFIX}:r:{fhash}")]
            if overridden
            else []
        )

        if field.widget == "toggle" or field.value_type is bool:
            state = "✅" if value else "⬜"
            target = "0" if value else "1"
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{state} {field.label}",
                        callback_data=f"{CB_PREFIX}:s:{fhash}:{target}",
                    )
                ]
                + reset_btn
            )
        elif field.choices:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{'●' if choice == value else '○'} {choice}",
                        callback_data=f"{CB_PREFIX}:s:{fhash}:{choice}",
                    )
                    for choice in field.choices
                ]
                + reset_btn
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{field.label}: {_format_value(field, value)}{mark}",
                        callback_data=f"{CB_PREFIX}:n",
                    )
                ]
                + reset_btn
            )
            stepper = _stepper_row(field, value, fhash)
            if stepper:
                rows.append(stepper)

    if module_has_advanced_fields(module, chat_type):
        lines.append("")
        lines.append(ADVANCED_FOOTER)

    rows.append(
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=f"{CB_PREFIX}:m"),
            InlineKeyboardButton("❌ Закрити", callback_data=f"{CB_PREFIX}:x"),
        ]
    )
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def _parse_value(field: TelegramField, raw: str) -> Any:
    if field.value_type is bool:
        return raw == "1"
    if field.value_type is int:
        value: Any = int(raw)
    elif field.value_type is float:
        value = float(raw)
    else:
        value = raw
        if field.choices and value not in field.choices:
            raise ValueError(f"invalid choice: {value}")
        return value
    if field.ge is not None:
        value = max(value, field.ge)
    if field.le is not None:
        value = min(value, field.le)
    return field.value_type(value)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /config and /settings — show the settings menu."""
    chat = update.effective_chat
    if not chat or not update.message or chat.type not in (
        "private",
        "group",
        "supergroup",
    ):
        return

    if not await _is_allowed(update, context):
        await update.message.reply_text(MSG_ADMINS_ONLY)
        return

    chat_type = _normalize_chat_type(chat.type)
    chat_name = chat.title or (
        update.effective_user.full_name if update.effective_user else ""
    )
    await config_manager().ensure_chat(str(chat.id), chat.type, chat_name or "")

    text, markup = _build_root(chat_type)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def handle_config_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle all cfg:* callback presses (admin re-checked on every press)."""
    query = update.callback_query
    chat = update.effective_chat
    if not query or not query.data or not chat:
        return

    if not await _is_allowed(update, context):
        await query.answer(MSG_ADMINS_ONLY)
        return

    chat_id = str(chat.id)
    chat_type = _normalize_chat_type(chat.type)
    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    try:
        if action == "n":
            await query.answer()

        elif action == "x":
            await query.answer()
            if query.message:
                await query.message.delete()

        elif action == "m":
            await query.answer()
            text, markup = _build_root(chat_type)
            await _edit(query, text, markup)

        elif action == "c" and len(parts) == 3:
            module = parts[2]
            if module not in telegram_modules(chat_type):
                await query.answer(MSG_STALE_MENU, show_alert=True)
                return
            await query.answer()
            text, markup = await _build_category(chat_id, chat_type, module)
            await _edit(query, text, markup)

        elif action in ("s", "r") and len(parts) >= 3:
            field = _fields_by_hash(chat_type).get(parts[2])
            if field is None:
                await query.answer(MSG_STALE_MENU, show_alert=True)
                return
            mgr = config_manager()
            actor = telegram_actor(update.effective_user)
            if action == "s":
                value = _parse_value(field, ":".join(parts[3:]))
                await mgr.set_leaf(chat_id, field.module, field.path, value, actor=actor)
                await query.answer(MSG_SAVED)
            else:
                await mgr.reset_leaf(chat_id, field.module, field.path, actor=actor)
                await query.answer(MSG_RESET)
            text, markup = await _build_category(chat_id, chat_type, field.module)
            await _edit(query, text, markup)

        else:
            await query.answer(MSG_STALE_MENU, show_alert=True)

    except (ValueError, KeyError) as e:
        general_logger.warning(f"Invalid /config callback {query.data}: {e}")
        await query.answer(MSG_STALE_MENU, show_alert=True)
    except Exception as e:
        error_logger.error(
            f"Error handling /config callback {query.data}: {e}", exc_info=True
        )
        await query.answer("❌ Сталася помилка. Спробуйте ще раз.", show_alert=True)


async def _edit(query: Any, text: str, markup: InlineKeyboardMarkup) -> None:
    """Edit menu message in place, ignoring no-op edits."""
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise
