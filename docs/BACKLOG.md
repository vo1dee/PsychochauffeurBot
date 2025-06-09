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