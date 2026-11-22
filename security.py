"""Sessions, password hashing and auth dependencies.

Sessions are httpOnly JWT cookies (7 days). The principal is re-derived from the
DB on every request so a role change takes effect immediately — never from baked
token claims. Roles: "user" | "admin".
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response
from passlib.context import CryptContext

from lib.db import db

SESSION_COOKIE = "dea_session"
SESSION_TTL_DAYS = 7
SECRET = os.environ.get("SESSION_SECRET", "")
if len(SECRET) < 32:
    raise RuntimeError("SESSION_SECRET wajib diatur dengan nilai acak minimal 32 karakter")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except Exception:
        return False


def create_session_token(user_id: str, session_version: int = 0) -> str:
    payload = {
        "sub": user_id,
        "ver": session_version,
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=SESSION_TTL_DAYS * 24 * 3600,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


async def get_current_user(request: Request) -> dict | None:
    """Return the user doc for the session cookie, or None for anonymous."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    user = await db.users.find_one({"id": payload.get("sub")})
    if not user or payload.get("ver", 0) != user.get("session_version", 0):
        return None
    return user


async def require_user(user: dict | None = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu")
    return user


async def require_admin(user: dict | None = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Akses khusus admin")
    return user
