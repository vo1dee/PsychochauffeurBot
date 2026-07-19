# Backlog Issues

The following items are planned for future improvements:

4. **Re‑enable SSL verification and implement proper timeouts/backoff in VideoDownloader HTTP calls**
   - Remove `ssl=False`, enforce certificate verification.
   - Configure HTTP timeouts and exponential retry delays.

6. **Make the OpenAI model configurable**
   - Replace hard‑coded "gpt‑4.1" with an environment variable or config option.

9. **Improve screenshot scheduling with max‑retry and exponential backoff**
   - Prevent infinite loops on persistent failures in `ScreenshotManager.schedule_task()`.

12. **Refactor handler registration in `main.py`**
    - Dynamically discover and register command/message handlers instead of a static dict.

13. **Multilanguage support (eng/ukr) for the /config Telegram UI**
    - Handoff from the 2026-07 config-UI project: v1 ships Ukrainian-only
      (`label_uk`/`description_uk` in the schema with English fallback).
    - Add a proper language mechanism (per-chat or per-user language choice) and
      extend it to the rest of the bot's user-facing strings.

14. **Remove dead image-analysis feature code**
    - Handoff from the 2026-07 config-UI project: the `image_analysis` config
      context was removed from the schema; the feature code is now dead.
    - Delete `handle_photo_analysis` + its `filters.PHOTO` registration in
      `handler_registry.py`, the `analyze_image` path in `modules/gpt.py`, and
      related prompts/DB helpers.

15. **Telegram history view for the config audit ledger**
    - Handoff from the 2026-07 config-UI project: the audit ledger is write-only.
    - Add a "History" view (e.g. last N changes per category) in /config and/or
      a web UI page.