"""
Pydantic config schema models.

Each model defines a config module with typed fields, defaults, scope, and UI hints.
Adding a new setting = adding a field with Field(..., json_schema_extra={...}).

Scope:
  "global"   — setting only exists at global level, cannot be overridden per-chat
  "per_chat" — setting has a global default but can be overridden per-chat

Telegram exposure:
  telegram=("group", "private") — field is editable from the /config menu in those
  chat types. Fields without it are advanced settings (web UI / bot owner only).
  label_uk/description_uk are the strings the Telegram UI shows (English fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UI widget types (used by the web UI to render the right input)
# ---------------------------------------------------------------------------
class Widget(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SLIDER = "slider"
    TOGGLE = "toggle"
    SELECT = "select"
    TAGS = "tags"
    JSON = "json"


# ---------------------------------------------------------------------------
# Helper to attach scope + UI metadata to a field
# ---------------------------------------------------------------------------
def CField(
    default: Any = ...,
    *,
    scope: str = "per_chat",
    widget: Widget = Widget.TEXT,
    label: str = "",
    description: str = "",
    label_uk: str = "",
    description_uk: str = "",
    telegram: tuple[str, ...] | None = None,
    ge: float | None = None,
    le: float | None = None,
    choices: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Wrapper around pydantic Field that attaches config metadata."""
    extra: dict[str, Any] = {
        "scope": scope,
        "widget": widget.value,
    }
    if label:
        extra["label"] = label
    if description:
        extra["description"] = description
    if label_uk:
        extra["label_uk"] = label_uk
    if description_uk:
        extra["description_uk"] = description_uk
    if telegram is not None:
        extra["telegram"] = list(telegram)
    if choices is not None:
        extra["choices"] = choices

    field_kwargs: dict[str, Any] = {"json_schema_extra": extra, **kwargs}
    if ge is not None:
        field_kwargs["ge"] = ge
    if le is not None:
        field_kwargs["le"] = le

    return Field(default, **field_kwargs)


# ---------------------------------------------------------------------------
# GPT context sub-model (reused for command, mention, private, random, etc.)
# ---------------------------------------------------------------------------
class GPTContextConfig(BaseModel):
    enabled: bool = CField(True, widget=Widget.TOGGLE, label="Enabled")
    model: str = CField(
        "gpt-4.1-mini",
        widget=Widget.TEXT,
        label="Model",
        description="Any model name supported by OpenRouter",
    )
    max_tokens: int = CField(
        1500, widget=Widget.NUMBER, label="Max tokens", ge=1, le=16000
    )
    temperature: float = CField(
        0.6, widget=Widget.SLIDER, label="Temperature", ge=0.0, le=2.0
    )
    presence_penalty: float = CField(
        0.0, widget=Widget.SLIDER, label="Presence penalty", ge=-2.0, le=2.0
    )
    frequency_penalty: float = CField(
        0.0, widget=Widget.SLIDER, label="Frequency penalty", ge=-2.0, le=2.0
    )
    system_prompt: str = CField(
        "", widget=Widget.TEXTAREA, label="System prompt"
    )


# ---------------------------------------------------------------------------
# Module configs
# ---------------------------------------------------------------------------
class GPTConfig(BaseModel):
    """GPT / LLM settings per context."""

    __module_label__ = "GPT / LLM"
    __module_label_uk__ = "GPT / ШІ"
    __module_description_uk__ = "Відповіді штучного інтелекту: команди, згадки, аналіз."

    enabled: bool = CField(
        True,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Module enabled",
        label_uk="Модуль увімкнено",
        description_uk="Вимикає всі відповіді ШІ в цьому чаті.",
        telegram=("group", "private"),
    )

    command: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=1500,
            temperature=0.6,
            system_prompt=(
                "You are a helpful assistant. Respond to user commands in a clear "
                "and concise manner. If the user's request appears to be in Russian, "
                "respond in Ukrainian instead. Do not reply in Russian under any "
                "circumstance. You answer like a helpfull assistant and stick to the "
                "point of the conversation. Keep your responses concise and relevant "
                "to the conversation."
            ),
        )
    )
    mention: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=1200,
            temperature=0.5,
            system_prompt=(
                "You are a helpful assistant who responds to mentions in group chats. "
                "Keep your responses concise and relevant to the conversation. "
                "If the user's request appears to be in Russian, respond in Ukrainian "
                "instead. Do not reply in Russian under any circumstance."
            ),
        )
    )
    private: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=1000,
            temperature=0.7,
            system_prompt=(
                "You are a helpful assistant for private conversations. "
                "Keep your responses conversational and engaging."
            ),
        )
    )
    random: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=800,
            temperature=0.7,
            presence_penalty=0.1,
            frequency_penalty=0.1,
            system_prompt=(
                "You are a friendly assistant who occasionally joins conversations "
                "in group chats. Keep your responses casual and engaging."
            ),
        )
    )
    weather: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=400,
            temperature=0.2,
            system_prompt=(
                "You are a weather information assistant. "
                "Provide concise weather updates and forecasts."
            ),
        )
    )
    summary: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=800,
            temperature=0.3,
            presence_penalty=0.1,
            frequency_penalty=0.1,
            system_prompt=(
                "Do not reply in Russian under any circumstance. Always summarize "
                "in Ukrainian. If the user's request appears to be in Russian, respond "
                "in Ukrainian instead."
            ),
        )
    )
    analyze: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            max_tokens=1200,
            temperature=0.4,
            presence_penalty=0.1,
            frequency_penalty=0.1,
            system_prompt=(
                "You are an analytical assistant. Analyze the given information "
                "and provide insights."
            ),
        )
    )


