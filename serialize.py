"""Pydantic serializers shared by routers — keep in sync with frontend/src/lib/types.ts."""

from lib.dates import utc
from lib.store import is_store_open
from models.admin import AdminUserOut, SettingsOut
from models.auth import UserOut
from models.catalog import PackageOut
from models.orders import OrderOut
from models.shared import AiVerdict, FakeFlag, RobloxProfile
from models.topups import TopupOut


def user_out(u: dict) -> UserOut:
    return UserOut(
        id=u["id"],
        username=u["username"],
        role=u.get("role", "user"),
        coins=u.get("coins", 0),
        created_at=utc(u["created_at"]),
    )


def admin_user_out(u: dict) -> AdminUserOut:
    return AdminUserOut(
        id=u["id"],
        username=u["username"],
        role=u.get("role", "user"),
        coins=u.get("coins", 0),
        created_at=utc(u["created_at"]),
    )


def package_out(d: dict) -> PackageOut:
    return PackageOut(
        id=d["id"],
        robux=d["robux"],
        price_idr=d["price_idr"],
        tag=d.get("tag"),
        active=d.get("active", True),
        sort=d.get("sort", 0),
    )


def order_out(doc: dict) -> OrderOut:
    return OrderOut(
        id=doc["id"],
        code=doc["code"],
        user_id=doc.get("user_id"),
        roblox_username=doc["roblox_username"],
        roblox_profile=RobloxProfile(**doc["roblox_profile"]) if doc.get("roblox_profile") else None,
        roblox_verified=doc.get("roblox_verified", False),
        robux=doc["robux"],
        price_idr=doc["price_idr"],
        discount_percent=doc.get("discount_percent", 0),
        total_idr=doc["total_idr"],
        voucher_code=doc.get("voucher_code"),
        promo_discount_idr=doc.get("promo_discount_idr", 0),
        total_coins=doc.get("total_coins"),
        payment_method=doc["payment_method"],
        status=doc["status"],
        note=doc.get("note"),
        reject_reason=doc.get("reject_reason"),
        proof_file_id=doc.get("proof_file_id"),
        proof_flags=[FakeFlag(**f) for f in doc.get("proof_flags", [])],
        ai_verdict=AiVerdict(**doc["ai_verdict"]) if doc.get("ai_verdict") else None,
        created_at=utc(doc["created_at"]),
        updated_at=utc(doc["updated_at"]),
        processed_at=utc(doc.get("processed_at")),
    )


def topup_out(doc: dict) -> TopupOut:
    return TopupOut(
        id=doc["id"],
        code=doc["code"],
        user_id=doc["user_id"],
        coins=doc["coins"],
        amount_idr=doc["amount_idr"],
        payment_method=doc["payment_method"],
        status=doc["status"],
        reject_reason=doc.get("reject_reason"),
        proof_file_id=doc.get("proof_file_id"),
        proof_flags=[FakeFlag(**f) for f in doc.get("proof_flags", [])],
        ai_verdict=AiVerdict(**doc["ai_verdict"]) if doc.get("ai_verdict") else None,
        created_at=utc(doc["created_at"]),
        processed_at=utc(doc.get("processed_at")),
    )


def settings_out(doc: dict) -> SettingsOut:
    legacy_rate = float(doc.get("coin_rate", 1.1))
    price_per_100 = int(doc.get("coin_price_idr_per_100", round(legacy_rate * 100)))
    return SettingsOut(
        wa_number=doc.get("wa_number", ""),
        payment_accounts=doc.get("payment_accounts", []),
        coin_rate=price_per_100 / 100,
        coin_price_idr_per_100=price_per_100,
        coin_discount_percent=int(doc.get("coin_discount_percent", 10)),
        min_topup_coins=int(doc.get("min_topup_coins", 10000)),
        announcement=doc.get("announcement"),
        maintenance=bool(doc.get("maintenance", False)),
        qris_image_file_id=doc.get("qris_image_file_id"),
        store_name=doc.get("store_name", "Dea Store"),
        logo_file_id=doc.get("logo_file_id"),
        hero_title=doc.get("hero_title", "Top Up Robux Murah & Instan"),
        hero_subtitle=doc.get("hero_subtitle", "Cek username, pilih paket, lalu pesan dengan mudah."),
        store_open=bool(doc.get("store_open", True)),
        store_open_now=is_store_open(doc),
        opening_hours_enabled=bool(doc.get("opening_hours_enabled", False)),
        opens_at=doc.get("opens_at", "08:00"),
        closes_at=doc.get("closes_at", "22:00"),
        robux_stock=doc.get("robux_stock"),
        robux_stock_available=(
            max(0, int(doc["robux_stock"]) - int(doc.get("robux_stock_reserved", 0)))
            if doc.get("robux_stock") is not None else None
        ),
        custom_robux_price_per_1000_idr=int(doc.get("custom_robux_price_per_1000_idr", 150000)),
    )
