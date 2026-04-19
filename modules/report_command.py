"""
Usage analytics report command and scheduled weekly report.

Provides /report [days] for on-demand analytics and a weekly_report_callback
for scheduled delivery every Saturday at 23:00 Kyiv time.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
from telegram import Update
from telegram.ext import ContextTypes

from modules.const import KYIV_TZ
from modules.database import Database

logger = logging.getLogger(__name__)

WEEKLY_REPORT_CHAT_ID = int(os.getenv("REPORT_CHAT_ID", "0"))
WEEKLY_REPORT_THREAD_ID = int(os.getenv("REPORT_THREAD_ID", "0"))
REPORT_ALLOWED_USER_ID = int(os.getenv("REPORT_ALLOWED_USER_ID", "0"))
MAX_MESSAGE_LENGTH = 4096


def _pct_change(current: int, previous: int) -> str:
    if previous == 0:
        return "new" if current > 0 else "0%"
    change = round((current - previous) / previous * 100)
    if change > 0:
        return f"+{change}%"
    return f"{change}%"


async def fetch_report_data(days: int) -> Dict[str, Any]:
    """Fetch all analytics data for the given period and its comparison period."""
    now = datetime.now(KYIV_TZ)
    period_start = now - timedelta(days=days)
    prev_start = period_start - timedelta(days=days)

    now_utc = now.astimezone(pytz.UTC)
    period_start_utc = period_start.astimezone(pytz.UTC)
    prev_start_utc = prev_start.astimezone(pytz.UTC)

    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # 1. Message/command counts for both periods
        counts = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_total,
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2 AND is_command = true) AS current_commands,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_total,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1 AND is_command = true) AS prev_commands
            FROM messages
            WHERE timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, prev_start_utc)

        # 2. Active chats with titles and message counts (current period)
        active_chats = await conn.fetch("""
            SELECT m.chat_id, c.title, COUNT(*) AS cnt
            FROM messages m
            LEFT JOIN chats c ON m.chat_id = c.chat_id
            WHERE m.timestamp >= $1 AND m.timestamp < $2
            GROUP BY m.chat_id, c.title
            ORDER BY cnt DESC
        """, period_start_utc, now_utc)

        # 3. Previous period active chat count
        prev_active = await conn.fetchval("""
            SELECT COUNT(DISTINCT chat_id) FROM messages
            WHERE timestamp >= $1 AND timestamp < $2
        """, prev_start_utc, period_start_utc)

        # 4. New chats (first-ever message falls in current period)
        new_chats = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT chat_id FROM messages
                GROUP BY chat_id
                HAVING MIN(timestamp) >= $1 AND MIN(timestamp) < $2
            ) sub
        """, period_start_utc, now_utc)

        # 5. Top commands
        top_commands = await conn.fetch("""
            SELECT command_name, COUNT(*) AS cnt
            FROM messages
            WHERE timestamp >= $1 AND timestamp < $2
              AND is_command = true AND command_name IS NOT NULL
            GROUP BY command_name
            ORDER BY cnt DESC LIMIT 10
        """, period_start_utc, now_utc)

        # 6. Top users (excluding bots)
        top_users = await conn.fetch("""
            SELECT u.username, u.first_name, COUNT(*) AS cnt
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.timestamp >= $1 AND m.timestamp < $2 AND u.is_bot = false
            GROUP BY u.user_id, u.username, u.first_name
            ORDER BY cnt DESC LIMIT 5
        """, period_start_utc, now_utc)

        # 7. Hourly distribution (Kyiv time)
        hourly = await conn.fetch("""
            SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Kyiv')::int AS hour,
                   COUNT(*) AS cnt
            FROM messages
            WHERE timestamp >= $1 AND timestamp < $2
            GROUP BY hour ORDER BY hour
        """, period_start_utc, now_utc)

        # 8. Daily breakdown
        daily = await conn.fetch("""
            SELECT
                (timestamp AT TIME ZONE 'Europe/Kyiv')::date AS day,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_command = true) AS commands
            FROM messages
            WHERE timestamp >= $1 AND timestamp < $2
            GROUP BY day ORDER BY day
        """, period_start_utc, now_utc)

        # 9. Inactive chats (no activity in >14 days)
        inactive_count = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT chat_id FROM messages
                GROUP BY chat_id
                HAVING MAX(timestamp) < $1
            ) sub
        """, (now - timedelta(days=14)).astimezone(pytz.UTC))

        # 10. Total chats ever
        total_chats = await conn.fetchval("SELECT COUNT(DISTINCT chat_id) FROM messages")

        # 11. URL modification and video download counts
        url_mods = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'url_modification'
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, prev_start_utc)

        vid_downloads = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'video_download'
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, prev_start_utc)

        # 12. Media sent (photos + videos)
        media = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM messages
            WHERE timestamp >= $3 AND timestamp < $2
              AND (raw_telegram_message ? 'photo' OR raw_telegram_message ? 'video'
                   OR raw_telegram_message ? 'video_note' OR raw_telegram_message ? 'animation')
        """, period_start_utc, now_utc, prev_start_utc)

        # 13. User reactions added
        reactions = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'reaction'
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, prev_start_utc)

        # 14. Stickers sent
        stickers = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM messages
            WHERE timestamp >= $3 AND timestamp < $2
              AND raw_telegram_message ? 'sticker'
        """, period_start_utc, now_utc, prev_start_utc)

        # 15. Songs sent
        songs = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'song_sent'
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, prev_start_utc)

    return {
        "now": now,
        "period_start": period_start,
        "current_total": counts["current_total"],
        "current_commands": counts["current_commands"],
        "prev_total": counts["prev_total"],
        "prev_commands": counts["prev_commands"],
        "active_chats": active_chats,
        "prev_active_count": prev_active or 0,
        "new_chats": new_chats or 0,
        "top_commands": top_commands,
        "top_users": top_users,
        "hourly": hourly,
        "daily": daily,
        "inactive_count": inactive_count or 0,
        "total_chats": total_chats or 0,
        "url_mods_current": url_mods["current_count"] or 0,
        "url_mods_prev": url_mods["prev_count"] or 0,
        "vid_downloads_current": vid_downloads["current_count"] or 0,
        "vid_downloads_prev": vid_downloads["prev_count"] or 0,
        "media_current": media["current_count"] or 0,
        "media_prev": media["prev_count"] or 0,
        "reactions_current": reactions["current_count"] or 0,
        "reactions_prev": reactions["prev_count"] or 0,
        "stickers_current": stickers["current_count"] or 0,
        "stickers_prev": stickers["prev_count"] or 0,
        "songs_current": songs["current_count"] or 0,
        "songs_prev": songs["prev_count"] or 0,
    }


def _html(text: str) -> str:
    """Escape HTML special characters in dynamic text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _peak_time_range(hourly: List) -> str:
    """Find the best 2-hour window from hourly data."""
    if not hourly:
        return "N/A"
    hour_map = {r["hour"]: r["cnt"] for r in hourly}
    best_start, best_total = 0, 0
    for h in range(24):
        total = hour_map.get(h, 0) + hour_map.get((h + 1) % 24, 0)
        if total > best_total:
            best_start, best_total = h, total
    end = (best_start + 2) % 24
    return f"{best_start:02d}:00–{end:02d}:00"


