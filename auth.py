"""Auth routes — httpOnly cookie sessions, all under /api/auth."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from lib.db import db
from lib.dates import now
from lib.security import (
    clear_session_cookie,
    create_session_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from lib.serialize import user_out
from models.auth import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
async def register(input: RegisterIn, response: Response):
    username_lower = input.username.lower()
    if await db.users.find_one({"username_lower": username_lower}):
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")

    referrer = None
    if input.referral_code:
        referrer = await db.users.find_one({"referral_code": input.referral_code.strip().upper()})
        if not referrer:
            raise HTTPException(status_code=400, detail="Kode referral tidak ditemukan")
    user = {
        "id": str(uuid.uuid4()),
        "username": input.username,
        "username_lower": username_lower,
        "password_hash": hash_password(input.password),
        "role": "user",
        "coins": 0,
        "reward_points": 0,
        "referral_code": uuid.uuid4().hex[:8].upper(),
        "referred_by": referrer["id"] if referrer else None,
        "session_version": 0,
        "created_at": now(),
    }
    await db.users.insert_one(user)
    set_session_cookie(response, create_session_token(user["id"], user["session_version"]))
    return user_out(user)


@router.post("/login", response_model=UserOut)
async def login(input: LoginIn, response: Response):
    user = await db.users.find_one({"username_lower": input.username.lower()})
    if not user or not verify_password(input.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    set_session_cookie(response, create_session_token(user["id"], user.get("session_version", 0)))
    return user_out(user)


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: dict | None = Depends(get_current_user)):
    return {"user": user_out(user) if user else None}
