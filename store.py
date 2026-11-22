"""Store availability helpers shared by the API and public settings response."""

from datetime import datetime, time
from zoneinfo import ZoneInfo


STORE_TIMEZONE = ZoneInfo("Asia/Jakarta")


def is_store_open(settings: dict, current: datetime | None = None) -> bool:
    if not settings.get("store_open", True):
        return False
    if not settings.get("opening_hours_enabled", False):
        return True

    try:
        opens = time.fromisoformat(settings.get("opens_at", "08:00"))
        closes = time.fromisoformat(settings.get("closes_at", "22:00"))
    except (TypeError, ValueError):
        return False

    local_time = (current or datetime.now(STORE_TIMEZONE)).astimezone(STORE_TIMEZONE).time()
    if opens == closes:
        return True
    if opens < closes:
        return opens <= local_time < closes
    return local_time >= opens or local_time < closes
