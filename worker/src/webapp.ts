// Demo Telegram Mini App: a small weather page served at GET /webapp.
// POST /webapp/verify checks Telegram initData server-side (HMAC with the bot token);
// POST /webapp/location[/save] read and write the user's home city (shared with /weather).

import { getLocation, HOME_CHAT_ID, normalizeCity, setLocation } from "./locations";

export interface WebAppEnv {
  DATA_DB: D1Database;
  TELEGRAM_BOT_TOKEN?: string;
}

const INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60;

const PAGE = `<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Погода</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  /* Fallback palette for when Telegram doesn't provide theme params (e.g. a plain browser). */
  :root {
    --fb-bg: #ffffff; --fb-text: #111111; --fb-hint: #888888;
    --fb-card: #f2f2f5; --fb-accent: #2481cc; --fb-accent-text: #ffffff;
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --fb-bg: #17212b; --fb-text: #f5f5f5; --fb-hint: #708499;
      --fb-card: #232e3c; --fb-accent: #5288c1; --fb-accent-text: #ffffff;
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --fb-bg: #17212b; --fb-text: #f5f5f5; --fb-hint: #708499;
    --fb-card: #232e3c; --fb-accent: #5288c1; --fb-accent-text: #ffffff;
    color-scheme: dark;
  }
  /* Telegram's theme params (set by telegram-web-app.js) win over the fallbacks. */
  :root {
    --bg: var(--tg-theme-bg-color, var(--fb-bg));
    --text: var(--tg-theme-text-color, var(--fb-text));
    --hint: var(--tg-theme-hint-color, var(--fb-hint));
    --card: var(--tg-theme-secondary-bg-color, var(--fb-card));
    --accent: var(--tg-theme-button-color, var(--fb-accent));
    --accent-text: var(--tg-theme-button-text-color, var(--fb-accent-text));
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 16px; background: var(--bg); color: var(--text);
         font: 16px/1.4 -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .hint { color: var(--hint); font-size: 14px; }
  form { display: flex; gap: 8px; margin: 16px 0; }
  input { flex: 1; min-width: 0; padding: 10px 12px; border: none; border-radius: 10px;
          background: var(--card); color: var(--text); font-size: 16px; }
  button { padding: 10px 14px; border: none; border-radius: 10px; background: var(--accent);
           color: var(--accent-text); font-size: 16px; }
  .card { background: var(--card); border-radius: 14px; padding: 14px; margin-bottom: 12px; }
  .now { display: flex; align-items: center; gap: 12px; }
  .now .icon { font-size: 44px; }
  .now .temp { font-size: 34px; font-weight: 600; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; margin-top: 10px; font-size: 15px; }
  .days { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
  .days .icon { font-size: 26px; }
  details summary { cursor: pointer; }
  .saved { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .saved button { padding: 8px 12px; font-size: 15px; }
  pre { white-space: pre-wrap; word-break: break-all; font-size: 12px; margin: 8px 0 0; }
</style>
</head>
<body>
  <h1 id="hello">Погода</h1>
  <div class="hint" id="env"></div>

  <form id="search">
    <input id="city" placeholder="Місто" autocomplete="off">
    <button type="submit">Знайти</button>
  </form>

  <div id="result"><div class="hint">Завантаження…</div></div>

  <div class="card saved" id="saved" hidden>
    <span id="saved-text"></span>
    <button type="button" id="save" hidden></button>
  </div>

  <details class="card">
    <summary>🔐 Перевірка initData на сервері</summary>
    <pre id="verify">…</pre>
  </details>

<script>
  const tg = window.Telegram && window.Telegram.WebApp;
  const user = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;

  // Inside Telegram follow its light/dark mode; in a plain browser the CSS media query decides.
  function applyTheme() {
    if (!tg || !tg.initData) return;
    document.documentElement.dataset.theme = tg.colorScheme;
    try {
      tg.setHeaderColor("bg_color");
      tg.setBackgroundColor("bg_color");
    } catch (e) { /* older Telegram clients */ }
  }

  if (tg) {
    applyTheme();
    tg.onEvent("themeChanged", applyTheme);
    tg.ready();
    tg.expand();
    tg.MainButton.setText("Закрити");
    tg.MainButton.onClick(() => tg.close());
    tg.MainButton.show();
  }
  document.getElementById("hello").textContent = user ? "Привіт, " + user.first_name + "!" : "Погода";
  document.getElementById("env").textContent = tg && tg.initData
    ? "Відкрито в Telegram · " + tg.platform + " · тема " + tg.colorScheme
    : "Відкрито не в Telegram (звичайний браузер)";

  const CODES = {
    0: ["☀️", "Ясно"], 1: ["🌤", "Переважно ясно"], 2: ["⛅️", "Мінлива хмарність"], 3: ["☁️", "Хмарно"],
    45: ["🌫", "Туман"], 48: ["🌫", "Туман"], 51: ["🌦", "Мряка"], 53: ["🌦", "Мряка"], 55: ["🌦", "Мряка"],
    61: ["🌧", "Дощ"], 63: ["🌧", "Дощ"], 65: ["🌧", "Сильний дощ"], 66: ["🌧", "Крижаний дощ"], 67: ["🌧", "Крижаний дощ"],
    71: ["🌨", "Сніг"], 73: ["🌨", "Сніг"], 75: ["❄️", "Сильний сніг"], 77: ["🌨", "Снігова крупа"],
    80: ["🌦", "Злива"], 81: ["🌦", "Злива"], 82: ["⛈", "Сильна злива"], 85: ["🌨", "Снігопад"], 86: ["🌨", "Снігопад"],
    95: ["⛈", "Гроза"], 96: ["⛈", "Гроза з градом"], 99: ["⛈", "Гроза з градом"],
  };
  const code = (c) => CODES[c] || ["🌡", "—"];

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const DEFAULT_CITY = "Київ";
  const signedIn = Boolean(tg && tg.initData);
  let savedCity = null;   // the user's home city, shared with /weather
  let shownCity = null;   // the city currently on screen
  let savedAlias = null;  // geocoded name of savedCity (e.g. "Львів" for a bot-saved "Lviv")

  async function api(path, payload) {
    const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify(Object.assign({ initData: tg.initData }, payload)) });
    return res.json();
  }

  function renderSaved() {
    const box = document.getElementById("saved");
    const button = document.getElementById("save");
    if (!signedIn) { box.hidden = true; return; }
    box.hidden = false;
    document.getElementById("saved-text").textContent = savedCity ? "⭐ Ваше місто: " + savedCity : "⭐ Місто не збережено";
    button.hidden = !shownCity || shownCity === savedCity || shownCity === savedAlias;
    button.textContent = "Зберегти " + shownCity;
  }

  async function saveCity() {
    const button = document.getElementById("save");
    button.disabled = true;
    try {
      const data = await api("/webapp/location/save", { city: shownCity });
      if (!data.ok) throw new Error(data.reason || "не вдалося зберегти");
      savedCity = data.city;
      savedAlias = null;
      if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (e) {
      tg.showAlert ? tg.showAlert("Помилка: " + e.message) : alert(e.message);
    } finally {
      button.disabled = false;
      renderSaved();
    }
  }

  async function load(name, isSaved) {
    const result = document.getElementById("result");
    result.replaceChildren(el("div", "hint", "Завантаження…"));
    try {
      const geo = await fetch("https://geocoding-api.open-meteo.com/v1/search?count=1&language=uk&name=" + encodeURIComponent(name)).then(r => r.json());
      const place = geo.results && geo.results[0];
      if (!place) throw new Error("Місто не знайдено");
      const params = new URLSearchParams({
        latitude: place.latitude, longitude: place.longitude, timezone: "auto", forecast_days: "3",
        current: "temperature_2m,apparent_temperature,relative_humidity_2m,surface_pressure,wind_speed_10m,weather_code",
        daily: "weather_code,temperature_2m_max,temperature_2m_min",
      });
      const w = await fetch("https://api.open-meteo.com/v1/forecast?" + params).then(r => r.json());
      if (isSaved) savedAlias = place.name;
      render(place, w);
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    } catch (e) {
      result.replaceChildren(el("div", "card", "⚠️ " + e.message));
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
    }
  }

  function render(place, w) {
    const c = w.current;
    const [icon, label] = code(c.weather_code);
    const now = el("div", "card");
    now.append(el("div", "hint", place.name + (place.country ? ", " + place.country : "")));
    const row = el("div", "now");
    row.append(el("div", "icon", icon), el("div", "temp", Math.round(c.temperature_2m) + "°C"), el("div", "", label));
    const grid = el("div", "grid");
    grid.append(
      el("div", "", "🤔 Відчувається: " + Math.round(c.apparent_temperature) + "°C"),
      el("div", "", "💧 Вологість: " + c.relative_humidity_2m + "%"),
      el("div", "", "📊 Тиск: " + Math.round(c.surface_pressure) + " гПа"),
      el("div", "", "💨 Вітер: " + Math.round(c.wind_speed_10m) + " км/год"),
    );
    now.append(row, grid);

    const days = el("div", "card days");
    w.daily.time.forEach((day, i) => {
      const d = el("div");
      const weekday = new Date(day).toLocaleDateString("uk-UA", { weekday: "short" });
      d.append(
        el("div", "hint", weekday),
        el("div", "icon", code(w.daily.weather_code[i])[0]),
        el("div", "", Math.round(w.daily.temperature_2m_max[i]) + "° / " + Math.round(w.daily.temperature_2m_min[i]) + "°"),
      );
      days.append(d);
    });

    document.getElementById("result").replaceChildren(now, days);
    shownCity = place.name;
    document.getElementById("city").value = place.name;
    renderSaved();
  }

  async function verify() {
    const out = document.getElementById("verify");
    if (!tg || !tg.initData) { out.textContent = "Немає initData — сторінку відкрито поза Telegram."; return; }
    try {
      const res = await fetch("/webapp/verify", { method: "POST", headers: { "Content-Type": "application/json" },
                                                 body: JSON.stringify({ initData: tg.initData }) });
      out.textContent = JSON.stringify(await res.json(), null, 2);
    } catch (e) {
      out.textContent = "Помилка: " + e.message;
    }
  }

  document.getElementById("search").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("city").value.trim();
    if (name) load(name);
  });
  document.getElementById("save").addEventListener("click", saveCity);

  async function start() {
    if (signedIn) {
      try {
        const data = await api("/webapp/location", {});
        if (data.ok) savedCity = data.city;
      } catch (e) { /* fall back to the default city */ }
    }
    if (savedCity) load(savedCity, true);
    else load(DEFAULT_CITY);
  }
  start();
  verify();
</script>
</body>
</html>`;

