"""Server-side date helpers. The pod clock is UTC — anchor "today" here, never in the browser."""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now() -> datetime:
    """Aware UTC now — always store aware datetimes so Pydantic serialises with the offset."""
    return datetime.now(timezone.utc)


def utc(dt: datetime | None) -> datetime | None:
    """Motor hands back naive datetimes; normalise to aware UTC before serialising."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def today_iso(tz: str | None = None) -> str:
    """Today's date as YYYY-MM-DD in `tz` (default: APP_TZ env, else UTC)."""
    zone = tz or os.environ.get("APP_TZ", "UTC")
    return datetime.now(ZoneInfo(zone)).strftime("%Y-%m-%d")
