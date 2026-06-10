"""
Read-only stats / analytics queries for the web UI.

All bot activity data (users, chats, messages, bot_events) lives in the
PostgreSQL database managed by modules.database.Database. Errors are parsed
from the rotating logs/error.log files.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from modules.database import Database

TZ = "Europe/Kyiv"

LOG_DIR = Path(__file__).parent.parent / "logs"


# ---------------------------------------------------------------------------
# Admin: users / chats / messages
# ---------------------------------------------------------------------------
async def fetch_users(page: int = 1, per_page: int = 50, q: str = "") -> dict[str, Any]:
    """Paginated user list with message counts and last activity."""
    pool = await Database.get_pool()
    offset = (max(page, 1) - 1) * per_page
    pattern = f"%{q}%"
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT COUNT(*) FROM users u
            WHERE $1 = '' OR u.username ILIKE $2 OR u.first_name ILIKE $2
                  OR u.last_name ILIKE $2 OR CAST(u.user_id AS TEXT) LIKE $2
            """,
            q, pattern,
        )
        rows = await conn.fetch(
            """
            SELECT u.user_id, u.first_name, u.last_name, u.username, u.is_bot,
                   u.created_at,
                   COUNT(m.internal_message_id) AS msg_count,
                   MAX(m.timestamp) AS last_seen,
                   COUNT(DISTINCT m.chat_id) AS chat_count
            FROM users u
            LEFT JOIN messages m ON m.user_id = u.user_id
            WHERE $1 = '' OR u.username ILIKE $2 OR u.first_name ILIKE $2
                  OR u.last_name ILIKE $2 OR CAST(u.user_id AS TEXT) LIKE $2
            GROUP BY u.user_id
            ORDER BY msg_count DESC, u.user_id
            LIMIT $3 OFFSET $4
            """,
            q, pattern, per_page, offset,
        )
    return {"rows": [dict(r) for r in rows], "total": total, "page": page,
            "pages": max(1, -(-total // per_page))}


async def fetch_chats(page: int = 1, per_page: int = 50, q: str = "") -> dict[str, Any]:
    """Paginated chat list with message/user counts and last activity."""
    pool = await Database.get_pool()
    offset = (max(page, 1) - 1) * per_page
    pattern = f"%{q}%"
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT COUNT(*) FROM chats c
            WHERE $1 = '' OR c.title ILIKE $2 OR CAST(c.chat_id AS TEXT) LIKE $2
            """,
            q, pattern,
        )
        rows = await conn.fetch(
            """
            SELECT c.chat_id, c.chat_type, c.title, c.created_at,
                   COUNT(m.internal_message_id) AS msg_count,
                   COUNT(DISTINCT m.user_id) AS user_count,
                   MAX(m.timestamp) AS last_activity
            FROM chats c
            LEFT JOIN messages m ON m.chat_id = c.chat_id
            WHERE $1 = '' OR c.title ILIKE $2 OR CAST(c.chat_id AS TEXT) LIKE $2
            GROUP BY c.chat_id
            ORDER BY msg_count DESC, c.chat_id
            LIMIT $3 OFFSET $4
            """,
            q, pattern, per_page, offset,
        )
    return {"rows": [dict(r) for r in rows], "total": total, "page": page,
            "pages": max(1, -(-total // per_page))}


async def fetch_messages(
    page: int = 1,
    per_page: int = 50,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    q: str = "",
    only_commands: bool = False,
    only_gpt: bool = False,
) -> dict[str, Any]:
    """Paginated message browser with filters."""
    pool = await Database.get_pool()
    offset = (max(page, 1) - 1) * per_page

    where = ["TRUE"]
    params: list[Any] = []

    def arg(value: Any) -> str:
        params.append(value)
        return f"${len(params)}"

    if chat_id is not None:
        where.append(f"m.chat_id = {arg(chat_id)}")
    if user_id is not None:
        where.append(f"m.user_id = {arg(user_id)}")
    if q:
        where.append(f"m.text ILIKE {arg(f'%{q}%')}")
    if only_commands:
        where.append("m.is_command = TRUE")
    if only_gpt:
        where.append("m.is_gpt_reply = TRUE")
    where_sql = " AND ".join(where)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM messages m WHERE {where_sql}", *params
        )
        rows = await conn.fetch(
            f"""
            SELECT m.internal_message_id, m.message_id, m.chat_id, m.user_id,
                   m.timestamp, m.text, m.is_command, m.command_name, m.is_gpt_reply,
                   c.title AS chat_title,
                   u.username, u.first_name, u.last_name
            FROM messages m
            LEFT JOIN chats c ON c.chat_id = m.chat_id
            LEFT JOIN users u ON u.user_id = m.user_id
            WHERE {where_sql}
            ORDER BY m.timestamp DESC
            LIMIT {arg(per_page)} OFFSET {arg(offset)}
            """,
            *params,
        )
    return {"rows": [dict(r) for r in rows], "total": total, "page": page,
            "pages": max(1, -(-total // per_page))}


async def fetch_chat_options() -> list[dict[str, Any]]:
    """Compact chat list for filter dropdowns."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id, chat_type, title FROM chats ORDER BY title NULLS LAST"
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
def _fill_days(rows: list[dict[str, Any]], days: int, keys: list[str]) -> list[dict[str, Any]]:
    """Fill gaps so charts have one point per day, zeroes where no data."""
    by_day = {r["day"].isoformat(): r for r in rows}
    out = []
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        src = by_day.get(d, {})
        out.append({"day": d, **{k: src.get(k, 0) or 0 for k in keys}})
    return out


async def fetch_summary() -> dict[str, Any]:
    """Headline counters for the analytics page."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                (SELECT COUNT(*) FROM messages) AS total_messages,
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM chats) AS total_chats,
                (SELECT COUNT(*) FROM messages WHERE is_command) AS total_commands,
                (SELECT COUNT(*) FROM messages WHERE is_gpt_reply) AS total_gpt,
                (SELECT COUNT(*) FROM messages
                  WHERE (timestamp AT TIME ZONE '{TZ}')::date = (NOW() AT TIME ZONE '{TZ}')::date)
                  AS messages_today,
                (SELECT COUNT(DISTINCT user_id) FROM messages
                  WHERE (timestamp AT TIME ZONE '{TZ}')::date = (NOW() AT TIME ZONE '{TZ}')::date)
                  AS active_users_today,
                (SELECT COUNT(DISTINCT user_id) FROM messages
                  WHERE timestamp >= NOW() - INTERVAL '7 days') AS active_users_7d,
                (SELECT COUNT(DISTINCT user_id) FROM messages
                  WHERE timestamp >= NOW() - INTERVAL '30 days') AS active_users_30d,
                (SELECT COUNT(*) FROM bot_events) AS total_events
            """
        )
    return dict(row)


async def fetch_activity_series(days: int = 30) -> list[dict[str, Any]]:
    """Per-day messages, active users, commands, GPT replies."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT (timestamp AT TIME ZONE '{TZ}')::date AS day,
                   COUNT(*) AS messages,
                   COUNT(DISTINCT user_id) AS active_users,
                   COUNT(*) FILTER (WHERE is_command) AS commands,
                   COUNT(*) FILTER (WHERE is_gpt_reply) AS gpt_replies
            FROM messages
            WHERE timestamp >= (NOW() AT TIME ZONE '{TZ}')::date - $1::int + 1
            GROUP BY 1 ORDER BY 1
            """,
            days,
        )
    return _fill_days([dict(r) for r in rows], days,
                      ["messages", "active_users", "commands", "gpt_replies"])


async def fetch_new_users_series(days: int = 30) -> list[dict[str, Any]]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT (created_at AT TIME ZONE '{TZ}')::date AS day, COUNT(*) AS new_users
            FROM users
            WHERE created_at >= (NOW() AT TIME ZONE '{TZ}')::date - $1::int + 1
            GROUP BY 1 ORDER BY 1
            """,
            days,
        )
    return _fill_days([dict(r) for r in rows], days, ["new_users"])


async def fetch_hourly_histogram(days: int = 30) -> list[int]:
    """Messages per hour of day (0-23), local time."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT EXTRACT(HOUR FROM timestamp AT TIME ZONE '{TZ}')::int AS hour,
                   COUNT(*) AS count
            FROM messages
            WHERE timestamp >= NOW() - ($1::int || ' days')::interval
            GROUP BY 1
            """,
            days,
        )
    counts = [0] * 24
    for r in rows:
        counts[r["hour"]] = r["count"]
    return counts


async def fetch_weekday_histogram(days: int = 30) -> list[int]:
    """Messages per day of week (0=Mon .. 6=Sun), local time."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT EXTRACT(ISODOW FROM timestamp AT TIME ZONE '{TZ}')::int - 1 AS dow,
                   COUNT(*) AS count
            FROM messages
            WHERE timestamp >= NOW() - ($1::int || ' days')::interval
            GROUP BY 1
            """,
            days,
        )
    counts = [0] * 7
    for r in rows:
        counts[r["dow"]] = r["count"]
    return counts


async def fetch_top_chats(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.chat_id, COALESCE(c.title, CAST(m.chat_id AS TEXT)) AS title,
                   COUNT(*) AS count
            FROM messages m LEFT JOIN chats c ON c.chat_id = m.chat_id
            WHERE m.timestamp >= NOW() - ($1::int || ' days')::interval
            GROUP BY m.chat_id, c.title ORDER BY count DESC LIMIT $2
            """,
            days, limit,
        )
    return [dict(r) for r in rows]


