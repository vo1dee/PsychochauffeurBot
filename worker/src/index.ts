export interface Env {
  DATA_DB: D1Database;
  CONFIG_DB: D1Database;
  D1_API_TOKEN: string;
}

type JsonRecord = Record<string, unknown>;

function response(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function stringValue(value: unknown, field: string, required = true): string | null {
  if (typeof value === "string") return value;
  if (!required && (value === null || value === undefined)) return null;
  throw new Error(`${field} must be a string`);
}

function integerValue(value: unknown, field: string, required = true): number | null {
  if (typeof value === "number" && Number.isSafeInteger(value)) return value;
  if (!required && (value === null || value === undefined)) return null;
  throw new Error(`${field} must be an integer`);
}

function booleanValue(value: unknown, field: string, defaultValue = false): number {
  if (value === undefined) return defaultValue ? 1 : 0;
  if (typeof value !== "boolean") throw new Error(`${field} must be a boolean`);
  return value ? 1 : 0;
}

async function requestBody(request: Request): Promise<JsonRecord> {
  const value: unknown = await request.json();
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("JSON object required");
  return value as JsonRecord;
}

function authorized(request: Request, env: Env): boolean {
  return request.headers.get("Authorization") === `Bearer ${env.D1_API_TOKEN}`;
}

function isoTimestamp(value: unknown, field: string, required = true): string | null {
  const timestamp = stringValue(value, field, required);
  if (timestamp === null) return null;
  if (Number.isNaN(Date.parse(timestamp))) throw new Error(`${field} must be an ISO-8601 timestamp`);
  return timestamp;
}

async function dataOperation(path: string, body: JsonRecord, db: D1Database): Promise<unknown> {
  if (path === "/v1/data/chat") {
    const chatId = integerValue(body.chat_id, "chat_id");
    await db.prepare("INSERT INTO chats (chat_id, chat_type, title) VALUES (?, ?, ?) ON CONFLICT(chat_id) DO UPDATE SET chat_type = excluded.chat_type, title = excluded.title")
      .bind(chatId, stringValue(body.chat_type, "chat_type"), stringValue(body.title, "title", false)).run();
    return { ok: true };
  }
  if (path === "/v1/data/user") {
    const userId = integerValue(body.user_id, "user_id");
    await db.prepare("INSERT INTO users (user_id, first_name, last_name, username, is_bot) VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET first_name = excluded.first_name, last_name = excluded.last_name, username = excluded.username, is_bot = excluded.is_bot")
      .bind(userId, stringValue(body.first_name, "first_name"), stringValue(body.last_name, "last_name", false), stringValue(body.username, "username", false), booleanValue(body.is_bot, "is_bot")).run();
    return { ok: true };
  }
  if (path === "/v1/data/message") {
    await db.prepare(`INSERT INTO messages (message_id, chat_id, user_id, timestamp, text, is_command, command_name, is_gpt_reply, replied_to_message_id, gpt_context_message_ids, raw_telegram_message)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(chat_id, message_id) DO NOTHING`).bind(
      integerValue(body.message_id, "message_id"), integerValue(body.chat_id, "chat_id"), integerValue(body.user_id, "user_id", false),
      isoTimestamp(body.timestamp, "timestamp"), stringValue(body.text, "text", false), booleanValue(body.is_command, "is_command"),
      stringValue(body.command_name, "command_name", false), booleanValue(body.is_gpt_reply, "is_gpt_reply"),
      integerValue(body.replied_to_message_id, "replied_to_message_id", false), stringValue(body.gpt_context_message_ids, "gpt_context_message_ids", false),
      stringValue(body.raw_telegram_message, "raw_telegram_message", false)).run();
    return { ok: true };
  }
  if (path === "/v1/data/event") {
    await db.prepare("INSERT INTO bot_events (event_type, chat_id, user_id, timestamp) VALUES (?, ?, ?, ?)").bind(
      stringValue(body.event_type, "event_type"), integerValue(body.chat_id, "chat_id"), integerValue(body.user_id, "user_id", false),
      isoTimestamp(body.timestamp, "timestamp", false) ?? new Date().toISOString()).run();
    return { ok: true };
  }
  if (path === "/v1/data/cache/set") {
    await db.prepare(`INSERT INTO analysis_cache (chat_id, time_period, message_content_hash, result, created_at) VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(chat_id, time_period, message_content_hash) DO UPDATE SET result = excluded.result, created_at = excluded.created_at`).bind(
      integerValue(body.chat_id, "chat_id"), stringValue(body.time_period, "time_period"), stringValue(body.message_content_hash, "message_content_hash"),
      stringValue(body.result, "result"), new Date().toISOString()).run();
    return { ok: true };
  }
  if (path === "/v1/data/cache/get") {
    const row = await db.prepare("SELECT result, created_at FROM analysis_cache WHERE chat_id = ? AND time_period = ? AND message_content_hash = ?").bind(
      integerValue(body.chat_id, "chat_id"), stringValue(body.time_period, "time_period"), stringValue(body.message_content_hash, "message_content_hash")).first();
    return { row };
  }
  if (path === "/v1/data/cache/delete") {
    const chatId = integerValue(body.chat_id, "chat_id");
    const period = stringValue(body.time_period, "time_period", false);
    const result = period === null
      ? await db.prepare("DELETE FROM analysis_cache WHERE chat_id = ?").bind(chatId).run()
      : await db.prepare("DELETE FROM analysis_cache WHERE chat_id = ? AND time_period = ?").bind(chatId, period).run();
    return { deleted: result.meta.changes };
  }
  if (path === "/v1/data/recap/upsert") {
    // The bot sends the full PostgreSQL row after every change; an out-of-order older row is ignored.
    const sendTime = stringValue(body.send_time, "send_time");
    if (sendTime === null || !/^([01]\d|2[0-3]):[0-5]\d$/.test(sendTime)) throw new Error("send_time must be HH:MM");
    const lastSentDate = stringValue(body.last_sent_date, "last_sent_date", false);
    if (lastSentDate !== null && !/^\d{4}-\d{2}-\d{2}$/.test(lastSentDate)) throw new Error("last_sent_date must be YYYY-MM-DD");
    await db.prepare(`INSERT INTO chat_recap_settings (chat_id, enabled, send_time, last_sent_date, last_pinned_message_id, updated_at)
      VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled, send_time = excluded.send_time,
      last_sent_date = excluded.last_sent_date, last_pinned_message_id = excluded.last_pinned_message_id, updated_at = excluded.updated_at
      WHERE julianday(excluded.updated_at) >= julianday(chat_recap_settings.updated_at)`).bind(
      integerValue(body.chat_id, "chat_id"), booleanValue(body.enabled, "enabled"), sendTime, lastSentDate,
      integerValue(body.last_pinned_message_id, "last_pinned_message_id", false),
      isoTimestamp(body.updated_at, "updated_at", false) ?? new Date().toISOString()).run();
    return { ok: true };
  }
  if (path === "/v1/data/messages/recent") {
    const limit = integerValue(body.limit, "limit");
    if (limit === null || limit < 1 || limit > 200) throw new Error("limit must be between 1 and 200");
    const commands = booleanValue(body.include_commands, "include_commands", true);
    const result = await db.prepare(`SELECT message_id, user_id, timestamp, text, is_command, command_name, is_gpt_reply FROM messages
      WHERE chat_id = ? AND (? = 1 OR is_command = 0) ORDER BY timestamp DESC LIMIT ?`).bind(integerValue(body.chat_id, "chat_id"), commands, limit).all();
    return { rows: result.results };
  }
  if (path === "/v1/data/messages/count") {
    const result = await db.prepare(`SELECT COUNT(*) AS count FROM messages WHERE chat_id = ?
      AND (? IS NULL OR user_id = ?) AND (? IS NULL OR timestamp >= ?) AND (? IS NULL OR text LIKE '%' || ? || '%')`).bind(
      integerValue(body.chat_id, "chat_id"), integerValue(body.user_id, "user_id", false), integerValue(body.user_id, "user_id", false),
      isoTimestamp(body.since, "since", false), isoTimestamp(body.since, "since", false), stringValue(body.text_filter, "text_filter", false), stringValue(body.text_filter, "text_filter", false)).first<{ count: number }>();
    return { count: result?.count ?? 0 };
  }
  throw new Error("Unknown data operation");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") return response({ error: "Not found" }, 404);
    if (!authorized(request, env)) return response({ error: "Unauthorized" }, 401);
    try {
      const path = new URL(request.url).pathname;
      const body = await requestBody(request);
      if (path.startsWith("/v1/data/")) return response(await dataOperation(path, body, env.DATA_DB));
      return response({ error: "Not found" }, 404);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid request";
      return response({ error: message }, 400);
    }
  },
};
