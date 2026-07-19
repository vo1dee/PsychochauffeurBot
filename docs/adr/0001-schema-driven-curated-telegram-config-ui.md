# Schema-driven, curated, buttons-only Telegram config UI

The `/config` (alias `/settings`) Telegram menu is generated entirely from the
`config_v2` Pydantic schema metadata — new per-field flags mark Telegram exposure,
chat-type visibility (group/private), and Ukrainian labels/descriptions. Only a
small curated subset of settings (toggles, selects, bounded numbers) is editable
from Telegram; every other setting shows "ask @vo1dee" instead. All interaction is
inline buttons — there is deliberately **no typed-text input**: numeric fields use
stepper buttons whose `callback_data` encodes **absolute target values**, making
presses idempotent, stateless across bot restarts, and race-safe (last write wins)
when two admins or the web UI edit concurrently.

## Considered Options

- **Full-depth menu tree with ForceReply text input** — complete coverage of ~70
  nested fields, rejected: requires per-user pending-input conversation state,
  timeout handling, and validation round-trips in busy groups; the advanced fields
  (system prompts, ban-word lists) are owner-level knobs anyway.
- **Hand-maintained UI taxonomy separate from schema modules** — friendlier
  grouping, rejected: a permanent mapping layer to keep in sync with the schema.

## Consequences

- Adding a setting to the Telegram UI = annotating its schema field; no UI code.
- Group-chat authorization is enforced per button press (admin/creator check on
  every callback), because inline keyboards in groups are pressable by anyone.
