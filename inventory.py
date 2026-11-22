"""Robux inventory with atomic reservations for paid orders and coin orders."""

from lib.db import db


class StockUnavailable(Exception):
    pass


async def available_robux(settings: dict | None = None) -> int | None:
    doc = settings if settings is not None else await db.settings.find_one({"id": "store"}) or {}
    total = doc.get("robux_stock")
    if total is None:
        return None
    return max(0, int(total) - int(doc.get("robux_stock_reserved", 0)))


async def ensure_stock_available(amount: int) -> None:
    current = await available_robux()
    if current is not None and current < amount:
        raise StockUnavailable(f"Stok tersisa {current:,} Robux. Pesanan ini membutuhkan {amount:,} Robux.".replace(",", "."))


async def reserve_robux(amount: int) -> bool:
    """Reserve inventory atomically; return False if the shop does not track stock."""
    result = await db.settings.update_one(
        {
            "id": "store",
            "robux_stock": {"$type": "number"},
            "$expr": {
                "$gte": [
                    {"$subtract": ["$robux_stock", {"$ifNull": ["$robux_stock_reserved", 0]}]},
                    amount,
                ]
            },
        },
        {"$inc": {"robux_stock_reserved": amount}},
    )
    if result.modified_count:
        return True

    current = await db.settings.find_one({"id": "store"}) or {}
    if current.get("robux_stock") is None:
        return False
    available = await available_robux(current) or 0
    raise StockUnavailable(f"Stok tersisa {available:,} Robux. Pesanan ini membutuhkan {amount:,} Robux.".replace(",", "."))


async def release_robux(amount: int) -> None:
    await db.settings.update_one(
        {"id": "store", "robux_stock_reserved": {"$gte": amount}},
        {"$inc": {"robux_stock_reserved": -amount}},
    )


async def consume_robux(amount: int) -> bool:
    result = await db.settings.update_one(
        {
            "id": "store",
            "robux_stock": {"$type": "number", "$gte": amount},
            "robux_stock_reserved": {"$gte": amount},
        },
        {"$inc": {"robux_stock": -amount, "robux_stock_reserved": -amount}},
    )
    return bool(result.modified_count)
