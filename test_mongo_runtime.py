"""Loop-lifecycle regression tests with a loop-bound fake driver, no database."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from lib.mongo_runtime import LoopMongoRuntime, MongoClientProxy, MongoDatabaseProxy


class FakeDatabase:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def command(self, name, **kwargs):
        return self.client.future({"ok": 1})

    def __getattr__(self, name):
        return FakeCollection(self.client)

    def __getitem__(self, name):
        return FakeCollection(self.client)


class FakeCollection:
    def __init__(self, client):
        self.client = client

    def find_one(self, query):
        return self.client.future({"id": "fixture"})


class FakeClient:
    def __init__(self, loop):
        self.loop = loop
        self.closed = False

    def __getitem__(self, name):
        return FakeDatabase(self, name)

    def future(self, value):
        if self.closed:
            raise RuntimeError("Client is closed")
        future = self.loop.create_future()
        self.loop.call_soon(future.set_result, value)
        return future

    def close(self):
        self.closed = True


class MongoRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.created = []

        def factory(loop):
            client = FakeClient(loop)
            self.created.append(client)
            return client

        self.runtime = LoopMongoRuntime(factory, "fixture-db")
        self.db = MongoDatabaseProxy(self.runtime)
        self.client = MongoClientProxy(self.runtime)

    def tearDown(self):
        self.runtime.close()

    async def read_database(self):
        self.assertEqual(await self.db.command("ping"), {"ok": 1})
        self.assertEqual(await self.db.users.find_one({}), {"id": "fixture"})
        self.assertEqual(await self.db["users"].find_one({}), {"id": "fixture"})
        return self.runtime.get_client()

    def test_import_and_metadata_do_not_create_a_client(self):
        self.assertEqual(self.db.name, "fixture-db")
        self.assertEqual(self.created, [])
        with self.assertRaisesRegex(RuntimeError, "no running event loop"):
            self.runtime.get_database()
        self.assertEqual(self.created, [])

    def test_two_asyncio_run_loops_never_share_a_bound_client(self):
        first = asyncio.run(self.read_database())
        second = asyncio.run(self.read_database())
        self.assertIsNot(first, second)
        self.assertTrue(first.closed)
        self.assertIsNot(first.loop, second.loop)
        self.assertEqual(len(self.created), 2)

    def test_requests_in_one_loop_reuse_the_client(self):
        async def run():
            first = await self.read_database()
            second = await self.read_database()
            self.assertIs(first, second)

        asyncio.run(run())
        self.assertEqual(len(self.created), 1)

    def test_lifespan_shutdown_allows_restart_in_the_same_loop(self):
        async def run():
            first = await self.read_database()
            self.client.close()
            self.assertTrue(first.closed)
            second = await self.read_database()
            self.assertIsNot(first, second)

        asyncio.run(run())

    def test_closing_an_unused_runtime_creates_nothing(self):
        self.client.close()
        self.assertEqual(self.created, [])

    def test_gridfs_import_is_lazy_and_uploads_work_across_loops(self):
        stored = {}
        buckets = []

        class FakeNoFile(Exception):
            pass

        class FakeBucket:
            def __init__(bucket, database, bucket_name):
                # Real Motor GridFS resolves its client's loop here as well.
                self.assertIs(database.client.loop, asyncio.get_running_loop())
                bucket.client = database.client
                buckets.append(bucket)

            def upload_from_stream(bucket, filename, stream, metadata):
                stored[filename] = stream.read()
                return bucket.client.future(None)

            def open_download_stream_by_name(bucket, filename):
                class Stream:
                    def read(stream):
                        return bucket.client.future(stored[filename])

                return bucket.client.future(Stream())

        fake_modules = {
            "gridfs.errors": types.SimpleNamespace(NoFile=FakeNoFile),
            "motor.motor_asyncio": types.SimpleNamespace(AsyncIOMotorGridFSBucket=FakeBucket),
            "lib.db": types.SimpleNamespace(get_database=self.runtime.get_database),
        }
        spec = importlib.util.spec_from_file_location("fixture_uploads", BACKEND / "lib/uploads.py")
        uploads = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, fake_modules):
            spec.loader.exec_module(uploads)
        uploads.UPLOAD_STORAGE = "gridfs"
        self.assertEqual(buckets, [])
        self.assertEqual(self.created, [])
        asyncio.run(uploads.store_upload("fixture.png", b"fixture-image", "image/png"))
        self.assertEqual(asyncio.run(uploads.read_upload("fixture.png")), b"fixture-image")
        self.assertEqual(len(buckets), 2)
        self.assertIsNot(buckets[0].client, buckets[1].client)


class RealMotorRuntimeTests(unittest.TestCase):
    """Optional real-driver smoke; connect=False means no Mongo server needed."""

    def test_real_motor_database_and_gridfs_are_local_to_each_loop(self):
        try:
            from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
        except ImportError:
            self.skipTest("Optional Motor dependencies are not installed")

        created = []

        def factory(loop):
            client = AsyncIOMotorClient("mongodb://localhost:27017", io_loop=loop, connect=False)
            created.append(client)
            return client

        runtime = LoopMongoRuntime(factory, "fixture-db")
        proxy = MongoDatabaseProxy(runtime)
        self.assertEqual(created, [])
        self.assertEqual(proxy.name, "fixture-db")
        self.assertEqual(created, [])

        async def inspect():
            database = runtime.get_database()
            self.assertIsInstance(database, AsyncIOMotorDatabase)
            self.assertIs(database.client.get_io_loop(), asyncio.get_running_loop())
            bucket = AsyncIOMotorGridFSBucket(database, bucket_name="uploads")
            self.assertIs(bucket.get_io_loop(), asyncio.get_running_loop())
            self.assertIs(proxy.users.database.client, database.client)
            return database.client

        try:
            first = asyncio.run(inspect())
            second = asyncio.run(inspect())
            self.assertIsNot(first, second)
            self.assertEqual(len(created), 2)
        finally:
            runtime.close()


if __name__ == "__main__":
    unittest.main()
