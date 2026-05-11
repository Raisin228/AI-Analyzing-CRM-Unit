"""Управление подключением к PostgreSQL."""

import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self) -> None:
        self._pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=10)
        logger.info("DB pool initialized")

    async def close_pool(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")
        return self._pool


_manager: Optional[DBManager] = None


async def init_db(dsn: str) -> None:
    global _manager
    _manager = DBManager(dsn)
    await _manager.init_pool()


async def close_db() -> None:
    global _manager
    if _manager:
        await _manager.close_pool()
        _manager = None


def pool() -> asyncpg.Pool:
    if _manager is None:
        raise RuntimeError("DB is not initialized")
    return _manager.pool