class RandomResponseSettings(BaseModel):
    enabled: bool = CField(
        False,
        widget=Widget.TOGGLE,
        label="Enabled",
        label_uk="Випадкові відповіді",
        description_uk="Бот час від часу сам відповідає в чаті.",
        telegram=("group",),
    )
    min_words: int = CField(
        5,
        widget=Widget.NUMBER,
        label="Min words",
        label_uk="Мін. слів",
        description_uk="Мінімальна кількість слів у повідомленні для випадкової відповіді.",
        telegram=("group",),
        ge=1,
        le=100,
    )
    message_threshold: int = CField(
        50,
        widget=Widget.NUMBER,
        label="Message threshold",
        label_uk="Поріг повідомлень",
        description_uk="Скільки повідомлень має накопичитися перед випадковою відповіддю.",
        telegram=("group",),
        ge=1,
        le=1000,
    )
    probability: float = CField(
        0.02,
        widget=Widget.SLIDER,
        label="Probability",
        label_uk="Ймовірність",
        description_uk="Ймовірність випадкової відповіді (від 0 до 1).",
        telegram=("group",),
        ge=0.0,
        le=1.0,
    )
    context_messages_count: int = CField(
        3, widget=Widget.NUMBER, label="Context messages", ge=1, le=50
    )


class ChatBehaviorConfig(BaseModel):
    """Chat behavior and restrictions."""

    __module_label__ = "Chat Behavior"
    __module_label_uk__ = "Поведінка чату"
    __module_description_uk__ = "Обмеження команд та випадкові відповіді."

    enabled: bool = CField(
        True,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Module enabled",
        label_uk="Модуль увімкнено",
        description_uk="Вимикає обмеження та випадкові відповіді.",
        telegram=("group",),
    )
    restrictions_enabled: bool = CField(
        False,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Restrictions enabled",
        label_uk="Обмеження команд",
        description_uk="Дозволяє лише команди зі списку дозволених.",
        telegram=("group",),
    )
    allowed_commands: list[str] = CField(
        default_factory=lambda: ["help", "weather", "cat", "gpt", "analyze", "gm"],
        scope="per_chat",
        widget=Widget.TAGS,
        label="Allowed commands",
    )
    ban_words: list[str] = CField(
        default_factory=list,
        scope="per_chat",
        widget=Widget.TAGS,
        label="Banned words",
    )
    ban_symbols: list[str] = CField(
        default_factory=list,
        scope="per_chat",
        widget=Widget.TAGS,
        label="Banned symbols",
    )
    random_response_settings: RandomResponseSettings = Field(
        default_factory=RandomResponseSettings
    )
    restriction_sticker_id: str = CField(
        "", scope="per_chat", widget=Widget.TEXT, label="Restriction sticker ID"
    )
    restriction_sticker_unique_id: str = CField(
        "AgAD6BQAAh-z-FM",
        scope="per_chat",
        widget=Widget.TEXT,
        label="Restriction sticker unique ID",
    )


class SafetyConfig(BaseModel):
    """File safety / allowed types."""

    __module_label__ = "Safety"
    __module_label_uk__ = "Безпека"
    __module_description_uk__ = "Фільтрація файлів за типом."

    enabled: bool = CField(
        True,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Module enabled",
        label_uk="Модуль увімкнено",
        description_uk="Вимикає перевірку типів файлів.",
        telegram=("group", "private"),
    )
    allowed_file_types: list[str] = CField(
        default_factory=lambda: [
            "image/jpeg",
            "image/png",
            "image/gif",
            "video/mp4",
            "video/quicktime",
        ],
        scope="global",
        widget=Widget.TAGS,
        label="Allowed file types",
    )


class WeatherConfig(BaseModel):
    """Weather module settings."""

    __module_label__ = "Weather"
    __module_label_uk__ = "Погода"
    __module_description_uk__ = "Команда /weather та прогнози."

    enabled: bool = CField(
        True,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Module enabled",
        label_uk="Модуль увімкнено",
        description_uk="Вимикає команди погоди в цьому чаті.",
        telegram=("group", "private"),
    )
    units: str = CField(
        "metric",
        scope="per_chat",
        widget=Widget.SELECT,
        label="Units",
        label_uk="Одиниці",
        description_uk="Метричні (°C) або імперські (°F) одиниці.",
        telegram=("group", "private"),
        choices=["metric", "imperial"],
    )


