"""Store settings: public read (payment info, coin rules), admin write."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from lib.db import db
from lib.dates import now
from lib.proofs import save_proof
from lib.security import require_admin
from lib.serialize import settings_out
from models.admin import SettingsIn

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings():
    doc = await db.settings.find_one({"id": "store"})
    return settings_out(doc or {})


@router.put("")
async def update_settings(input: SettingsIn, admin: dict = Depends(require_admin)):
    current = await db.settings.find_one({"id": "store"}) or {}
    reserved = int(current.get("robux_stock_reserved", 0))
    values = input.model_dump()
    reserved_expr = {"$ifNull": ["$robux_stock_reserved", 0]}
    if input.robux_stock is None:
        stock_guard = {"$eq": [reserved_expr, 0]}
    else:
        stock_guard = {"$lte": [reserved_expr, input.robux_stock]}
    updated = await db.settings.update_one(
        {"id": "store", "$expr": stock_guard},
        {"$set": values},
    )
    if not updated.matched_count:
        if current:
            reserved = int((await db.settings.find_one({"id": "store"}) or {}).get("robux_stock_reserved", reserved))
            if input.robux_stock is None:
                detail = "Selesaikan atau tolak pesanan yang sedang memakai stok sebelum menonaktifkan stok."
            else:
                detail = f"Stok tidak bisa diatur di bawah {reserved:,} Robux yang sedang dipesan.".replace(",", ".")
            raise HTTPException(status_code=409, detail=detail)
        await db.settings.insert_one({"id": "store", "robux_stock_reserved": 0, **values})
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": admin["id"],
        "admin_username": admin["username"],
        "action": "settings_update",
        "target": "store",
        "detail": None,
        "created_at": now(),
    })
    doc = await db.settings.find_one({"id": "store"})
    return settings_out(doc or {})


@router.post("/qris")
async def upload_qris(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    content = await file.read()
    try:
        fdoc = await save_proof(
            content, file.content_type,
            uploaded_by=admin["id"],
            ref_type="qris", ref_id="store", ref_code="qris",
            public=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.settings.update_one(
        {"id": "store"},
        {"$set": {"qris_image_file_id": fdoc["id"]}},
        upsert=True,
    )
    doc = await db.settings.find_one({"id": "store"})
    return settings_out(doc or {})


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    content = await file.read()
    try:
        fdoc = await save_proof(
            content, file.content_type,
            uploaded_by=admin["id"],
            ref_type="store_logo", ref_id="store", ref_code="logo",
            public=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.settings.update_one(
        {"id": "store"},
        {"$set": {"logo_file_id": fdoc["id"]}},
        upsert=True,
    )
    doc = await db.settings.find_one({"id": "store"})
    return settings_out(doc or {})
