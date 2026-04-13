"""
Pydantic config schema models.

Each model defines a config module with typed fields, defaults, scope, and UI hints.
Adding a new setting = adding a field with Field(..., json_schema_extra={...}).

Scope:
  "global"   — setting only exists at global level, cannot be overridden per-chat
  "per_chat" — setting has a global default but can be overridden per-chat
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

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

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")

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
    image_analysis: GPTContextConfig = Field(
        default_factory=lambda: GPTContextConfig(
            enabled=False,
            max_tokens=250,
            temperature=0.2,
            system_prompt=(
                "You are an image analysis assistant. Provide detailed descriptions "
                "and analysis of images. Describe the main elements in 2-3 concise "
                "sentences. Focus on objects, people, settings, actions, and context. "
                "Do not speculate beyond what is clearly visible. Keep descriptions "
                "factual and objective."
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
    enabled: bool = CField(False, widget=Widget.TOGGLE, label="Enabled")
    min_words: int = CField(5, widget=Widget.NUMBER, label="Min words", ge=1)
    message_threshold: int = CField(
        50, widget=Widget.NUMBER, label="Message threshold", ge=1
    )
    probability: float = CField(
        0.02, widget=Widget.SLIDER, label="Probability", ge=0.0, le=1.0
    )
    context_messages_count: int = CField(
        3, widget=Widget.NUMBER, label="Context messages", ge=1, le=50
    )


class ChatBehaviorConfig(BaseModel):
    """Chat behavior and restrictions."""

    __module_label__ = "Chat Behavior"

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
    restrictions_enabled: bool = CField(
        False, scope="per_chat", widget=Widget.TOGGLE, label="Restrictions enabled"
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

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
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

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
    units: str = CField(
        "metric",
        scope="global",
        widget=Widget.SELECT,
        label="Units",
        choices=["metric", "imperial"],
    )


class SpeechmaticsConfig(BaseModel):
    """Speech recognition settings."""

    __module_label__ = "Speech Recognition"

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
    allow_all_users: bool = CField(
        False, scope="per_chat", widget=Widget.TOGGLE, label="Allow all users"
    )


class VideoSendConfig(BaseModel):
    """Video download / send settings."""

    __module_label__ = "Video Send"

    enabled: bool = CField(True, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
    send_video_file: bool = CField(
        False, scope="per_chat", widget=Widget.TOGGLE, label="Send as video file"
    )
    video_path: str = CField(
        "downloads", scope="global", widget=Widget.TEXT, label="Video path"
    )
    before_video_path: Optional[str] = CField(
        None, scope="global", widget=Widget.TEXT, label="Before video path"
    )


class RemindersConfig(BaseModel):
    """Reminders module settings."""

    __module_label__ = "Reminders"

    enabled: bool = CField(False, scope="per_chat", widget=Widget.TOGGLE, label="Module enabled")
    max_reminders_per_user: int = CField(
        5, scope="global", widget=Widget.NUMBER, label="Max reminders per user", ge=1
    )
    max_reminder_duration_days: int = CField(
        30, scope="global", widget=Widget.NUMBER, label="Max duration (days)", ge=1
    )
    reminder_notification_interval_minutes: int = CField(
        60, scope="global", widget=Widget.NUMBER, label="Notification interval (min)", ge=1
    )
    allow_recurring_reminders: bool = CField(
        True, scope="global", widget=Widget.TOGGLE, label="Allow recurring"
    )
    max_recurring_reminders: int = CField(
        3, scope="global", widget=Widget.NUMBER, label="Max recurring", ge=1
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
    "video_send": VideoSendConfig,
    "reminders": RemindersConfig,
}


def get_module_label(key: str) -> str:
    """Return human-readable label for a module key."""
    model = MODULE_REGISTRY.get(key)
    if model and hasattr(model, "__module_label__"):
        return model.__module_label__  # type: ignore[return-value]
    return key.replace("_", " ").title()
