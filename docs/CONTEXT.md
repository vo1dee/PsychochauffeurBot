# PsychoChauffeur Bot — Configuration

The language of the bot's configuration system: how per-chat settings are defined,
who may change them, and how changes are recorded.

## Language

### Settings and values

**Config Module**:
A named group of related bot settings (GPT, Chat Behavior, Safety, Weather, Speech).
In the Telegram settings menu, each config module is presented as one category button.
_Avoid_: category, section

**Global Default**:
The value a setting has when no chat has overridden it.
_Avoid_: base value, fallback

**Override**:
A per-chat value that shadows the global default for one setting in one chat.
_Avoid_: custom value, chat value

**Effective Config**:
The settings a chat actually runs with — global defaults merged with that chat's overrides.
_Avoid_: chat config, merged config

**Reset**:
Removing an override so the setting follows the global default again (including future
changes to that default).
_Avoid_: delete, clear

### Exposure

**Curated Setting**:
A setting editable from inside Telegram via /config. The curated set is deliberately
small: toggles, selects, and bounded numbers.

**Advanced Setting**:
A setting not exposed in Telegram; changeable only by the Bot Owner.
_Avoid_: hidden setting

**Chat-type Visibility**:
Which chat types (group, private) a curated setting appears in. A setting invisible in
private chats is one that has no effect there.

### People

**Admin**:
A Telegram administrator or creator of a group chat — the only people who may change
that group's config. Checked on every button press, not just on the command.

**Bot Owner**:
vo1dee. The only person who changes advanced settings and global defaults.

### Accountability

**Actor**:
The identity responsible for a config change: a Telegram user, the web UI, or the system.

**Audit Ledger**:
The append-only record of config changes — what changed, old and new value, actor,
and source. Write-only for now; nothing in the bot reads it back.
_Avoid_: history, change log