async def fetch_top_users(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.user_id,
                   COALESCE(u.username, u.first_name, CAST(m.user_id AS TEXT)) AS name,
                   COUNT(*) AS count
            FROM messages m JOIN users u ON u.user_id = m.user_id
            WHERE m.timestamp >= NOW() - ($1::int || ' days')::interval
              AND u.is_bot = FALSE
            GROUP BY m.user_id, u.username, u.first_name
            ORDER BY count DESC LIMIT $2
            """,
            days, limit,
        )
    return [dict(r) for r in rows]


async def fetch_top_commands(days: int = 30, limit: int = 15) -> list[dict[str, Any]]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT command_name, COUNT(*) AS count
            FROM messages
            WHERE is_command AND command_name IS NOT NULL
              AND timestamp >= NOW() - ($1::int || ' days')::interval
            GROUP BY command_name ORDER BY count DESC LIMIT $2
            """,
            days, limit,
        )
    return [dict(r) for r in rows]


async def fetch_bot_events(days: int = 30) -> dict[str, Any]:
    """Bot event totals by type + per-day series."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        totals = await conn.fetch(
            """
            SELECT event_type, COUNT(*) AS count
            FROM bot_events
            WHERE timestamp >= NOW() - ($1::int || ' days')::interval
            GROUP BY event_type ORDER BY count DESC
            """,
            days,
        )
        daily = await conn.fetch(
            f"""
            SELECT (timestamp AT TIME ZONE '{TZ}')::date AS day, event_type,
                   COUNT(*) AS count
            FROM bot_events
            WHERE timestamp >= (NOW() AT TIME ZONE '{TZ}')::date - $1::int + 1
            GROUP BY 1, 2 ORDER BY 1
            """,
            days,
        )
    types = [r["event_type"] for r in totals]
    series: dict[str, dict[str, int]] = {t: {} for t in types}
    for r in daily:
        series[r["event_type"]][r["day"].isoformat()] = r["count"]
    today = date.today()
    labels = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    return {
        "totals": [dict(r) for r in totals],
        "labels": labels,
        "series": {t: [series[t].get(d, 0) for d in labels] for t in types},
    }


async def fetch_retention(weeks: int = 10) -> dict[str, Any]:
    """Weekly cohort retention: % of each first-seen cohort active N weeks later."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH first_seen AS (
                SELECT user_id, date_trunc('week', MIN(timestamp)) AS cohort_week
                FROM messages WHERE user_id IS NOT NULL
                GROUP BY user_id
            ),
            activity AS (
                SELECT DISTINCT user_id, date_trunc('week', timestamp) AS active_week
                FROM messages WHERE user_id IS NOT NULL
            )
            SELECT f.cohort_week,
                   (EXTRACT(EPOCH FROM (a.active_week - f.cohort_week)) / 604800)::int
                       AS week_offset,
                   COUNT(DISTINCT a.user_id) AS users
            FROM first_seen f
            JOIN activity a USING (user_id)
            WHERE f.cohort_week >= date_trunc('week', NOW()) - ($1::int || ' weeks')::interval
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            weeks,
        )
    cohorts: dict[str, dict[int, int]] = {}
    for r in rows:
        week = r["cohort_week"].date().isoformat()
        cohorts.setdefault(week, {})[r["week_offset"]] = r["users"]

    max_offset = min(weeks, max((max(v) for v in cohorts.values()), default=0))
    table = []
    for week in sorted(cohorts):
        size = cohorts[week].get(0, 0)
        cells = []
        for off in range(max_offset + 1):
            users = cohorts[week].get(off)
            pct = round(users / size * 100) if size and users is not None else None
            cells.append({"users": users, "pct": pct})
        table.append({"week": week, "size": size, "cells": cells})
    return {"table": table, "max_offset": max_offset}


