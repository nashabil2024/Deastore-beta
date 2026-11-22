"""Serve uploaded files (payment proofs, QRIS image).

Public files (store QRIS) are open. Proofs require admin, the uploader's session,
or the owning order/topup code as ?code= (guest tracking).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from lib.db import db
from lib.security import get_current_user
from lib.uploads import read_upload

router = APIRouter(tags=["files"])


@router.get("/files/{file_id}")
async def get_file(file_id: str, code: str | None = None, user: dict | None = Depends(get_current_user)):
    f = await db.files.find_one({"id": file_id})
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    if not f.get("public"):
        is_admin = bool(user) and user.get("role") == "admin"
        is_owner = bool(user) and f.get("uploaded_by") == user["id"]
        has_code = bool(code) and code.upper().strip() == f.get("ref_code")
        if not (is_admin or is_owner or has_code):
            raise HTTPException(status_code=403, detail="Tidak ada akses ke file ini")

    content = await read_upload(f["filename"])
    if content is None:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return Response(content=content, media_type=f["mime"])
