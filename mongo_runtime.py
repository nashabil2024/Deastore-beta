"""Keep Mongo resources local to the running asyncio loop, never import time."""

import asyncio
from collections.abc import Callable
from threading import RLock
from typing import Any


class LoopMongoRuntime:
    def __init__(self, client_factory: Callable[[asyncio.AbstractEventLoop], Any], database_name: str):
        self._client_factory = client_factory
        self.database_name = database_name
        self._clients: dict[asyncio.AbstractEventLoop, Any] = {}
        self._lock = RLock()

    def get_client(self) -> Any:
        loop = asyncio.get_running_loop()
        with self._lock:
            # A cloud inspector can use and close a temporary loop before the
            # server starts. Do not retain its client or use its cached loop.
            for previous_loop in list(self._clients):
                if previous_loop.is_closed():
                    self._clients.pop(previous_loop).close()
            if loop not in self._clients:
                self._clients[loop] = self._client_factory(loop)
            return self._clients[loop]

    def get_database(self) -> Any:
        return self.get_client()[self.database_name]

    def close(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        with self._lock:
            if loop is None:
                clients = list(self._clients.values())
                self._clients.clear()
            else:
                current = self._clients.pop(loop, None)
                clients = [current] if current is not None else []
            for client in clients:
                client.close()


class MongoClientProxy:
    """Preserve existing imports while resolving the actual client lazily."""

    def __init__(self, runtime: LoopMongoRuntime):
        self._runtime = runtime

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime.get_client(), name)

    def __getitem__(self, name: str) -> Any:
        return self._runtime.get_client()[name]

    def close(self) -> None:
        self._runtime.close()


class MongoDatabaseProxy:
    def __init__(self, runtime: LoopMongoRuntime):
        self._runtime = runtime

    @property
    def name(self) -> str:
        return self._runtime.database_name

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime.get_database(), name)

    def __getitem__(self, name: str) -> Any:
        return self._runtime.get_database()[name]
