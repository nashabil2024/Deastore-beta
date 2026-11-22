"""Payment-proof uploads: disk storage + md5/perceptual hashing + duplicate (fake) detection.

A proof is "fake-suspect" when the exact same bytes were already used on another
order/topup, or when a perceptually near-identical image (aHash 64-bit, distance <= 6)
was uploaded before — the classic recycled-screenshot fraud.
"""

import hashlib
import io
import uuid

from PIL import Image

from lib.db import db
from lib.dates import now
from lib.uploads import store_upload

ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 5 * 1024 * 1024
PHASH_DISTANCE = 6


def ahash(content: bytes) -> str | None:
    """64-bit average hash as 16 hex chars; None when the bytes are not a decodable image."""
    try:
        img = Image.open(io.BytesIO(content)).convert("L").resize((8, 8), Image.LANCZOS)
        px = list(img.getdata())
        avg = sum(px) / len(px)
        bits = "".join("1" if p > avg else "0" for p in px)
        return f"{int(bits, 2):016x}"
    except Exception:
        return None


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


async def save_proof(
    content: bytes,
    mime: str | None,
    *,
    uploaded_by: str | None,
    ref_type: str,
    ref_id: str,
    ref_code: str,
    public: bool = False,
) -> dict:
    """Validate + store one image; returns the files doc. Raises ValueError on bad input."""
    if mime not in ALLOWED_MIME:
        raise ValueError("Format bukti harus JPG, PNG, atau WebP")
    if len(content) == 0:
        raise ValueError("File kosong")
    if len(content) > MAX_BYTES:
        raise ValueError("Ukuran file maksimal 5MB")

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ALLOWED_MIME[mime]}"
    await store_upload(filename, content, mime)

    doc = {
        "id": file_id,
        "filename": filename,
        "mime": mime,
        "size": len(content),
        "md5": hashlib.md5(content).hexdigest(),
        "phash": ahash(content),
        "uploaded_by": uploaded_by,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "ref_code": ref_code,
        "public": public,
        "created_at": now(),
    }
    await db.files.insert_one(doc)
    return doc


async def find_duplicates(md5: str, phash: str | None, exclude_file_id: str) -> list[dict]:
    """Flags referencing earlier private uploads with identical or near-identical content."""
    flags: list[dict] = []
    exact = await db.files.find({
        "md5": md5,
        "id": {"$ne": exclude_file_id},
        "public": {"$ne": True},
    }).to_list(3)
    for f in exact:
        flags.append({"kind": "exact", "ref_type": f.get("ref_type"), "ref_code": f.get("ref_code")})

    if phash and not flags:
        candidates = await db.files.find({
            "phash": {"$nin": [None, ""]},
            "id": {"$ne": exclude_file_id},
            "public": {"$ne": True},
        }).to_list(1000)
        for f in candidates:
            if f.get("phash") and hamming(phash, f["phash"]) <= PHASH_DISTANCE:
                flags.append({"kind": "similar", "ref_type": f.get("ref_type"), "ref_code": f.get("ref_code")})
                if len(flags) >= 3:
                    break
    return flags