async function hmacSha256(key: ArrayBuffer | Uint8Array, data: string): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(data));
}

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
export async function verifyInitData(initData: string, botToken: string, nowSeconds = Math.floor(Date.now() / 1000)): Promise<{ ok: boolean; reason?: string; user?: unknown }> {
  const params = new URLSearchParams(initData);
  const hash = params.get("hash");
  if (!hash) return { ok: false, reason: "hash missing" };
  params.delete("hash");
  const dataCheckString = Array.from(params.entries())
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
  const secretKey = await hmacSha256(new TextEncoder().encode("WebAppData"), botToken);
  const expected = toHex(await hmacSha256(secretKey, dataCheckString));
  if (expected !== hash) return { ok: false, reason: "bad signature" };
  const authDate = Number(params.get("auth_date"));
  if (!Number.isFinite(authDate) || nowSeconds - authDate > INIT_DATA_MAX_AGE_SECONDS) return { ok: false, reason: "initData expired" };
  const user = params.get("user");
  return { ok: true, user: user ? JSON.parse(user) : null };
}

type InitDataUser = { id: number };

async function readJson(request: Request): Promise<Record<string, unknown>> {
  const body: unknown = await request.json();
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("JSON object required");
  return body as Record<string, unknown>;
}

// Verifies initData from the request body; returns the Telegram user or an error Response.
async function authenticate(body: Record<string, unknown>, env: WebAppEnv): Promise<InitDataUser | Response> {
  if (!env.TELEGRAM_BOT_TOKEN) return Response.json({ ok: false, reason: "TELEGRAM_BOT_TOKEN secret is not set on the worker" }, { status: 503 });
  if (typeof body.initData !== "string") return Response.json({ ok: false, reason: "initData must be a string" }, { status: 400 });
  const result = await verifyInitData(body.initData, env.TELEGRAM_BOT_TOKEN);
  const user = result.user as { id?: unknown } | null | undefined;
  if (!result.ok || !user || typeof user.id !== "number") return Response.json({ ok: false, reason: result.reason ?? "user missing" }, { status: 401 });
  return { id: user.id };
}

