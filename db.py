"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

from lib.mongo_config import resolve_mongo_config
from lib.mongo_runtime import LoopMongoRuntime, MongoClientProxy, MongoDatabaseProxy

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url, _mongo_options = resolve_mongo_config(os.environ)
_runtime = LoopMongoRuntime(
    lambda loop: AsyncIOMotorClient(mongo_url, io_loop=loop, **_mongo_options),
    os.environ["DB_NAME"],
)
client = MongoClientProxy(_runtime)
db = MongoDatabaseProxy(_runtime)


def get_database():
    """Return the real Motor database for APIs such as GridFS that require it."""
    return _runtime.get_database()

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "status_checks": [IndexModel([("timestamp", DESCENDING)], name="timestamp_desc")],
    "users": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("username_lower", ASCENDING)], name="username_lower", unique=True),
        IndexModel([("referral_code", ASCENDING)], name="referral_code", unique=True, sparse=True),
    ],
    "orders": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("code", ASCENDING)], name="code", unique=True),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
    ],
    "coin_topups": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("code", ASCENDING)], name="code", unique=True),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
    ],
    "packages": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("sort", ASCENDING)], name="sort"),
    ],
    "files": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("md5", ASCENDING)], name="md5"),
        IndexModel([("phash", ASCENDING)], name="phash"),
        IndexModel([("ref_code", ASCENDING)], name="ref_code"),
    ],
    "roblox_cache": [
        IndexModel([("username", ASCENDING)], name="username", unique=True),
    ],
    "admin_logs": [IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "customer_notifications": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")],
    "giveaway_entries": [IndexModel([("giveaway_id", ASCENDING), ("user_id", ASCENDING)], name="giveaway_user", unique=True)],
    "rewarded_orders": [IndexModel([("order_id", ASCENDING)], name="order_id", unique=True)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)