# ---------------------------------------------------------------------------
# Errors (parsed from logs/error.log*)
# ---------------------------------------------------------------------------
_LOG_LINE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}),\d+ [+-]\d{4} - "
    r"(?P<logger>\S+) - (?P<level>\w+) - (?P<rest>.*)$"
)
_CTX = re.compile(r"^Ctx:\[[^\]]*\]\[[^\]]*\]\[[^\]]*\]\[[^\]]*\] - ")


def _normalize_error(msg: str) -> str:
    """Collapse variable parts (URLs, ids) so similar errors group together."""
    msg = re.sub(r"https?://\S+", "<url>", msg)
    msg = re.sub(r"\b\d{5,}\b", "<id>", msg)
    return msg.strip()[:120]


def parse_error_log(days: int = 30, recent_limit: int = 50) -> dict[str, Any]:
    """Parse rotating error logs into per-day counts, top groups, recent entries."""
    cutoff = datetime.now() - timedelta(days=days)
    entries: list[dict[str, Any]] = []

    files = [LOG_DIR / "error.log"]
    files += sorted(LOG_DIR.glob("error.log.*"),
                    key=lambda p: p.stat().st_mtime, reverse=True)

    for path in files:
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                current: Optional[dict[str, Any]] = None
                for line in f:
                    m = _LOG_LINE.match(line.rstrip("\n"))
                    if m:
                        msg = _CTX.sub("", m.group("rest"))
                        current = {
                            "timestamp": f"{m.group('date')} {m.group('time')}",
                            "date": m.group("date"),
                            "level": m.group("level"),
                            "message": msg,
                        }
                        if current["timestamp"] >= cutoff.strftime("%Y-%m-%d %H:%M:%S"):
                            entries.append(current)
                        else:
                            current = None
                    elif current is not None and len(current["message"]) < 4000:
                        # Continuation line (traceback) — attach to last entry
                        current["message"] += "\n" + line.rstrip("\n")
        except OSError:
            continue

    entries.sort(key=lambda e: e["timestamp"], reverse=True)

    by_day: dict[str, int] = {}
    groups: dict[str, int] = {}
    for e in entries:
        by_day[e["date"]] = by_day.get(e["date"], 0) + 1
        key = _normalize_error(e["message"].splitlines()[0])
        groups[key] = groups.get(key, 0) + 1

    today = date.today()
    labels = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    return {
        "total": len(entries),
        "labels": labels,
        "daily": [by_day.get(d, 0) for d in labels],
        "top_groups": sorted(
            ({"message": k, "count": v} for k, v in groups.items()),
            key=lambda g: g["count"], reverse=True,
        )[:15],
        "recent": entries[:recent_limit],
    }
