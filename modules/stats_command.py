"""
Per-chat activity statistics command.

Provides /stats [days|all] for on-demand chat-specific analytics
with engagement insights, weekday activity charts, and trend analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
from telegram import Update
from telegram.ext import ContextTypes

from modules.const import KYIV_TZ
from modules.database import Database
from modules.report_command import _pct_change, _peak_time_range

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
BLOCKS = " ▏▎▍▌▋▊▉█"


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _empty_stats_data(now: datetime, period_start: datetime, is_all_time: bool) -> Dict[str, Any]:
    return {
        "now": now,
        "period_start": period_start,
        "is_all_time": is_all_time,
        "days": (now - period_start).days or 1,
        "current_total": 0,
        "current_commands": 0,
        "prev_total": 0,
        "prev_commands": 0,
        "active_users": [],
        "new_users_count": 0,
        "inactive_users_count": 0,
        "top_commands": [],
        "hourly": [],
        "weekday": [],
        "avg_response_seconds": None,
        "prev_avg_response_seconds": None,
    }


async def fetch_stats_data(chat_id: int, days: Optional[int] = None) -> Dict[str, Any]:
    """Fetch all chat-specific analytics data for the given period."""
    now = datetime.now(KYIV_TZ)
    now_utc = now.astimezone(pytz.UTC)
    is_all_time = days is None

    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        if is_all_time:
            earliest = await conn.fetchval(
                "SELECT MIN(timestamp) FROM messages WHERE chat_id = $1", chat_id
            )
            if earliest is None:
                return _empty_stats_data(now, now, is_all_time=True)
            period_start_utc = earliest
            period_start = earliest.astimezone(KYIV_TZ)
            prev_start_utc = None
            actual_days = (now_utc - period_start_utc).days or 1
        else:
            period_start = now - timedelta(days=days)
            period_start_utc = period_start.astimezone(pytz.UTC)
            prev_start_utc = (period_start - timedelta(days=days)).astimezone(pytz.UTC)
            actual_days = days

        # 1. Message/command counts
        if prev_start_utc is not None:
            counts = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_total,
                    COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2 AND is_command = true) AS current_commands,
                    COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_total,
                    COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1 AND is_command = true) AS prev_commands
                FROM messages
                WHERE chat_id = $4 AND timestamp >= $3 AND timestamp < $2
            """, period_start_utc, now_utc, prev_start_utc, chat_id)
        else:
            row = await conn.fetchrow("""
                SELECT COUNT(*) AS current_total,
                       COUNT(*) FILTER (WHERE is_command = true) AS current_commands
                FROM messages
                WHERE chat_id = $1 AND timestamp >= $2 AND timestamp < $3
            """, chat_id, period_start_utc, now_utc)
            counts = {
                "current_total": row["current_total"],
                "current_commands": row["current_commands"],
                "prev_total": 0,
                "prev_commands": 0,
            }

        # 2. Active users (non-bot)
        active_users = await conn.fetch("""
            SELECT DISTINCT m.user_id, u.username, u.first_name
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1 AND m.timestamp >= $2 AND m.timestamp < $3
              AND u.is_bot = false
        """, chat_id, period_start_utc, now_utc)

        # 3. New users (first message in this chat falls in current period)
        new_users = await conn.fetchval("""
            SELECT COUNT(*) FROM (
                SELECT user_id FROM messages
                WHERE chat_id = $1
                GROUP BY user_id
                HAVING MIN(timestamp) >= $2 AND MIN(timestamp) < $3
            ) sub
        """, chat_id, period_start_utc, now_utc)

        # 4. Inactive users (active in previous period, absent in current)
        inactive_users = 0
        if prev_start_utc is not None:
            inactive_users = await conn.fetchval("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT user_id FROM messages
                    WHERE chat_id = $1 AND timestamp >= $2 AND timestamp < $3
                    EXCEPT
                    SELECT DISTINCT user_id FROM messages
                    WHERE chat_id = $1 AND timestamp >= $3 AND timestamp < $4
                ) sub
            """, chat_id, prev_start_utc, period_start_utc, now_utc)

        # 5. Top commands
        top_commands = await conn.fetch("""
            SELECT command_name, COUNT(*) AS cnt
            FROM messages
            WHERE chat_id = $1 AND timestamp >= $2 AND timestamp < $3
              AND is_command = true AND command_name IS NOT NULL
            GROUP BY command_name
            ORDER BY cnt DESC LIMIT 5
        """, chat_id, period_start_utc, now_utc)

        # 6. Hourly distribution (Kyiv time)
        hourly = await conn.fetch("""
            SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Kyiv')::int AS hour,
                   COUNT(*) AS cnt
            FROM messages
            WHERE chat_id = $1 AND timestamp >= $2 AND timestamp < $3
            GROUP BY hour ORDER BY hour
        """, chat_id, period_start_utc, now_utc)

        # 7. Weekday distribution (Kyiv time, DOW: 0=Sun..6=Sat)
        weekday = await conn.fetch("""
            SELECT EXTRACT(DOW FROM timestamp AT TIME ZONE 'Europe/Kyiv')::int AS dow,
                   COUNT(*) AS cnt
            FROM messages
            WHERE chat_id = $1 AND timestamp >= $2 AND timestamp < $3
            GROUP BY dow ORDER BY dow
        """, chat_id, period_start_utc, now_utc)

        # 8. Response time (median of reply deltas, human replies only)
        avg_response_seconds = await _calc_response_time(
            conn, chat_id, period_start_utc, now_utc
        )

        # 9. Previous period response time
        prev_avg_response_seconds = None
        if prev_start_utc is not None:
            prev_avg_response_seconds = await _calc_response_time(
                conn, chat_id, prev_start_utc, period_start_utc
            )

    return {
        "now": now,
        "period_start": period_start,
        "is_all_time": is_all_time,
        "days": actual_days,
        "current_total": counts["current_total"],
        "current_commands": counts["current_commands"],
        "prev_total": counts["prev_total"],
        "prev_commands": counts["prev_commands"],
        "active_users": active_users,
        "new_users_count": new_users or 0,
        "inactive_users_count": inactive_users or 0,
        "top_commands": top_commands,
        "hourly": hourly,
        "weekday": weekday,
        "avg_response_seconds": avg_response_seconds,
        "prev_avg_response_seconds": prev_avg_response_seconds,
    }


async def _calc_response_time(conn, chat_id: int, start_utc, end_utc) -> Optional[float]:
    """Calculate median response time (seconds) for human replies in a period."""
    rows = await conn.fetch("""
        SELECT EXTRACT(EPOCH FROM (reply.timestamp - original.timestamp)) AS delta
        FROM messages reply
        JOIN messages original
            ON original.chat_id = reply.chat_id
            AND original.message_id = reply.replied_to_message_id
        WHERE reply.chat_id = $1
            AND reply.timestamp >= $2 AND reply.timestamp < $3
            AND reply.replied_to_message_id IS NOT NULL
            AND reply.is_gpt_reply = false
            AND EXTRACT(EPOCH FROM (reply.timestamp - original.timestamp)) > 0
            AND EXTRACT(EPOCH FROM (reply.timestamp - original.timestamp)) < 86400
    """, chat_id, start_utc, end_utc)
    if not rows:
        return None
    deltas = sorted(r["delta"] for r in rows)
    return deltas[len(deltas) // 2]


def _build_weekday_chart(weekday_data: List) -> str:
    """Build ASCII weekday activity chart with unicode blocks."""
    dow_map = {r["dow"]: r["cnt"] for r in weekday_data}
    max_cnt = max(dow_map.values()) if dow_map else 0
    if max_cnt == 0:
        return "  No activity data"

    peak_dow = max(dow_map, key=dow_map.get)
    max_bar_width = 16
    lines = []
    for dow in range(7):
        cnt = dow_map.get(dow, 0)
        name = DAY_NAMES[dow]
        if max_cnt > 0 and cnt > 0:
            ratio = cnt / max_cnt
            full_blocks = int(ratio * max_bar_width)
            remainder = (ratio * max_bar_width) - full_blocks
            partial_idx = int(remainder * 8)
            bar = BLOCKS[-1] * full_blocks
            if partial_idx > 0 and full_blocks < max_bar_width:
                bar += BLOCKS[partial_idx]
        else:
            bar = ""
        marker = " \u2190 peak" if dow == peak_dow else ""
        lines.append(f"{name} {bar} {cnt:,}{marker}")
    return "\n".join(lines)


def _format_response_time(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def _build_engagement_trend(data: Dict[str, Any]) -> str:
    active_count = len(data["active_users"])
    new_count = data["new_users_count"]
    cur = data["current_total"]
    prev = data["prev_total"]

    if data["is_all_time"] or prev == 0:
        if active_count > 0:
            return f"{active_count} users contributed to this chat's history."
        return "No significant activity recorded."

    change_pct = round((cur - prev) / prev * 100) if prev > 0 else 0
    if change_pct > 20:
        trend = "Activity surging"
    elif change_pct > 5:
        trend = "Activity growing"
    elif change_pct > -5:
        trend = "Activity stable"
    elif change_pct > -20:
        trend = "Activity declining"
    else:
        trend = "Activity dropped significantly"

    extras = []
    if new_count > 0:
        extras.append(f"{new_count} new participant{'s' if new_count != 1 else ''}")
    if data["inactive_users_count"] > 0:
        extras.append(f"{data['inactive_users_count']} went quiet")
    if extras:
        trend += f" ({', '.join(extras)})"
    return trend + "."


def _build_ai_analysis(data: Dict[str, Any]) -> str:
    sentences: List[str] = []
    active_count = len(data["active_users"])
    cur_total = data["current_total"]
    prev_total = data["prev_total"]
    days = data["days"]

    # Volume characterization
    msgs_per_day = round(cur_total / days, 1) if days > 0 else 0
    if msgs_per_day > 50:
        sentences.append(f"Highly active chat averaging {msgs_per_day} messages/day.")
    elif msgs_per_day > 10:
        sentences.append(f"Moderate activity with ~{msgs_per_day} messages/day.")
    elif msgs_per_day > 0:
        sentences.append(f"Light activity at ~{msgs_per_day} messages/day.")
    else:
        sentences.append("No messages recorded in this period.")
        return sentences[0]

    # Period-over-period comparison
    if not data["is_all_time"] and prev_total > 0:
        change = round((cur_total - prev_total) / prev_total * 100)
        direction = "up" if change > 0 else "down"
        if abs(change) >= 5:
            driver = ""
            if data["top_commands"]:
                cmd = data["top_commands"][0]["command_name"].split("@")[0]
                driver = f", driven by /{cmd} usage"
            sentences.append(f"Volume is {direction} {abs(change)}% vs the previous period{driver}.")

    # Weekday pattern
    weekday = data.get("weekday", [])
    if weekday:
        dow_map = {r["dow"]: r["cnt"] for r in weekday}
        if dow_map:
            peak_dow = max(dow_map, key=dow_map.get)
            low_dow = min(dow_map, key=dow_map.get)
            peak_cnt = dow_map[peak_dow]
            low_cnt = dow_map[low_dow]
            if low_cnt > 0 and peak_cnt > low_cnt * 1.5:
                sentences.append(
                    f"{DAY_NAMES[peak_dow]} is the peak day ({peak_cnt:,} msgs), "
                    f"while {DAY_NAMES[low_dow]} is the quietest ({low_cnt:,})."
                )

    # Response time insight
    avg_rt = data.get("avg_response_seconds")
    if avg_rt is not None:
        if avg_rt < 60:
            sentences.append("Very fast replies indicate real-time engagement.")
        elif avg_rt < 300:
            sentences.append("Quick response times suggest active monitoring.")
        elif avg_rt < 3600:
            sentences.append("Response pace is typical for asynchronous chats.")

    # Peak time
    hourly = data.get("hourly", [])
    if hourly:
        peak_range = _peak_time_range(hourly)
        sentences.append(f"The {peak_range} Kyiv window is the dominant activity zone.")

    return " ".join(sentences[:4])


def format_stats(data: Dict[str, Any]) -> str:
    """Format chat stats into HTML output."""
    days = data["days"]
    is_all_time = data["is_all_time"]
    cur_total = data["current_total"]
    prev_total = data["prev_total"]
    active_count = len(data["active_users"])
    new_count = data["new_users_count"]
    inactive_count = data["inactive_users_count"]

    header = "📊 <b>Chat Statistics (All Time)</b>" if is_all_time else f"📊 <b>Chat Statistics (Last {days} Days)</b>"
    lines = [header, ""]

    # Messages
    if is_all_time:
        lines.append(f"💬 <b>Messages sent:</b> {cur_total:,}")
    else:
        lines.append(f"💬 <b>Messages sent:</b> {cur_total:,} ({_pct_change(cur_total, prev_total)})")

    # Active users
    user_extras = []
    if new_count > 0:
        user_extras.append(f"{new_count} new")
    if inactive_count > 0:
        user_extras.append(f"{inactive_count} went inactive")
    user_note = f" ({', '.join(user_extras)})" if user_extras else ""
    lines.append(f"🧍‍♂️ <b>Active users:</b> {active_count}{user_note}")

    # Most used command
    if data["top_commands"]:
        cmd = data["top_commands"][0]
        cmd_name = cmd["command_name"].split("@")[0]
        lines.append(f"🔥 <b>Most used command:</b> /{_html(cmd_name)} ({cmd['cnt']}x)")

    # Peak activity time
    peak = _peak_time_range(data["hourly"])
    lines.append(f"⏱ <b>Peak activity time:</b> {peak} (Kyiv)")

    # Response time
    avg_rt = data.get("avg_response_seconds")
    prev_rt = data.get("prev_avg_response_seconds")
    rt_str = _format_response_time(avg_rt)
    if not is_all_time and avg_rt is not None and prev_rt is not None and prev_rt > 0:
        rt_change = round((avg_rt - prev_rt) / prev_rt * 100)
        if rt_change < -5:
            rt_str += " (↓faster)"
        elif rt_change > 5:
            rt_str += " (↑slower)"
        else:
            rt_str += " (stable)"
    lines.append(f"🕒 <b>Avg response time:</b> {rt_str}")

    # Engagement trend
    lines.append(f"💡 <b>Engagement:</b> {_build_engagement_trend(data)}")

    # Weekday activity chart
    lines.append("")
    lines.append("📊 <b>Daily Activity Pattern:</b>")
    lines.append(f"<pre>{_build_weekday_chart(data['weekday'])}</pre>")

    # AI Analysis
    lines.append(f"🧠 <b>Key takeaway:</b> {_build_ai_analysis(data)}")

    report = "\n".join(lines)
    if len(report) > MAX_MESSAGE_LENGTH:
        report = report[:MAX_MESSAGE_LENGTH - 20] + "\n...(truncated)"
    return report


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats [days|all] command. Available to any user in any chat."""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    args = context.args if hasattr(context, "args") else []
    days: Optional[int] = 7

    if args:
        arg = args[0].strip().lower()
        if arg == "all":
            days = None
        else:
            try:
                days = int(arg)
                if days < 1 or days > 3650:
                    await update.message.reply_text("❌ Number of days must be between 1 and 3650.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Usage: /stats, /stats 30, or /stats all")
                return

    try:
        progress_msg = await update.message.reply_text("⏳ Generating chat statistics...")
        data = await fetch_stats_data(chat_id, days)
        text = format_stats(data)
        await progress_msg.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in /stats command: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ Error generating statistics. Try again later.")
        except Exception:
            pass