// Returns a Response for /webapp routes, or null so the caller handles the request.
export async function handleWebApp(request: Request, env: WebAppEnv): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  if (request.method === "GET" && path === "/webapp") {
    return new Response(PAGE, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
  }
  if (request.method !== "POST" || !["/webapp/verify", "/webapp/location", "/webapp/location/save"].includes(path)) return null;

  let body: Record<string, unknown>;
  try {
    body = await readJson(request);
  } catch {
    return Response.json({ ok: false, reason: "invalid request" }, { status: 400 });
  }
  if (path === "/webapp/verify") {
    if (!env.TELEGRAM_BOT_TOKEN) return Response.json({ ok: false, reason: "TELEGRAM_BOT_TOKEN secret is not set on the worker" });
    if (typeof body.initData !== "string") return Response.json({ ok: false, reason: "initData must be a string" }, { status: 400 });
    const result = await verifyInitData(body.initData, env.TELEGRAM_BOT_TOKEN);
    return Response.json(result, { status: result.ok ? 200 : 401 });
  }

  const user = await authenticate(body, env);
  if (user instanceof Response) return user;
  if (path === "/webapp/location") {
    return Response.json({ ok: true, city: await getLocation(env.DATA_DB, user.id, null) });
  }
  let city: string;
  try {
    city = normalizeCity(body.city);
  } catch (error) {
    return Response.json({ ok: false, reason: error instanceof Error ? error.message : "invalid city" }, { status: 400 });
  }
  await setLocation(env.DATA_DB, user.id, HOME_CHAT_ID, city);
  return Response.json({ ok: true, city });
}
