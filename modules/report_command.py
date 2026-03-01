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
    }


def _html(text: str) -> str:
    """Escape HTML special characters in dynamic text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_report(data: Dict[str, Any], days: int) -> str:
    """Format analytics data into an HTML report string."""
    now = data["now"]
    start = data["period_start"]
    start_str = start.strftime("%d.%m")
    end_str = now.strftime("%d.%m")

    cur_total = data["current_total"]
    cur_cmds = data["current_commands"]
    prev_total = data["prev_total"]
    prev_cmds = data["prev_commands"]
    active = data["active_chats"]
    active_count = len(active)
    prev_active = data["prev_active_count"]
    new_chats = data["new_chats"]
    total_chats = data["total_chats"]
    inactive = data["inactive_count"]

    lines = []
    lines.append(f"📊 <b>Weekly Intelligence Report ({start_str}–{end_str})</b>")
    lines.append("")
    lines.append(f"📨 <b>Messages:</b> {cur_total:,} ({_pct_change(cur_total, prev_total)})")
    lines.append(f"⌨️ <b>Commands:</b> {cur_cmds} ({_pct_change(cur_cmds, prev_cmds)})")
    lines.append(f"💬 <b>Active chats:</b> {active_count} ({_pct_change(active_count, prev_active)})")
    lines.append(f"🆕 <b>New chats:</b> {new_chats}")

    # Most used feature
    if data["top_commands"]:
        top_cmd = data["top_commands"][0]
        cmd_name = top_cmd["command_name"].split("@")[0]
        lines.append(f"🔥 <b>Top feature:</b> /{_html(cmd_name)} ({top_cmd['cnt']} uses)")

    lines.append(f"😴 <b>Inactive chats:</b> {inactive} (no activity in 14+ days)")

    # Peak hour
    if data["hourly"]:
        peak = max(data["hourly"], key=lambda r: r["cnt"])
        lines.append(f"⏱ <b>Peak time:</b> {peak['hour']:02d}:00 ({peak['cnt']} msgs)")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # Top commands
    if data["top_commands"]:
        lines.append("🏆 <b>Top commands:</b>")
        for i, cmd in enumerate(data["top_commands"][:5], 1):
            name = cmd["command_name"].split("@")[0]
            lines.append(f" {i}. /{_html(name)} — {cmd['cnt']}")
        lines.append("")

    # Top users
    if data["top_users"]:
        lines.append("👥 <b>Top users:</b>")
        for i, user in enumerate(data["top_users"][:5], 1):
            name = f"@{user['username']}" if user["username"] else _html(user["first_name"])
            lines.append(f" {i}. {name} — {user['cnt']:,}")
        lines.append("")

    # Daily breakdown
    daily = data["daily"]
    if daily:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        lines.append("📅 <b>Daily breakdown:</b>")
        daily_lines = []
        peak_day = max(daily, key=lambda r: r["total"])
        for row in daily:
            d = row["day"]
            dow = day_names[d.weekday()]
            marker = " ←peak" if row["day"] == peak_day["day"] else ""
            daily_lines.append(f" {dow} {d.strftime('%d.%m')}: {row['total']:,} ({row['commands']} cmd){marker}")

        # Truncate if too many days would blow the message limit
        if len(daily_lines) > 14:
            shown = daily_lines[-7:]
            lines.append(f" <i>...and {len(daily_lines) - 7} earlier days</i>")
            lines.extend(shown)
        else:
            lines.extend(daily_lines)
        lines.append("")

    # Retention
    retention = round(active_count / total_chats * 100) if total_chats > 0 else 0
    lines.append(f"🔄 <b>Retention:</b> {retention}% ({active_count}/{total_chats} chats)")

    # Chat activity breakdown
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

    # Key takeaway
    lines.append("")
    if daily and len(daily) >= 2:
        peak_d = max(daily, key=lambda r: r["total"])
        low_d = min(daily, key=lambda r: r["total"])
        day_names_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        peak_name = day_names_full[peak_d["day"].weekday()]
        low_name = day_names_full[low_d["day"].weekday()]
        cmd_trend = _pct_change(cur_cmds, prev_cmds)
        lines.append(
            f"💡 Peak day: {peak_name} ({peak_d['total']:,} msgs), "
            f"quietest: {low_name} ({low_d['total']:,}). "
            f"Commands {cmd_trend} vs previous period."
        )

    report = "\n".join(lines)

    # Safety truncation
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
