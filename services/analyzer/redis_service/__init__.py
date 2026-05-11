"""Управление подключением к Redis."""

import logging
from typing import Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self, url: str):
        self.url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        self._client = Redis.from_url(self.url, decode_responses=False)
        logger.info("Redis connected")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> Redis | None:
        return self._client


_manager: Optional[RedisManager] = None


async def connect(url: str) -> None:
    global _manager
    _manager = RedisManager(url)
    await _manager.connect()


async def disconnect() -> None:
    global _manager
    if _manager:
        await _manager.disconnect()
        _manager = None


def client() -> Redis | None:
    return _manager.client if _manager else None
