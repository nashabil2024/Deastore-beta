"""Order lifecycle: create (manual payment or coin), track by code, upload payment proof.

Manual payment → status menunggu_pembayaran until a proof is uploaded, then
menunggu_verifikasi (admin approves/rejects). Coin payment requires login and
atomically deducts the discounted coin price; the order lands directly in diproses.
"""

import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from lib.ai_check import run_ai_check
from lib.db import db
from lib.defs import PAYMENT_METHODS, new_code
from lib.dates import now
from lib.inventory import StockUnavailable, ensure_stock_available, release_robux, reserve_robux
from lib.proofs import find_duplicates, save_proof
from lib.roblox import lookup
from lib.security import get_current_user, require_user
from lib.serialize import order_out
from lib.store import is_store_open
from lib.whatsapp import send_admin_transaction_alert
from models.orders import OrderCreate, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


async def get_settings_doc() -> dict:
    return await db.settings.find_one({"id": "store"}) or {}


def payment_is_configured(method: str, settings: dict) -> bool:
    """QRIS can be configured using the QR image alone; other methods need an account."""
    if method == "qris" and settings.get("qris_image_file_id"):
        return True
    return any(account.get("method") == method for account in settings.get("payment_accounts", []))


async def reserve_voucher(voucher: dict) -> None:
    """Atomically reserve one voucher use so concurrent orders cannot exceed its cap."""
    max_uses = voucher.get("max_uses")
    query = {"id": voucher["id"], "active": True}
    if max_uses is not None:
        query["uses"] = {"$lt": int(max_uses)}
    result = await db.vouchers.update_one(query, {"$inc": {"uses": 1}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Kuota voucher baru saja habis. Silakan gunakan kode lain.")


async def release_voucher(voucher: dict) -> None:
    await db.vouchers.update_one({"id": voucher["id"], "uses": {"$gt": 0}}, {"$inc": {"uses": -1}})


@router.post("", response_model=OrderOut)
async def create_order(
    input: OrderCreate,
    background: BackgroundTasks,
    user: dict | None = Depends(get_current_user),
):
    method = input.payment_method
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Metode pembayaran tidak valid")

    settings = await get_settings_doc()
    if not is_store_open(settings):
        raise HTTPException(status_code=503, detail="Toko sedang tutup. Silakan kembali saat toko buka.")
    pkg = await db.packages.find_one({"robux": input.robux, "active": True})
    if pkg:
        price_idr = int(pkg["price_idr"])
        price_source = "package"
    else:
        # Any quantity is allowed. The total is rounded up to whole rupiah
        # from the public 1,000 Robux price configured by the admin.
        base_per_1000 = int(settings.get("custom_robux_price_per_1000_idr", 150000))
        price_idr = math.ceil(input.robux * base_per_1000 / 1000)
        price_source = "custom"
    # Preserve the catalog price separately from the discounted payable total.
    base_price_idr = price_idr
    # Optional promo voucher is validated and reserved before the order is committed.
    voucher = None
    promo_discount_idr = 0
    if input.voucher_code:
        if not user:
            raise HTTPException(status_code=401, detail="Login untuk menggunakan voucher")
        voucher = await db.vouchers.find_one({"code": input.voucher_code.strip().upper(), "active": True})
        if not voucher:
            raise HTTPException(status_code=400, detail="Voucher tidak valid atau sudah tidak aktif")
        if price_idr < int(voucher.get("min_order", 0)):
            raise HTTPException(status_code=400, detail=f"Minimal transaksi voucher Rp{int(voucher.get('min_order', 0)):,}")
        expiry = voucher.get("expires_at")
        if expiry and str(expiry) < now().isoformat():
            raise HTTPException(status_code=400, detail="Voucher sudah kedaluwarsa")
        max_uses = voucher.get("max_uses")
        if max_uses is not None and int(voucher.get("uses", 0)) >= int(max_uses):
            raise HTTPException(status_code=400, detail="Kuota voucher sudah habis")
        if voucher.get("kind") == "percent":
            promo_discount_idr = math.floor(price_idr * int(voucher["value"]) / 100)
        else:
            promo_discount_idr = min(price_idr, int(voucher["value"]))
        price_idr = max(0, price_idr - promo_discount_idr)

    discount = 0
    total_coins = None
    if method == "coin":
        if not user:
            raise HTTPException(status_code=401, detail="Login dulu untuk membayar dengan Saldo Coin")
        discount = int(settings.get("coin_discount_percent", 10))
        price_per_100 = int(settings.get("coin_price_idr_per_100", round(float(settings.get("coin_rate", 1.1)) * 100)))
        total_coins = math.ceil(price_idr * (100 - discount) / price_per_100)
    elif not payment_is_configured(method, settings):
        raise HTTPException(status_code=503, detail="Metode pembayaran ini belum diatur oleh admin")
    else:
        try:
            await ensure_stock_available(input.robux)
        except StockUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    res = await lookup(input.roblox_username)
    profile = res.get("profile")
    verified = res.get("status") == "found"

    stock_reserved = False
    if method == "coin":
        try:
            stock_reserved = await reserve_robux(input.robux)
        except StockUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    order = {
        "id": str(uuid.uuid4()),
        "code": new_code("DEA"),
        "user_id": user["id"] if user else None,
        "roblox_username": input.roblox_username.strip(),
        "roblox_profile": profile,
        "roblox_verified": verified,
        "robux": input.robux,
        "price_idr": base_price_idr,
        "price_source": price_source,
        "discount_percent": discount,
        "total_idr": price_idr,
        "voucher_code": voucher.get("code") if voucher else None,
        "promo_discount_idr": promo_discount_idr,
        "total_coins": total_coins,
        "payment_method": method,
        "status": "menunggu_pembayaran",
        "note": input.note,
        "reject_reason": None,
        "proof_file_id": None,
        "proof_flags": [],
        "ai_verdict": None,
        "created_at": now(),
        "updated_at": now(),
        "processed_at": None,
        "stock_reserved": stock_reserved,
    }

    if method == "coin":
        # Atomic check-and-deduct: only succeeds when the balance is sufficient.
        deducted = await db.users.find_one_and_update(
            {"id": user["id"], "coins": {"$gte": total_coins}},
            {"$inc": {"coins": -total_coins}},
        )
        if not deducted:
            if stock_reserved:
                await release_robux(input.robux)
            needed = f"{total_coins:,}".replace(",", ".")
            raise HTTPException(
                status_code=400,
                detail=f"Saldo coin tidak cukup. Butuh {needed} coin (diskon {discount}%). Top-up coin dulu ya.",
            )
        order["status"] = "diproses"
        order["processed_at"] = now()
        voucher_reserved = False
        try:
            if voucher:
                await reserve_voucher(voucher)
                voucher_reserved = True
            await db.orders.insert_one(order)
        except Exception:
            if voucher_reserved:
                await release_voucher(voucher)
            await db.users.update_one({"id": user["id"]}, {"$inc": {"coins": total_coins}})  # refund
            if stock_reserved:
                await release_robux(input.robux)
            raise
    else:
        voucher_reserved = False
        try:
            if voucher:
                await reserve_voucher(voucher)
                voucher_reserved = True
            await db.orders.insert_one(order)
        except Exception:
            if voucher_reserved:
                await release_voucher(voucher)
            raise

    if user:
        from routers.community import notify
        await notify(user["id"], "Pesanan berhasil dibuat", f"Pesanan {order['code']} berhasil dibuat dan statusnya {order['status']}.", "success")

    total_label = f"{total_coins:,} coin".replace(",", ".") if total_coins is not None else f"Rp{price_idr:,}".replace(",", ".")
    background.add_task(
        send_admin_transaction_alert,
        order["code"],
        "Pesanan Robux",
        input.roblox_username.strip(),
        total_label,
    )

    return order_out(order)


@router.get("/mine", response_model=list[OrderOut])
async def my_orders(user: dict = Depends(require_user)):
    docs = await db.orders.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    return [order_out(d) for d in docs]


@router.get("/{code}", response_model=OrderOut)
async def get_order(code: str):
    doc = await db.orders.find_one({"code": code.upper().strip()})
    if not doc:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan. Periksa kembali kode pesanan.")
    return order_out(doc)


@router.post("/{code}/proof", response_model=OrderOut)
async def upload_proof(
    code: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict | None = Depends(get_current_user),
):
    doc = await db.orders.find_one({"code": code.upper().strip()})
    if not doc:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    if doc["status"] != "menunggu_pembayaran":
        raise HTTPException(status_code=400, detail="Bukti pembayaran sudah diunggah atau pesanan sudah diproses")

    content = await file.read()
    stock_reserved = False
    try:
        stock_reserved = await reserve_robux(doc["robux"])
        fdoc = await save_proof(
            content, file.content_type,
            uploaded_by=doc.get("user_id"),
            ref_type="order", ref_id=doc["id"], ref_code=doc["code"],
        )
    except StockUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        if stock_reserved:
            await release_robux(doc["robux"])
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        if stock_reserved:
            await release_robux(doc["robux"])
        raise

    try:
        flags = await find_duplicates(fdoc["md5"], fdoc.get("phash"), fdoc["id"])
        updated = await db.orders.update_one(
            {"id": doc["id"], "status": "menunggu_pembayaran"},
            {"$set": {
                "proof_file_id": fdoc["id"],
                "proof_flags": flags,
                "ai_verdict": {"ai_status": "pending"},
                "status": "menunggu_verifikasi",
                "updated_at": now(),
                "stock_reserved": stock_reserved,
            }},
        )
        if not updated.modified_count:
            if stock_reserved:
                await release_robux(doc["robux"])
            raise HTTPException(status_code=409, detail="Pesanan berubah saat bukti dikirim. Segarkan status pesanan lalu coba lagi.")
    except HTTPException:
        raise
    except Exception:
        if stock_reserved:
            await release_robux(doc["robux"])
        raise

    background.add_task(
        send_admin_transaction_alert,
        doc["code"],
        "Bukti pembayaran masuk",
        doc["roblox_username"],
        f"Rp{doc['total_idr']:,}".replace(",", "."),
    )
    background.add_task(run_ai_check, "order", doc["id"], content, file.content_type, doc["total_idr"])

    doc = await db.orders.find_one({"id": doc["id"]})
    return order_out(doc)
