"""Admin console: stats, order/topup verification with fake-payment detection,
package & pricing manager, user management, audit log. Every route requires admin."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from lib.ai_check import run_ai_check
from lib.db import db
from lib.dates import now
from lib.inventory import consume_robux, release_robux
from lib.uploads import read_upload
from lib.security import hash_password, require_admin
from lib.serialize import admin_user_out, order_out, package_out, topup_out
from lib.whatsapp import whatsapp_alert_status
from models.admin import AdjustCoinsIn, AdminLogOut, RejectIn, StatsOut, UserPasswordIn, UserRoleIn
from models.catalog import PackageIn

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/notification-status")
async def notification_status(_: dict = Depends(require_admin)):
    return whatsapp_alert_status()


async def audit(admin: dict, action: str, target: str, detail: str | None = None) -> None:
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": admin["id"],
        "admin_username": admin["username"],
        "action": action,
        "target": target,
        "detail": detail,
        "created_at": now(),
    })


@router.get("/stats", response_model=StatsOut)
async def stats(_: dict = Depends(require_admin)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    orders_pending = await db.orders.count_documents(
        {"status": {"$in": ["menunggu_pembayaran", "menunggu_verifikasi"]}}
    )
    orders_today = await db.orders.count_documents({"created_at": {"$gte": today_start}})
    topups_pending = await db.coin_topups.count_documents(
        {"status": {"$in": ["menunggu_pembayaran", "menunggu_verifikasi"]}}
    )
    users_count = await db.users.count_documents({})
    rev = await db.orders.aggregate([
        {"$match": {"status": {"$in": ["diproses", "selesai"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_idr"}, "robux": {"$sum": "$robux"}}},
    ]).to_list(1)
    coins = await db.users.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$coins"}}},
    ]).to_list(1)
    return StatsOut(
        orders_pending=orders_pending,
        orders_today=orders_today,
        topups_pending=topups_pending,
        users_count=users_count,
        revenue_idr=rev[0]["total"] if rev else 0,
        robux_sold=rev[0]["robux"] if rev else 0,
        coin_circulation=coins[0]["total"] if coins else 0,
    )


# ---------- orders ----------


@router.get("/orders")
async def list_orders(status: str | None = None, _: dict = Depends(require_admin)):
    if status == "pending":
        q = {"status": {"$in": ["menunggu_pembayaran", "menunggu_verifikasi"]}}
    elif status:
        q = {"status": status}
    else:
        q = {}
    docs = await db.orders.find(q).sort("created_at", -1).to_list(300)
    return [order_out(d) for d in docs]


async def _load_order(order_id: str) -> dict:
    doc = await db.orders.find_one({"id": order_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    return doc


@router.get("/orders/{order_id}")
async def get_order_admin(order_id: str, _: dict = Depends(require_admin)):
    return order_out(await _load_order(order_id))


@router.post("/orders/{order_id}/approve")
async def approve_order(order_id: str, admin: dict = Depends(require_admin)):
    doc = await _load_order(order_id)
    if doc["status"] != "menunggu_verifikasi":
        raise HTTPException(status_code=400, detail="Hanya pesanan yang menunggu verifikasi yang bisa disetujui")
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"status": "diproses", "processed_at": now(), "updated_at": now()}},
    )
    if doc.get("user_id"):
        from routers.community import notify
        await notify(doc["user_id"], "Pesanan mulai diproses", f"Pesanan {doc['code']} sudah diverifikasi dan sedang diproses.", "info")
    await audit(admin, "order_approve", doc["code"], f"{doc['robux']} Robux")
    return order_out(await _load_order(order_id))


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: str, admin: dict = Depends(require_admin)):
    doc = await _load_order(order_id)
    if doc["status"] != "diproses":
        raise HTTPException(status_code=400, detail="Hanya pesanan berstatus diproses yang bisa diselesaikan")
    reserved = bool(doc.get("stock_reserved"))
    updated = await db.orders.update_one(
        {"id": order_id, "status": "diproses"},
        {"$set": {"status": "selesai", "processed_at": now(), "updated_at": now(), "stock_reserved": False}},
    )
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="Status pesanan berubah. Muat ulang lalu coba lagi.")
    if reserved and not await consume_robux(doc["robux"]):
        await db.orders.update_one(
            {"id": order_id, "status": "selesai", "stock_reserved": False},
            {"$set": {"status": "diproses", "processed_at": doc.get("processed_at"), "updated_at": now(), "stock_reserved": True}},
        )
        raise HTTPException(status_code=409, detail="Stok yang dicadangkan tidak ditemukan. Periksa pengaturan stok sebelum menyelesaikan pesanan.")
    from routers.community import award_completed_order, notify
    completed = await _load_order(order_id)
    await award_completed_order(completed)
    if completed.get("user_id"):
        await notify(completed["user_id"], "Pesanan selesai", f"Pesanan {completed['code']} sudah selesai. Terima kasih sudah berbelanja di DeaStore!", "success")
    await audit(admin, "order_complete", doc["code"], f"{doc['robux']} Robux dikirim")
    return order_out(completed)


@router.post("/orders/{order_id}/reject")
async def reject_order(order_id: str, input: RejectIn, admin: dict = Depends(require_admin)):
    doc = await _load_order(order_id)
    if doc["status"] not in ("menunggu_verifikasi", "diproses"):
        raise HTTPException(status_code=400, detail="Pesanan ini tidak bisa ditolak")
    updated = await db.orders.update_one(
        {"id": order_id, "status": {"$in": ["menunggu_verifikasi", "diproses"]}},
        {"$set": {"status": "ditolak", "reject_reason": input.reason, "processed_at": now(), "updated_at": now(), "stock_reserved": False}},
    )
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="Status pesanan berubah. Muat ulang lalu coba lagi.")
    if doc.get("stock_reserved"):
        await release_robux(doc["robux"])
    refund_note = ""
    if doc["payment_method"] == "coin" and doc.get("total_coins"):
        # Coin orders were deducted at creation — refund on rejection.
        await db.users.update_one({"id": doc["user_id"]}, {"$inc": {"coins": doc["total_coins"]}})
        refund_note = f" (refund {doc['total_coins']} coin)"
    if doc.get("user_id"):
        from routers.community import notify
        await notify(doc["user_id"], "Pesanan ditolak", f"Pesanan {doc['code']} ditolak: {input.reason}", "warning")
    await audit(admin, "order_reject", doc["code"], f"{input.reason}{refund_note}")
    return order_out(await _load_order(order_id))


@router.delete("/orders/{order_id}")
async def delete_cancelled_order(order_id: str, admin: dict = Depends(require_admin)):
    """Remove only an unpaid or rejected order — never an active/paid order."""
    doc = await _load_order(order_id)
    if doc["status"] not in ("menunggu_pembayaran", "ditolak"):
        raise HTTPException(
            status_code=400,
            detail="Hanya pesanan belum dibayar atau yang sudah ditolak yang dapat dihapus.",
        )
    await db.orders.delete_one({"id": order_id, "status": {"$in": ["menunggu_pembayaran", "ditolak"]}})
    await audit(admin, "order_delete", doc["code"], f"Pesanan {doc['status']} dihapus")
    return {"ok": True}


@router.post("/orders/{order_id}/rescan")
async def rescan_order(order_id: str, background: BackgroundTasks, _: dict = Depends(require_admin)):
    doc = await _load_order(order_id)
    if not doc.get("proof_file_id"):
        raise HTTPException(status_code=400, detail="Pesanan belum punya bukti pembayaran")
    fdoc = await db.files.find_one({"id": doc["proof_file_id"]})
    if not fdoc:
        raise HTTPException(status_code=404, detail="File bukti tidak ditemukan")
    content = await read_upload(fdoc["filename"])
    if content is None:
        raise HTTPException(status_code=404, detail="File bukti tidak ada di penyimpanan")
    await db.orders.update_one({"id": order_id}, {"$set": {"ai_verdict": {"ai_status": "pending"}}})
    background.add_task(run_ai_check, "order", order_id, content, fdoc["mime"], doc["total_idr"])
    return order_out(await _load_order(order_id))


# ---------- coin top-ups ----------


@router.get("/topups")
async def list_topups(status: str | None = None, _: dict = Depends(require_admin)):
    if status == "pending":
        q = {"status": {"$in": ["menunggu_pembayaran", "menunggu_verifikasi"]}}
    elif status:
        q = {"status": status}
    else:
        q = {}
    docs = await db.coin_topups.find(q).sort("created_at", -1).to_list(300)
    return [topup_out(d) for d in docs]


@router.post("/topups/{topup_id}/approve")
async def approve_topup(topup_id: str, admin: dict = Depends(require_admin)):
    doc = await db.coin_topups.find_one({"id": topup_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Permintaan top-up tidak ditemukan")
    if doc["status"] != "menunggu_verifikasi":
        raise HTTPException(status_code=400, detail="Hanya top-up yang menunggu verifikasi yang bisa disetujui")
    await db.coin_topups.update_one({"id": topup_id}, {"$set": {"status": "disetujui", "processed_at": now()}})
    await db.users.update_one({"id": doc["user_id"]}, {"$inc": {"coins": doc["coins"]}})
    from routers.community import notify
    await notify(doc["user_id"], "Top-up coin disetujui", f"{doc['coins']} coin dari top-up {doc['code']} sudah masuk ke saldo.", "success")
    await audit(admin, "topup_approve", doc["code"], f"+{doc['coins']} coin")
    doc = await db.coin_topups.find_one({"id": topup_id})
    return topup_out(doc)


@router.post("/topups/{topup_id}/reject")
async def reject_topup(topup_id: str, input: RejectIn, admin: dict = Depends(require_admin)):
    doc = await db.coin_topups.find_one({"id": topup_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Permintaan top-up tidak ditemukan")
    if doc["status"] != "menunggu_verifikasi":
        raise HTTPException(status_code=400, detail="Top-up ini tidak bisa ditolak")
    await db.coin_topups.update_one(
        {"id": topup_id},
        {"$set": {"status": "ditolak", "reject_reason": input.reason, "processed_at": now()}},
    )
    from routers.community import notify
    await notify(doc["user_id"], "Top-up coin ditolak", f"Top-up {doc['code']} ditolak: {input.reason}", "warning")
    await audit(admin, "topup_reject", doc["code"], input.reason)
    doc = await db.coin_topups.find_one({"id": topup_id})
    return topup_out(doc)


@router.post("/topups/{topup_id}/rescan")
async def rescan_topup(topup_id: str, background: BackgroundTasks, _: dict = Depends(require_admin)):
    doc = await db.coin_topups.find_one({"id": topup_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Permintaan top-up tidak ditemukan")
    if not doc.get("proof_file_id"):
        raise HTTPException(status_code=400, detail="Top-up belum punya bukti pembayaran")
    fdoc = await db.files.find_one({"id": doc["proof_file_id"]})
    if not fdoc:
        raise HTTPException(status_code=404, detail="File bukti tidak ditemukan")
    content = await read_upload(fdoc["filename"])
    if content is None:
        raise HTTPException(status_code=404, detail="File bukti tidak ada di penyimpanan")
    await db.coin_topups.update_one({"id": topup_id}, {"$set": {"ai_verdict": {"ai_status": "pending"}}})
    background.add_task(run_ai_check, "topup", topup_id, content, fdoc["mime"], doc["amount_idr"])
    doc = await db.coin_topups.find_one({"id": topup_id})
    return topup_out(doc)


# ---------- packages ----------


@router.get("/packages")
async def admin_list_packages(_: dict = Depends(require_admin)):
    docs = await db.packages.find().sort("sort", 1).to_list(200)
    return [package_out(d) for d in docs]


@router.post("/packages")
async def create_package(input: PackageIn, admin: dict = Depends(require_admin)):
    if await db.packages.find_one({"robux": input.robux}):
        raise HTTPException(status_code=400, detail=f"Paket {input.robux} Robux sudah ada")
    doc = {"id": str(uuid.uuid4()), **input.model_dump()}
    await db.packages.insert_one(doc)
    await audit(admin, "package_create", f"{input.robux} robux", f"Rp{input.price_idr:,}".replace(",", "."))
    return package_out(doc)


@router.put("/packages/{package_id}")
async def update_package(package_id: str, input: PackageIn, admin: dict = Depends(require_admin)):
    doc = await db.packages.find_one({"id": package_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    await db.packages.update_one({"id": package_id}, {"$set": input.model_dump()})
    await audit(admin, "package_update", f"{input.robux} robux", f"harga baru Rp{input.price_idr:,}".replace(",", "."))
    doc = await db.packages.find_one({"id": package_id})
    return package_out(doc)


@router.delete("/packages/{package_id}")
async def delete_package(package_id: str, admin: dict = Depends(require_admin)):
    doc = await db.packages.find_one({"id": package_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    await db.packages.delete_one({"id": package_id})
    await audit(admin, "package_delete", f"{doc['robux']} robux", None)
    return {"ok": True}


# ---------- users ----------


@router.get("/users")
async def admin_list_users(_: dict = Depends(require_admin)):
    docs = await db.users.find({}, {"password_hash": 0}).sort("created_at", -1).to_list(500)
    return [admin_user_out(d) for d in docs]


@router.post("/users/{user_id}/adjust-coins")
async def adjust_coins(user_id: str, input: AdjustCoinsIn, admin: dict = Depends(require_admin)):
    if input.delta == 0:
        raise HTTPException(status_code=400, detail="Perubahan saldo tidak boleh 0")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    new_balance = user.get("coins", 0) + input.delta
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="Saldo akhir tidak boleh negatif")
    await db.users.update_one({"id": user_id}, {"$set": {"coins": new_balance}})
    await audit(admin, "coins_adjust", user["username"], f"{input.delta:+d} coin - {input.note or ''}")
    return admin_user_out(await db.users.find_one({"id": user_id}))


@router.post("/users/{user_id}/password")
async def change_user_password(user_id: str, input: UserPasswordIn, admin: dict = Depends(require_admin)):
    if len(input.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password maksimal 72 byte")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(input.password)}, "$inc": {"session_version": 1}},
    )
    await audit(admin, "user_password_change", user["username"], "Password diganti admin; sesi lama dicabut")
    return {"ok": True}


@router.post("/users/{user_id}/role")
async def change_user_role(user_id: str, input: UserRoleIn, admin: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")
    previous_role = user.get("role", "user")
    if user_id == admin["id"] and input.role != "admin":
        raise HTTPException(status_code=400, detail="Peran admin akun yang sedang dipakai tidak bisa diturunkan")
    if previous_role == "admin" and input.role == "user":
        remaining_admins = await db.users.count_documents({"role": "admin", "id": {"$ne": user_id}})
        if remaining_admins == 0:
            raise HTTPException(status_code=400, detail="Minimal harus ada satu akun admin")
    await db.users.update_one({"id": user_id}, {"$set": {"role": input.role}})
    await audit(admin, "user_role_change", user["username"], f"Peran {previous_role} → {input.role}")
    return admin_user_out(await db.users.find_one({"id": user_id}))


# ---------- audit log ----------


@router.get("/logs")
async def admin_logs(_: dict = Depends(require_admin)):
    docs = await db.admin_logs.find().sort("created_at", -1).to_list(30)
    return [
        AdminLogOut(
            id=d["id"],
            admin_username=d.get("admin_username", ""),
            action=d.get("action", ""),
            target=d.get("target", ""),
            detail=d.get("detail"),
            created_at=d["created_at"],
        )
        for d in docs
    ]
