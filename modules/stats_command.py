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
from modules.logger import general_logger, error_logger
from modules.chat_analysis import get_user_chat_stats_with_fallback
from config_v2.compat import get_shared_config_manager

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
        "url_mods_current": 0,
        "url_mods_prev": 0,
        "vid_downloads_current": 0,
        "vid_downloads_prev": 0,
        "media_current": 0,
        "media_prev": 0,
        "reactions_current": 0,
        "reactions_prev": 0,
        "stickers_current": 0,
        "stickers_prev": 0,
        "gifs_current": 0,
        "gifs_prev": 0,
        "songs_current": 0,
        "songs_prev": 0,
        "top_users": [],
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

        # 10. URL modification and video download counts
        _prev_bound = prev_start_utc if prev_start_utc is not None else period_start_utc
        url_mods = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'url_modification' AND chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        vid_downloads = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'video_download' AND chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 11. Media sent (photos + videos in messages)
        media = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM messages
            WHERE chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
              AND (raw_telegram_message ? 'photo' OR raw_telegram_message ? 'video'
                   OR raw_telegram_message ? 'video_note')
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 12. User reactions added
        reactions = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'reaction' AND chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 13. Stickers sent
        stickers = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM messages
            WHERE chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
              AND raw_telegram_message ? 'sticker'
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 14. GIFs sent
        gifs = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM messages
            WHERE chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
              AND raw_telegram_message ? 'animation'
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 15. Songs sent
        songs = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE timestamp >= $1 AND timestamp < $2) AS current_count,
                COUNT(*) FILTER (WHERE timestamp >= $3 AND timestamp < $1) AS prev_count
            FROM bot_events
            WHERE event_type = 'song_sent' AND chat_id = $4
              AND timestamp >= $3 AND timestamp < $2
        """, period_start_utc, now_utc, _prev_bound, chat_id)

        # 15. Top users leaderboard
        top_users = await conn.fetch("""
            SELECT m.user_id, u.username, u.first_name, COUNT(*) AS cnt
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.chat_id = $1 AND m.timestamp >= $2 AND m.timestamp < $3
              AND u.is_bot = false
            GROUP BY m.user_id, u.username, u.first_name
            ORDER BY cnt DESC LIMIT 5
        """, chat_id, period_start_utc, now_utc)

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
        "url_mods_current": url_mods["current_count"] or 0,
        "url_mods_prev": url_mods["prev_count"] or 0 if prev_start_utc is not None else 0,
        "vid_downloads_current": vid_downloads["current_count"] or 0,
        "vid_downloads_prev": vid_downloads["prev_count"] or 0 if prev_start_utc is not None else 0,
        "media_current": media["current_count"] or 0,
        "media_prev": media["prev_count"] or 0 if prev_start_utc is not None else 0,
        "reactions_current": reactions["current_count"] or 0,
        "reactions_prev": reactions["prev_count"] or 0 if prev_start_utc is not None else 0,
        "stickers_current": stickers["current_count"] or 0,
        "stickers_prev": stickers["prev_count"] or 0 if prev_start_utc is not None else 0,
        "gifs_current": gifs["current_count"] or 0,
        "gifs_prev": gifs["prev_count"] or 0 if prev_start_utc is not None else 0,
        "songs_current": songs["current_count"] or 0,
        "songs_prev": songs["prev_count"] or 0 if prev_start_utc is not None else 0,
        "top_users": top_users,
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

    # URL modifications
    url_mods_cur = data["url_mods_current"]
    url_mods_prev = data["url_mods_prev"]
    if url_mods_cur > 0 or not is_all_time:
        mods_str = f"{url_mods_cur:,}"
        if not is_all_time:
            mods_str += f" ({_pct_change(url_mods_cur, url_mods_prev)})"
        lines.append(f"🔗 <b>URL modifications:</b> {mods_str}")

    # Video downloads
    vid_dl_cur = data["vid_downloads_current"]
    vid_dl_prev = data["vid_downloads_prev"]
    if vid_dl_cur > 0 or not is_all_time:
        dl_str = f"{vid_dl_cur:,}"
        if not is_all_time:
            dl_str += f" ({_pct_change(vid_dl_cur, vid_dl_prev)})"
        lines.append(f"📥 <b>Video downloads:</b> {dl_str}")

    # Media sent
    media_cur = data["media_current"]
    media_prev = data["media_prev"]
    if media_cur > 0 or not is_all_time:
        media_str = f"{media_cur:,}"
        if not is_all_time:
            media_str += f" ({_pct_change(media_cur, media_prev)})"
        lines.append(f"🖼 <b>Media sent:</b> {media_str}")

    # Reactions
    reactions_cur = data["reactions_current"]
    reactions_prev = data["reactions_prev"]
    if reactions_cur > 0 or not is_all_time:
        react_str = f"{reactions_cur:,}"
        if not is_all_time:
            react_str += f" ({_pct_change(reactions_cur, reactions_prev)})"
        lines.append(f"👍 <b>Reactions:</b> {react_str}")

    # Stickers sent
    stickers_cur = data["stickers_current"]
    stickers_prev = data["stickers_prev"]
    if stickers_cur > 0 or not is_all_time:
        stickers_str = f"{stickers_cur:,}"
        if not is_all_time:
            stickers_str += f" ({_pct_change(stickers_cur, stickers_prev)})"
        lines.append(f"🎭 <b>Stickers sent:</b> {stickers_str}")

    # GIFs sent
    gifs_cur = data["gifs_current"]
    gifs_prev = data["gifs_prev"]
    if gifs_cur > 0 or not is_all_time:
        gifs_str = f"{gifs_cur:,}"
        if not is_all_time:
            gifs_str += f" ({_pct_change(gifs_cur, gifs_prev)})"
        lines.append(f"🎞 <b>GIFs sent:</b> {gifs_str}")

    # Songs sent
    songs_cur = data["songs_current"]
    songs_prev_val = data["songs_prev"]
    if songs_cur > 0 or not is_all_time:
        songs_str = f"{songs_cur:,}"
        if not is_all_time:
            songs_str += f" ({_pct_change(songs_cur, songs_prev_val)})"
        lines.append(f"🎵 <b>Songs sent:</b> {songs_str}")

    # Active users
    user_extras = []
    if new_count > 0:
        user_extras.append(f"{new_count} new")
    if inactive_count > 0:
        user_extras.append(f"{inactive_count} went inactive")
    user_note = f" ({', '.join(user_extras)})" if user_extras else ""
    lines.append(f"🧍‍♂️ <b>Active users:</b> {active_count}{user_note}")

    # Chat leaderboard
    if data.get("top_users"):
        lines.append("")
        lines.append("🏆 <b>Leaderboard:</b>")
        for i, user in enumerate(data["top_users"], 1):
            name = f"@{user['username']}" if user["username"] else _html(user["first_name"])
            lines.append(f" {i}. {name} — {user['cnt']:,}")
        lines.append("")

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


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show message statistics for the calling user in the current chat."""
    chat_id = str(update.effective_chat.id) if update.effective_chat else "unknown"
    user_id = update.effective_user.id if update.effective_user else "unknown"
    username = update.effective_user.username if update.effective_user and update.effective_user.username else f"ID:{user_id}"
    chat_type = update.effective_chat.type if update.effective_chat else "unknown"

    try:
        general_logger.info(f"mystats_command: chat_id={chat_id}, user_id={user_id}, username={username}")

        stats = await get_user_chat_stats_with_fallback(
            int(chat_id) if str(chat_id).lstrip('-').isdigit() else 0,
            int(user_id) if str(user_id).isdigit() else 0,
            username
        )

        general_logger.info(f"mystats_command: stats={stats}")

        if not stats['total_messages']:
            await update.message.reply_text(
                "📊 У вас ще немає повідомлень в цьому чаті."
            ) if update.message else None
            return

        safe_username = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        message_parts = [
            f"📊 Статистика повідомлень для {safe_username}",
            "",
            f"Загальна кількість повідомлень: {stats['total_messages']}",
            f"Повідомлень за останній тиждень: {stats['messages_last_week']}",
        ]

        chat_behavior_config = await get_shared_config_manager().get_config(chat_id, chat_type, module_name="chat_behavior")
        allowed_commands = chat_behavior_config.get("overrides", {}).get("allowed_commands", [])

        if stats['command_stats']:
            message_parts.extend(["", "Використані команди:"])
            for cmd, count in stats['command_stats']:
                if cmd in allowed_commands:
                    message_parts.append(f"- /{cmd}: {count}")

        if stats['first_message']:
            message_parts.extend(["", f"Перше повідомлення: {stats['first_message'].strftime('%Y-%m-%d')}"])

        try:
            _chat_id_int = int(chat_id) if str(chat_id).lstrip('-').isdigit() else 0
            _user_id_int = int(user_id) if str(user_id).isdigit() else 0
            if _chat_id_int and _user_id_int:
                pool = await Database.get_pool()
                async with pool.acquire() as conn:
                    url_mods_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM bot_events WHERE event_type = 'url_modification' AND chat_id = $1 AND user_id = $2",
                        _chat_id_int, _user_id_int
                    )
                    vid_dl_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM bot_events WHERE event_type = 'video_download' AND chat_id = $1 AND user_id = $2",
                        _chat_id_int, _user_id_int
                    )
                    media_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM messages
                        WHERE chat_id = $1 AND user_id = $2
                          AND (raw_telegram_message ? 'photo' OR raw_telegram_message ? 'video'
                               OR raw_telegram_message ? 'video_note')
                    """, _chat_id_int, _user_id_int)
                    reaction_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM bot_events WHERE event_type = 'reaction' AND chat_id = $1 AND user_id = $2",
                        _chat_id_int, _user_id_int
                    )
                    sticker_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM messages
                        WHERE chat_id = $1 AND user_id = $2
                          AND raw_telegram_message ? 'sticker'
                    """, _chat_id_int, _user_id_int)
                    gif_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM messages
                        WHERE chat_id = $1 AND user_id = $2
                          AND raw_telegram_message ? 'animation'
                    """, _chat_id_int, _user_id_int)
                    song_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM bot_events WHERE event_type = 'song_sent' AND chat_id = $1 AND user_id = $2",
                        _chat_id_int, _user_id_int
                    )
                if url_mods_count:
                    message_parts.append(f"Модифікацій посилань: {url_mods_count}")
                if vid_dl_count:
                    message_parts.append(f"Завантажень відео: {vid_dl_count}")
                if media_count:
                    message_parts.append(f"Медіа надіслано: {media_count}")
                if reaction_count:
                    message_parts.append(f"Реакцій поставлено: {reaction_count}")
                if sticker_count:
                    message_parts.append(f"Стікерів надіслано: {sticker_count}")
                if gif_count:
                    message_parts.append(f"GIF-ів надіслано: {gif_count}")
                if song_count:
                    message_parts.append(f"Пісень надіслано: {song_count}")
        except Exception:
            pass

        await update.message.reply_text(
            "\n".join(message_parts),
            parse_mode=None
        ) if update.message else None

    except Exception as e:
        error_logger.error(f"Error in mystats command: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(
                "❌ Виникла помилка при отриманні статистики. Спробуйте пізніше."
            )