class SpeechmaticsConfig(BaseModel):
    """Speech recognition settings."""

    __module_label__ = "Speech Recognition"
    __module_label_uk__ = "Розпізнавання мовлення"
    __module_description_uk__ = "Перетворення голосових повідомлень на текст."

    enabled: bool = CField(
        True,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Module enabled",
        label_uk="Модуль увімкнено",
        description_uk="Вимикає розпізнавання голосових у цьому чаті.",
        telegram=("group", "private"),
    )
    allow_all_users: bool = CField(
        False,
        scope="per_chat",
        widget=Widget.TOGGLE,
        label="Allow all users",
        label_uk="Дозволити всім",
        description_uk="Розпізнавання доступне всім користувачам, не лише адмінам.",
        telegram=("group",),
    )


# ---------------------------------------------------------------------------
# Registry — maps module key → Pydantic model class
# ---------------------------------------------------------------------------
MODULE_REGISTRY: dict[str, type[BaseModel]] = {
    "gpt": GPTConfig,
    "chat_behavior": ChatBehaviorConfig,
    "safety": SafetyConfig,
    "weather": WeatherConfig,
    "speechmatics": SpeechmaticsConfig,
}


def get_module_label(key: str, lang: str = "en") -> str:
    """Return human-readable label for a module key."""
    model = MODULE_REGISTRY.get(key)
    if model:
        if lang == "uk" and hasattr(model, "__module_label_uk__"):
            return model.__module_label_uk__  # type: ignore[return-value]
        if hasattr(model, "__module_label__"):
            return model.__module_label__  # type: ignore[return-value]
    return key.replace("_", " ").title()


def get_module_description(key: str, lang: str = "uk") -> str:
    """Return the module description shown in the Telegram UI."""
    model = MODULE_REGISTRY.get(key)
    if model and lang == "uk" and hasattr(model, "__module_description_uk__"):
        return model.__module_description_uk__  # type: ignore[return-value]
    return ""


# ---------------------------------------------------------------------------
# Telegram exposure — enumeration of curated fields for the /config menu
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TelegramField:
    """A schema field exposed in the Telegram /config menu."""

    module: str
    path: str  # dotted path within the module, e.g. "random_response_settings.probability"
    value_type: type
    widget: str
    label: str
    description: str
    default: Any
    ge: float | None = None
    le: float | None = None
    choices: list[str] | None = None


def _iter_model_fields(
    module: str, model_class: type[BaseModel], chat_type: str, prefix: str = ""
) -> list[TelegramField]:
    fields: list[TelegramField] = []
    for name, field_info in model_class.model_fields.items():
        path = f"{prefix}{name}"
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            fields.extend(
                _iter_model_fields(module, annotation, chat_type, prefix=f"{path}.")
            )
            continue

        extra = field_info.json_schema_extra
        if not isinstance(extra, dict):
            continue
        exposure = extra.get("telegram")
        if not exposure or chat_type not in exposure:
            continue

        ge = le = None
        for meta in field_info.metadata:
            if hasattr(meta, "ge"):
                ge = float(meta.ge)
            if hasattr(meta, "le"):
                le = float(meta.le)

        fields.append(
            TelegramField(
                module=module,
                path=path,
                value_type=annotation if isinstance(annotation, type) else str,
                widget=str(extra.get("widget", Widget.TEXT.value)),
                label=str(extra.get("label_uk") or extra.get("label") or name),
                description=str(extra.get("description_uk") or extra.get("description") or ""),
                default=field_info.get_default(call_default_factory=True),
                ge=ge,
                le=le,
                choices=list(extra["choices"]) if extra.get("choices") else None,
            )
        )
    return fields


def telegram_fields(module: str, chat_type: str) -> list[TelegramField]:
    """Curated fields of a module editable from Telegram in the given chat type.

    chat_type is normalized: "supergroup" counts as "group".
    """
    if chat_type == "supergroup":
        chat_type = "group"
    model_class = MODULE_REGISTRY.get(module)
    if not model_class or chat_type not in ("group", "private"):
        return []
    return _iter_model_fields(module, model_class, chat_type)


def telegram_modules(chat_type: str) -> list[str]:
    """Module keys that have at least one Telegram-editable field for this chat type."""
    return [key for key in MODULE_REGISTRY if telegram_fields(key, chat_type)]


def module_has_advanced_fields(module: str, chat_type: str) -> bool:
    """True if the module has settings NOT exposed in Telegram for this chat type."""
    model_class = MODULE_REGISTRY.get(module)
    if not model_class:
        return False
    exposed = {f.path for f in telegram_fields(module, chat_type)}

    def count_leaves(model: type[BaseModel], prefix: str = "") -> int:
        total = 0
        for name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                total += count_leaves(annotation, prefix=f"{prefix}{name}.")
            elif f"{prefix}{name}" not in exposed:
                total += 1
        return total

    return count_leaves(model_class) > 0
