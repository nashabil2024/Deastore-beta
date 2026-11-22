"""Seed Dea Store: admin account, Robux packages, store settings. Idempotent.

Run: cd backend && set ADMIN_USERNAME and ADMIN_PASSWORD, then python seed.py.
"""

import asyncio
import os
import uuid

from lib.db import client, db, ensure_indexes
from lib.dates import now
from lib.security import hash_password

PRICE_PER_ROBUX = 150  # 1.000 Robux = Rp150.000

PACKAGES: list[tuple[int, str | None]] = [
    (100, "Starter"), (200, None), (300, None), (400, "Hemat"), (500, None),
    (600, None), (700, None), (800, "Favorite"), (900, None), (1000, "Best Seller"),
    (1500, None), (2000, "Pro Gamer"), (3000, None), (5000, "Whale Pack"), (10000, "Ultimate"),
]

async def main() -> None:
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_username or len(admin_password) < 12:
        raise RuntimeError("ADMIN_USERNAME dan ADMIN_PASSWORD (minimal 12 karakter) wajib diatur")

    await ensure_indexes()

    if not await db.users.find_one({"username_lower": admin_username.lower()}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "username": admin_username,
            "username_lower": admin_username.lower(),
            "password_hash": hash_password(admin_password),
            "role": "admin",
            "coins": 0,
            "created_at": now(),
        })
        print(f"akun admin dibuat: {admin_username}")

    for sort, (robux, tag) in enumerate(PACKAGES):
        await db.packages.update_one(
            {"robux": robux},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "robux": robux,
                "price_idr": robux * PRICE_PER_ROBUX,
                "tag": tag,
                "active": True,
                "sort": sort,
            }},
            upsert=True,
        )
    print(f"{len(PACKAGES)} paket robux siap")

    await db.settings.update_one(
        {"id": "store"},
        {"$setOnInsert": {
            "id": "store",
            "wa_number": "",
            "payment_accounts": [],
            "coin_rate": 1.1,
            "coin_price_idr_per_100": 110,
            "coin_discount_percent": 10,
            "min_topup_coins": 10000,
            "announcement": "Selamat datang di Dea Store! Bayar pakai Saldo Coin dapat diskon 10%.",
            "maintenance": True,
            "qris_image_file_id": None,
            "store_name": "Dea Store",
            "logo_file_id": None,
            "hero_title": "Top Up Robux Murah & Instan",
            "hero_subtitle": "Cek username, pilih paket, lalu pesan dengan mudah.",
            "store_open": True,
            "opening_hours_enabled": False,
            "opens_at": "08:00",
            "closes_at": "22:00",
            "robux_stock": None,
            "robux_stock_reserved": 0,
            "custom_robux_price_per_1000_idr": 150000,
        }},
        upsert=True,
    )
    print("pengaturan toko siap")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
