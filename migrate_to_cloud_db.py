"""Copy the current local MongoDB data and uploaded images to an empty cloud DB.

Run inside the app container after the cloud MongoDB cluster is ready:
    python migrate_to_cloud_db.py --confirm-empty-destination

The destination URI is requested with hidden input and is never printed.
Add --resume only if a previous migration stopped partway through.
"""

import argparse
import asyncio
import getpass
import io
import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from lib.db import db as source_db
from lib.uploads import UPLOAD_DIR


async def migrate(*, confirm: bool, resume: bool) -> None:
    if not confirm:
        raise SystemExit("Tambahkan --confirm-empty-destination setelah memastikan database cloud masih kosong.")

    destination_uri = os.environ.get("MONGO_DEST_URL", "").strip()
    if not destination_uri:
        destination_uri = getpass.getpass("URI database cloud (input disembunyikan): ").strip()
    if not destination_uri.startswith(("mongodb://", "mongodb+srv://")):
        raise SystemExit("URI MongoDB tidak valid.")

    destination_name = os.environ.get("DEST_DB_NAME", source_db.name)
    destination_client = AsyncIOMotorClient(destination_uri, serverSelectionTimeoutMS=15000)
    try:
        await destination_client.admin.command("ping")
        destination_db = destination_client[destination_name]
        collections = await source_db.list_collection_names()

        if not resume:
            existing = []
            for name in collections:
                if await destination_db[name].estimated_document_count() > 0:
                    existing.append(name)
            if existing:
                raise RuntimeError("Database tujuan tidak kosong. Gunakan database baru atau --resume hanya untuk salinan sebelumnya.")

        source_files = await source_db.files.find({}, {"filename": 1, "mime": 1}).to_list(10000)
        missing = [f["filename"] for f in source_files if not (UPLOAD_DIR / f["filename"]).is_file()]
        if missing:
            raise RuntimeError(f"Ada {len(missing)} berkas lokal yang tidak ditemukan; migrasi dibatalkan sebelum menyalin data.")

        for name in collections:
            source_collection = source_db[name]
            destination_collection = destination_db[name]
            cursor = source_collection.find({}).batch_size(250)
            batch = []
            copied = 0
            async for document in cursor:
                batch.append(document)
                if len(batch) == 250:
                    for item in batch:
                        await destination_collection.replace_one({"_id": item["_id"]}, item, upsert=True)
                    copied += len(batch)
                    batch.clear()
            if batch:
                for item in batch:
                    await destination_collection.replace_one({"_id": item["_id"]}, item, upsert=True)
                copied += len(batch)
            print(f"Koleksi {name}: {copied} dokumen dipindahkan")

        bucket = AsyncIOMotorGridFSBucket(destination_db, bucket_name="uploads")
        for file_doc in source_files:
            filename = file_doc["filename"]
            already_there = await destination_db["uploads.files"].find_one({"filename": filename}, {"_id": 1})
            if already_there:
                continue
            content = (UPLOAD_DIR / filename).read_bytes()
            await bucket.upload_from_stream(filename, io.BytesIO(content), metadata={"mime": file_doc.get("mime", "application/octet-stream")})
        print(f"Gambar bukti/QRIS: {len(source_files)} berkas tersimpan")
        print("Salinan cloud selesai. Database lokal tetap tidak diubah.")
    finally:
        destination_client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-empty-destination", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(migrate(confirm=args.confirm_empty_destination, resume=args.resume))


if __name__ == "__main__":
    main()
