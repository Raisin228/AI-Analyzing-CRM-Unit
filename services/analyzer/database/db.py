"""Управление подключением к PostgreSQL."""

import logging

import asyncpg

from analyzer.app.config import settings

logger = logging.getLogger(__name__)


class DBManager:
    """Управление БД."""

    def __init__(self, dsn: str):
        """Инициализатор."""

        self.dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self) -> None:
        """Подключение к БД."""

        self._pool = asyncpg.create_pool(self.dsn, min_size=2, max_size=10)
        logger.info("DB pool initialized")

    async def close_pool(self) -> None:
        """Закрытие подключения к БД."""

        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Получить пул."""

        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")
        return self._pool


database = DBManager(settings.database_url)
