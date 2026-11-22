"""Coin top-up requests: user asks for N coins, pays manually, uploads proof,
admin approves (coins credited) or rejects."""

import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from lib.ai_check import run_ai_check
from lib.db import db
from lib.defs import PAYMENT_MANUAL, new_code
from lib.dates import now
from lib.proofs import find_duplicates, save_proof
from lib.security import require_user
from lib.serialize import topup_out
from lib.store import is_store_open
from lib.whatsapp import send_admin_transaction_alert
from models.topups import TopupCreate, TopupOut

router = APIRouter(prefix="/topups", tags=["topups"])


@router.post("", response_model=TopupOut)
async def create_topup(input: TopupCreate, background: BackgroundTasks, user: dict = Depends(require_user)):
    if input.payment_method not in PAYMENT_MANUAL:
        raise HTTPException(status_code=400, detail="Metode pembayaran tidak valid untuk top-up coin")

    settings = await db.settings.find_one({"id": "store"}) or {}
    if not is_store_open(settings):
        raise HTTPException(status_code=503, detail="Toko sedang tutup. Top-up coin akan tersedia saat toko buka.")
    if not any(account.get("method") == input.payment_method for account in settings.get("payment_accounts", [])):
        raise HTTPException(status_code=503, detail="Metode pembayaran ini belum diatur oleh admin")
    price_per_100 = int(settings.get("coin_price_idr_per_100", round(float(settings.get("coin_rate", 1.1)) * 100)))
    min_coins = int(settings.get("min_topup_coins", 10000))
    if input.coins < min_coins:
        minimum = f"{min_coins:,}".replace(",", ".")
        raise HTTPException(status_code=400, detail=f"Minimal top-up {minimum} coin")

    amount = math.ceil(input.coins * price_per_100 / 10000) * 100  # price_per_100; bulatkan ke atas ke Rp100
    doc = {
        "id": str(uuid.uuid4()),
        "code": new_code("TUP"),
        "user_id": user["id"],
        "coins": input.coins,
        "amount_idr": amount,
        "payment_method": input.payment_method,
        "status": "menunggu_pembayaran",
        "reject_reason": None,
        "proof_file_id": None,
        "proof_flags": [],
        "ai_verdict": None,
        "created_at": now(),
        "processed_at": None,
    }
    await db.coin_topups.insert_one(doc)
    from routers.community import notify
    await notify(user["id"], "Permintaan top-up dibuat", f"Top-up {doc['code']} menunggu pembayaran sebesar Rp{amount:,}.", "info")
    background.add_task(
        send_admin_transaction_alert,
        doc["code"],
        "Top-up coin baru",
        f"{input.coins:,} coin".replace(",", "."),
        f"Rp{amount:,}".replace(",", "."),
    )
    return topup_out(doc)


@router.get("/mine", response_model=list[TopupOut])
async def my_topups(user: dict = Depends(require_user)):
    docs = await db.coin_topups.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    return [topup_out(d) for d in docs]


@router.post("/{id}/proof", response_model=TopupOut)
async def upload_topup_proof(
    id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    doc = await db.coin_topups.find_one({"id": id, "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Permintaan top-up tidak ditemukan")
    if doc["status"] != "menunggu_pembayaran":
        raise HTTPException(status_code=400, detail="Bukti sudah diunggah atau permintaan sudah diproses")

    content = await file.read()
    try:
        fdoc = await save_proof(
            content, file.content_type,
            uploaded_by=user["id"],
            ref_type="topup", ref_id=doc["id"], ref_code=doc["code"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    flags = await find_duplicates(fdoc["md5"], fdoc.get("phash"), fdoc["id"])
    await db.coin_topups.update_one(
        {"id": doc["id"]},
        {"$set": {
            "proof_file_id": fdoc["id"],
            "proof_flags": flags,
            "ai_verdict": {"ai_status": "pending"},
            "status": "menunggu_verifikasi",
        }},
    )
    from routers.community import notify
    await notify(user["id"], "Bukti top-up diterima", f"Bukti pembayaran untuk {doc['code']} diterima dan menunggu verifikasi admin.", "info")
    background.add_task(
        send_admin_transaction_alert,
        doc["code"],
        "Bukti top-up masuk",
        f"{doc['coins']:,} coin".replace(",", "."),
        f"Rp{doc['amount_idr']:,}".replace(",", "."),
    )
    background.add_task(run_ai_check, "topup", doc["id"], content, file.content_type, doc["amount_idr"])

    doc = await db.coin_topups.find_one({"id": doc["id"]})
    return topup_out(doc)
