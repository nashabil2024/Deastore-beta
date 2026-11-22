"""Local or MongoDB GridFS storage for uploaded proof and QRIS images."""

import io
import os
from pathlib import Path

from gridfs.errors import NoFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from lib.db import get_database

UPLOAD_STORAGE = os.environ.get("UPLOAD_STORAGE", "local").strip().lower()
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(__file__).resolve().parent.parent / "uploads"))


def _get_bucket():
    # GridFS asks Motor for its loop when constructed. Build it inside the
    # current request, not while a cloud inspector is importing the app.
    return AsyncIOMotorGridFSBucket(get_database(), bucket_name="uploads")


async def store_upload(filename: str, content: bytes, mime: str) -> None:
    if UPLOAD_STORAGE == "gridfs":
        await _get_bucket().upload_from_stream(filename, io.BytesIO(content), metadata={"mime": mime})
        return
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / filename).write_bytes(content)


async def read_upload(filename: str) -> bytes | None:
    if UPLOAD_STORAGE == "gridfs":
        try:
            stream = await _get_bucket().open_download_stream_by_name(filename)
        except NoFile:
            return None
        return await stream.read()
    path = UPLOAD_DIR / filename
    if not path.is_file():
        return None
    return path.read_bytes()
