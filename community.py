"""DeaStore loyalty, referral, voucher, giveaway and customer notifications."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lib.db import db
from lib.dates import now
from lib.security import require_admin, require_user

router = APIRouter(prefix="/community", tags=["community"])


def tier_for(points: int) -> dict:
    if points >= 5000:
        return {"name": "Gold", "next": None, "minimum": 5000}
    if points >= 1500:
        return {"name": "Silver", "next": "Gold", "minimum": 5000}
    return {"name": "Bronze", "next": "Silver", "minimum": 1500}


async def notify(user_id: str, title: str, message: str, kind: str = "info") -> None:
    await db.customer_notifications.insert_one({
        "id": str(uuid.uuid4()), "user_id": user_id, "title": title,
        "message": message, "kind": kind, "read": False, "created_at": now(),
    })


async def award_completed_order(order: dict) -> None:
    """Idempotently award loyalty points and referral bonus after an order completes."""
    if not order.get("user_id"):
        return
    try:
        await db.rewarded_orders.insert_one({"order_id": order["id"], "user_id": order["user_id"], "created_at": now()})
    except Exception:
        return
    buyer = await db.users.find_one({"id": order["user_id"]})
    current_tier = tier_for(int((buyer or {}).get("reward_points", 0)))["name"]
    multiplier = 1.25 if current_tier == "Gold" else 1.10 if current_tier == "Silver" else 1.0
    points = max(1, int((int(order.get("total_idr", 0)) // 10000) * multiplier))
    await db.users.update_one({"id": order["user_id"]}, {"$inc": {"reward_points": points}})
    await notify(order["user_id"], "DeaPoints bertambah", f"Kamu mendapat {points} DeaPoints dari pesanan {order['code']}.", "success")
    buyer = await db.users.find_one({"id": order["user_id"]})
    referrer_id = buyer.get("referred_by") if buyer else None
    if referrer_id:
        first_done = await db.rewarded_orders.count_documents({"user_id": order["user_id"]})
        # Only the first completed order of a referred member earns referral bonus.
        if first_done == 1:
            await db.users.update_one({"id": referrer_id}, {"$inc": {"reward_points": 100}})
            await notify(referrer_id, "Bonus referral diterima", f"Teman yang kamu undang menyelesaikan pesanan pertama. Kamu mendapat 100 DeaPoints.", "success")


class VoucherIn(BaseModel):
    code: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    kind: str = Field(default="percent", pattern=r"^(percent|fixed)$")
    value: int = Field(gt=0, le=100000000)
    min_order: int = Field(default=0, ge=0)
    max_uses: int | None = Field(default=None, ge=1)
    active: bool = True
    expires_at: str | None = None


class GiveawayIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=1000)
    prize: str = Field(min_length=2, max_length=120)
    ends_at: str | None = None
    active: bool = True


@router.get("/me")
async def community_me(user: dict = Depends(require_user)):
    fresh = await db.users.find_one({"id": user["id"]}) or user
    points = int(fresh.get("reward_points", 0))
    tier = tier_for(points)
    referral_code = fresh.get("referral_code")
    if not referral_code:
        referral_code = uuid.uuid4().hex[:8].upper()
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": referral_code}})
    referrals = await db.users.count_documents({"referred_by": user["id"]})
    notifications = await db.customer_notifications.find({"user_id": user["id"]}).sort("created_at", -1).to_list(30)
    joined = await db.giveaway_entries.find({"user_id": user["id"]}).to_list(100)
    return {
        "reward_points": points, "tier": tier, "referral_code": referral_code,
        "referral_count": referrals,
        "unread_notifications": sum(1 for n in notifications if not n.get("read")),
        "notifications": [{"id": n["id"], "title": n["title"], "message": n["message"], "kind": n.get("kind", "info"), "read": n.get("read", False), "created_at": n["created_at"]} for n in notifications],
        "joined_giveaways": [e["giveaway_id"] for e in joined],
    }


@router.get("/vouchers")
async def active_vouchers():
    docs = await db.vouchers.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(50)
    current = now().isoformat()
    return [{"code": d["code"], "kind": d["kind"], "value": d["value"], "min_order": d.get("min_order", 0), "expires_at": d.get("expires_at")} for d in docs if (not d.get("expires_at") or str(d["expires_at"]) >= current) and (d.get("max_uses") is None or int(d.get("uses", 0)) < int(d["max_uses"]))]


@router.get("/giveaways")
async def active_giveaways():
    docs = await db.giveaways.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [{"id": d["id"], "title": d["title"], "description": d.get("description", ""), "prize": d["prize"], "ends_at": d.get("ends_at"), "participants": await db.giveaway_entries.count_documents({"giveaway_id": d["id"]})} for d in docs]


@router.post("/giveaways/{giveaway_id}/join")
async def join_giveaway(giveaway_id: str, user: dict = Depends(require_user)):
    giveaway = await db.giveaways.find_one({"id": giveaway_id, "active": True})
    if not giveaway:
        raise HTTPException(status_code=404, detail="Giveaway tidak tersedia")
    if giveaway.get("ends_at") and str(giveaway["ends_at"]) < now().isoformat():
        raise HTTPException(status_code=400, detail="Giveaway sudah berakhir")
    existing = await db.giveaway_entries.find_one({"giveaway_id": giveaway_id, "user_id": user["id"]})
    if existing:
        return {"ok": True, "message": "Kamu sudah terdaftar di giveaway ini."}
    await db.giveaway_entries.insert_one({"id": str(uuid.uuid4()), "giveaway_id": giveaway_id, "user_id": user["id"], "created_at": now()})
    await notify(user["id"], "Berhasil ikut giveaway", f"Kamu terdaftar pada giveaway {giveaway['title']}.", "success")
    return {"ok": True, "message": "Berhasil mengikuti giveaway!"}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(require_user)):
    await db.customer_notifications.update_one({"id": notification_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"ok": True}


@router.get("/admin/vouchers")
async def admin_vouchers(_: dict = Depends(require_admin)):
    return await db.vouchers.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/admin/vouchers")
async def create_voucher(input: VoucherIn, _: dict = Depends(require_admin)):
    code = input.code.upper()
    if await db.vouchers.find_one({"code": code}):
        raise HTTPException(status_code=409, detail="Kode voucher sudah digunakan")
    if input.kind == "percent" and input.value > 100:
        raise HTTPException(status_code=400, detail="Diskon persentase maksimal 100")
    doc = {"id": str(uuid.uuid4()), **input.model_dump(), "code": code, "uses": 0, "created_at": now()}
    await db.vouchers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/admin/vouchers/{voucher_id}")
async def toggle_voucher(voucher_id: str, active: bool, _: dict = Depends(require_admin)):
    result = await db.vouchers.update_one({"id": voucher_id}, {"$set": {"active": active}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Voucher tidak ditemukan")
    return {"ok": True}


@router.get("/admin/giveaways")
async def admin_giveaways(_: dict = Depends(require_admin)):
    return await db.giveaways.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/admin/giveaways")
async def create_giveaway(input: GiveawayIn, _: dict = Depends(require_admin)):
    doc = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": now()}
    await db.giveaways.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/admin/giveaways/{giveaway_id}")
async def toggle_giveaway(giveaway_id: str, active: bool, _: dict = Depends(require_admin)):
    result = await db.giveaways.update_one({"id": giveaway_id}, {"$set": {"active": active}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Giveaway tidak ditemukan")
    return {"ok": True}
