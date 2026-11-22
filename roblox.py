"""Roblox username resolution via the public Roblox web APIs, with a Mongo TTL cache.

Called server-side only (browser CORS + datacenter IP concerns stay out of the client).
If Roblox is unreachable the lookup degrades to status="unavailable" and the order flow
continues with a manual-check warning, per the store owner's preference.
"""

import asyncio
import logging
import random
import time

import httpx

from lib.db import db

logger = logging.getLogger(__name__)

USERS_URL = "https://users.roblox.com/v1/usernames/users"
THUMBS_URL = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
CACHE_TTL_SECONDS = 3600

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers={"User-Agent": "dea-store/1.0"},
        )
    return _client


class RobloxUnavailable(Exception):
    pass


async def _request(method: str, url: str, **kwargs) -> dict:
    """Retry only transient failures (429/5xx/timeouts) with capped backoff."""
    last: Exception | None = None
    for attempt in range(3):
        try:
            res = await _get_client().request(method, url, **kwargs)
            if res.status_code == 429 or res.status_code >= 500:
                delay = float(res.headers["retry-after"]) if res.headers.get("retry-after", "").isdigit() else 0.5 * (2**attempt)
                await asyncio.sleep(min(delay + random.random() * 0.2, 4.0))
                continue
            res.raise_for_status()
            return res.json()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                break
            await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
    raise RobloxUnavailable(str(last))


async def lookup(username: str) -> dict:
    """Return {"status": "found"|"not_found"|"unavailable", "profile": {...}|None}."""
    username = username.strip()
    key = username.lower()
    cached = await db.roblox_cache.find_one({"username": key})
    if cached and time.time() - cached.get("cached_at", 0) < CACHE_TTL_SECONDS:
        return {
            "status": "found",
            "profile": {
                "username": cached.get("roblox_name") or cached.get("profile", {}).get("username", username),
                "display_name": cached.get("display_name"),
                "user_id": cached.get("user_id"),
                "avatar_url": cached.get("avatar_url"),
            },
        }

    try:
        data = await _request("POST", USERS_URL, json={"usernames": [username], "excludeBannedUsers": False})
        matches = data.get("data") or []
        user = next(
            (u for u in matches if u.get("requestedUsername", "").casefold() == username.casefold()),
            None,
        )
        if not user:
            return {"status": "not_found", "profile": None}

        user_id = int(user["id"])
        avatar_url = None
        try:
            thumbs = await _request(
                "GET",
                THUMBS_URL,
                params={"userIds": str(user_id), "size": "420x420", "format": "Png", "isCircular": "false"},
            )
            item = next((x for x in (thumbs.get("data") or []) if int(x.get("targetId", -1)) == user_id), None)
            if item and item.get("state") == "Completed":
                avatar_url = item.get("imageUrl")
        except RobloxUnavailable:
            pass  # headshot is optional decoration; the resolved profile is enough

        profile = {
            "username": user.get("name") or username,
            "display_name": user.get("displayName"),
            "user_id": user_id,
            "avatar_url": avatar_url,
        }
        await db.roblox_cache.update_one(
            {"username": key},
            {"$set": {
                "username": key,
                "roblox_name": profile["username"],
                "display_name": profile["display_name"],
                "user_id": profile["user_id"],
                "avatar_url": profile["avatar_url"],
                "cached_at": time.time(),
            }},
            upsert=True,
        )
        return {"status": "found", "profile": profile}
    except RobloxUnavailable as exc:
        logger.warning("Roblox lookup unavailable for %r: %s", username, exc)
        return {"status": "unavailable", "profile": None}
