"""Управление подключением к PostgreSQL. Атрошенко Б. С."""

import logging

import asyncpg

logger = logging.getLogger(__name__)


class DBManager:
    """Менеджер для работы с БД."""

    def __init__(self, dsn: str):
        """Инициализатор."""

        self.dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self) -> None:
        """Создание пула подключений"""

        self._pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=10)
        logger.info("DB pool initialized")

    async def close_pool(self) -> None:
        """Закрытие Connetion."""

        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Получить пул подключение."""

        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")
        return self._pool
