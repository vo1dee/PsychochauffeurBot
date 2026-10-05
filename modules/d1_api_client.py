"""Authenticated client for the Psychochauffeur D1 Worker API.

This module intentionally exposes named application operations rather than SQL.
It allows the Python polling bot to dual-write to D1 without granting it a
Cloudflare account token or a database-wide administrative API.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class D1ApiError(RuntimeError):
    """Raised when the D1 Worker rejects or cannot process a request."""


class D1ApiClient:
    """Small async client for the typed D1 Worker API."""

    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    @classmethod
    def from_environment(cls) -> Optional["D1ApiClient"]:
        """Create a client only when the D1 Worker has been configured."""
        base_url = os.getenv("D1_API_URL")
        token = os.getenv("D1_API_TOKEN")
        if not base_url and not token:
            return None
        if not base_url or not token:
            raise D1ApiError("D1_API_URL and D1_API_TOKEN must be configured together")
        return cls(base_url, token, float(os.getenv("D1_API_TIMEOUT_SECONDS", "10")))

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise D1ApiError(f"D1 API request failed: {error}") from error
        if response.is_error:
            detail = (
                data.get("error", response.text)
                if isinstance(data, dict)
                else response.text
            )
            raise D1ApiError(f"D1 API returned {response.status_code}: {detail}")
        if not isinstance(data, dict):
            raise D1ApiError("D1 API returned a non-object response")
        return data

    async def save_chat(
        self, chat_id: int, chat_type: str, title: Optional[str]
    ) -> None:
        """Upsert chat metadata."""
        await self._post(
            "/v1/data/chat",
            {"chat_id": chat_id, "chat_type": chat_type, "title": title},
        )

    async def save_user(
        self,
        user_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        is_bot: bool,
    ) -> None:
        """Upsert user metadata."""
        await self._post(
            "/v1/data/user",
            {
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "is_bot": is_bot,
            },
        )

    async def save_message(self, payload: Dict[str, Any]) -> None:
        """Store one message payload."""
        await self._post("/v1/data/message", payload)

    async def set_analysis_cache(
        self, chat_id: int, time_period: str, message_hash: str, result: str
    ) -> None:
        """Upsert an analysis-cache result."""
        await self._post(
            "/v1/data/cache/set",
            {
                "chat_id": chat_id,
                "time_period": time_period,
                "message_content_hash": message_hash,
                "result": result,
            },
        )

    async def get_analysis_cache(
        self, chat_id: int, time_period: str, message_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Read an analysis-cache row."""
        data = await self._post(
            "/v1/data/cache/get",
            {
                "chat_id": chat_id,
                "time_period": time_period,
                "message_content_hash": message_hash,
            },
        )
        row = data.get("row")
        return row if isinstance(row, dict) else None

    async def invalidate_analysis_cache(
        self, chat_id: int, time_period: Optional[str]
    ) -> None:
        """Delete cache entries for a chat or one period."""
        await self._post(
            "/v1/data/cache/delete", {"chat_id": chat_id, "time_period": time_period}
        )

    async def save_recap_settings(self, row: Dict[str, Any]) -> None:
        """Overwrite a chat's recap settings with the current PostgreSQL row."""
        last_sent = row.get("last_sent_date")
        updated_at = row.get("updated_at")
        await self._post(
            "/v1/data/recap/upsert",
            {
                "chat_id": row["chat_id"],
                "enabled": bool(row["enabled"]),
                "send_time": row["send_time"],
                "last_sent_date": last_sent.isoformat() if last_sent is not None else None,
                "last_pinned_message_id": row.get("last_pinned_message_id"),
                "updated_at": serialize_datetime(updated_at) if updated_at is not None else None,
            },
        )

    async def record_event(
        self, event_type: str, chat_id: int, user_id: Optional[int]
    ) -> None:
        """Append an event record."""
        await self._post(
            "/v1/data/event",
            {"event_type": event_type, "chat_id": chat_id, "user_id": user_id},
        )


_client: Optional[D1ApiClient] = None
_client_lock = asyncio.Lock()


async def get_d1_api_client() -> Optional[D1ApiClient]:
    """Return the configured shared D1 client, if dual-write is enabled."""
    global _client
    if os.getenv("D1_DUAL_WRITE", "false").lower() not in {"1", "true", "yes"}:
        return None
    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = D1ApiClient.from_environment()
    return _client


async def close_d1_api_client() -> None:
    """Close and clear the shared D1 client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def serialize_datetime(value: datetime) -> str:
    """Return a UTC-compatible ISO timestamp accepted by the Worker."""
    return value.isoformat()
