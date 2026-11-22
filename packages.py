"""Public Robux package catalogue."""

from fastapi import APIRouter

from lib.db import db
from lib.serialize import package_out

router = APIRouter(tags=["packages"])


@router.get("/packages")
async def list_packages():
    docs = await db.packages.find({"active": True}).sort("sort", 1).to_list(200)
    return [package_out(d) for d in docs]
