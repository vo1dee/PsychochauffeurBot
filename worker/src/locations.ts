// Saved /weather cities (table user_locations). chat_id 0 is the user's home city.

export const HOME_CHAT_ID = 0;
export const MAX_CITY_LENGTH = 100;

export function normalizeCity(value: unknown): string {
  if (typeof value !== "string") throw new Error("city must be a string");
  const city = value.trim();
  if (!city || city.length > MAX_CITY_LENGTH) throw new Error(`city must be 1-${MAX_CITY_LENGTH} characters`);
  return city;
}

// Upsert; an older updated_at (e.g. from a CSV import) never overwrites a newer value.
export async function setLocation(db: D1Database, userId: number, chatId: number, city: string, updatedAt?: string): Promise<void> {
  await db.prepare(`INSERT INTO user_locations (user_id, chat_id, city, updated_at) VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id, chat_id) DO UPDATE SET city = excluded.city, updated_at = excluded.updated_at
    WHERE julianday(excluded.updated_at) >= julianday(user_locations.updated_at)`)
    .bind(userId, chatId, city, updatedAt ?? new Date().toISOString()).run();
}

// The chat override wins over the home city; pass chatId null (or 0) for the home city only.
export async function getLocation(db: D1Database, userId: number, chatId: number | null): Promise<string | null> {
  const row = await db.prepare(`SELECT city FROM user_locations WHERE user_id = ? AND chat_id IN (?, ?)
    ORDER BY CASE WHEN chat_id = ? THEN 0 ELSE 1 END LIMIT 1`)
    .bind(userId, chatId ?? HOME_CHAT_ID, HOME_CHAT_ID, chatId ?? HOME_CHAT_ID).first<{ city: string }>();
  return row?.city ?? null;
}