def _build_insights(data: Dict[str, Any], days: int) -> str:
    """Build the single-line insights paragraph."""
    parts: List[str] = []

    active_count = len(data["active_chats"])
    total_chats = data["total_chats"]
    retention = round(active_count / total_chats * 100) if total_chats > 0 else 0
    parts.append(f"Retention {retention}%")

    # Power users
    if data["top_users"]:
        names = []
        for u in data["top_users"][:3]:
            names.append(f"@{u['username']}" if u["username"] else _html(u["first_name"]))
        parts.append(f"power users: {', '.join(names)}")

    # Anomaly detection: find biggest daily spike/drop
    daily = data["daily"]
    day_names_full = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if daily and len(daily) >= 2:
        avg = sum(r["total"] for r in daily) / len(daily)
        if avg > 0:
            best = max(daily, key=lambda r: r["total"])
            worst = min(daily, key=lambda r: r["total"])
            best_pct = round((best["total"] - avg) / avg * 100)
            worst_pct = round((worst["total"] - avg) / avg * 100)
            best_dow = day_names_full[best["day"].weekday()]
            worst_dow = day_names_full[worst["day"].weekday()]
            if best_pct >= 20:
                top_cmd_name = ""
                if data["top_commands"]:
                    top_cmd_name = f" driven by /{data['top_commands'][0]['command_name'].split('@')[0]} usage"
                parts.append(f"big {best_dow} spike (+{best_pct}%){top_cmd_name}")
            elif worst_pct <= -20:
                parts.append(f"notable {worst_dow} dip ({worst_pct}%)")

    # Trend sentence
    cur_total = data["current_total"]
    prev_total = data["prev_total"]
    if prev_total > 0:
        change = round((cur_total - prev_total) / prev_total * 100)
        if change > 5:
            parts.append("activity trending up overall")
        elif change < -5:
            parts.append("activity cooled vs previous period")
        else:
            parts.append("activity stable vs previous period")

    return ". ".join(parts) + "."


def format_report(data: Dict[str, Any], days: int) -> str:
    """Format analytics data into a concise, insight-driven HTML report."""
    start_str = data["period_start"].strftime("%b %d")
    end_str = data["now"].strftime("%b %d")

    cur_total = data["current_total"]
    prev_total = data["prev_total"]
    cur_cmds = data["current_commands"]
    prev_cmds = data["prev_commands"]
    active = data["active_chats"]
    active_count = len(active)
    new_chats = data["new_chats"]
    inactive = data["inactive_count"]

    lines = [
        f"📊 <b>Weekly Intelligence Report ({start_str}–{end_str})</b>",
        "",
        f"📨 <b>Messages:</b> {cur_total:,} ({_pct_change(cur_total, prev_total)})",
        f"📈 <b>Commands:</b> {cur_cmds} ({_pct_change(cur_cmds, prev_cmds)})",
        f"🔗 <b>URL modifications:</b> {data['url_mods_current']:,} ({_pct_change(data['url_mods_current'], data['url_mods_prev'])})",
        f"📥 <b>Video downloads:</b> {data['vid_downloads_current']:,} ({_pct_change(data['vid_downloads_current'], data['vid_downloads_prev'])})",
        f"🖼 <b>Media sent:</b> {data['media_current']:,} ({_pct_change(data['media_current'], data['media_prev'])})",
        f"👍 <b>Reactions:</b> {data['reactions_current']:,} ({_pct_change(data['reactions_current'], data['reactions_prev'])})",
        f"🎭 <b>Stickers sent:</b> {data['stickers_current']:,} ({_pct_change(data['stickers_current'], data['stickers_prev'])})",
        f"🎵 <b>Songs sent:</b> {data['songs_current']:,} ({_pct_change(data['songs_current'], data['songs_prev'])})",
        f"👥 <b>Active chats:</b> {active_count} ({new_chats} new)",
    ]

    if data["top_commands"]:
        cmd_name = data["top_commands"][0]["command_name"].split("@")[0]
        lines.append(f"🔥 <b>Most used feature:</b> /{_html(cmd_name)}")

    lines.append(f"😴 <b>Dead chats:</b> {inactive} (no activity in 14 days)")
    lines.append(f"⏱ <b>Peak time:</b> {_peak_time_range(data['hourly'])}")

    # Top commands
    if data["top_commands"]:
        lines.append("")
        lines.append("🏆 <b>Top commands:</b>")
        for i, cmd in enumerate(data["top_commands"][:5], 1):
            name = cmd["command_name"].split("@")[0]
            lines.append(f" {i}. /{_html(name)} — {cmd['cnt']}")

    # Top users
    if data["top_users"]:
        lines.append("")
        lines.append("👤 <b>Top users:</b>")
        for i, user in enumerate(data["top_users"][:5], 1):
            name = f"@{user['username']}" if user["username"] else _html(user["first_name"])
            lines.append(f" {i}. {name} — {user['cnt']:,}")

    # Chat activity
    if active:
        total_msgs = sum(c["cnt"] for c in active)
        lines.append("")
        lines.append("📡 <b>Chat activity:</b>")
        for chat in active[:4]:
            title = _html(chat["title"] or f"Private {chat['chat_id']}")
            pct = round(chat["cnt"] / total_msgs * 100) if total_msgs > 0 else 0
            lines.append(f" • {title} — {chat['cnt']:,} ({pct}%)")
        remaining = len(active) - 4
        if remaining > 0:
            remaining_msgs = sum(c["cnt"] for c in active[4:])
            pct = round(remaining_msgs / total_msgs * 100) if total_msgs > 0 else 0
            lines.append(f" • {remaining} other chats — {remaining_msgs:,} ({pct}%)")

    # Insights
    lines.append("")
    lines.append(f"🔍 <b>Insights:</b> {_build_insights(data, days)}")

    report = "\n".join(lines)

    if len(report) > MAX_MESSAGE_LENGTH:
        report = report[:MAX_MESSAGE_LENGTH - 20] + "\n...(truncated)"

    return report


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report [days] command. Restricted to owner in the report chat."""
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None
    if chat_id != WEEKLY_REPORT_CHAT_ID or user_id != REPORT_ALLOWED_USER_ID:
        return

    try:
        args = context.args if hasattr(context, "args") else []
        days = int(args[0]) if args else 7
        if days < 1 or days > 365:
            await update.message.reply_text("❌ Number of days must be between 1 and 365.")
            return
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Usage: /report or /report 30")
        return

    try:
        progress_msg = await update.message.reply_text("⏳ Generating report...")
        data = await fetch_report_data(days)
        text = format_report(data, days)
        await progress_msg.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in /report command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Error generating report. Try again later.")
        except Exception:
            pass


async def weekly_report_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled callback: send weekly report every Saturday at 23:00 Kyiv time."""
    try:
        data = await fetch_report_data(7)
        text = format_report(data, 7)
        await context.bot.send_message(
            chat_id=WEEKLY_REPORT_CHAT_ID,
            text=text,
            parse_mode="HTML",
            message_thread_id=WEEKLY_REPORT_THREAD_ID,
        )
        logger.info("Weekly report sent successfully")
    except Exception as e:
        logger.error(f"Error sending weekly report: {e}", exc_info=True)
