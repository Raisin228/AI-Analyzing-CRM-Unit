"""Управление подключением к PostgreSQL. Атрошенко Б. С."""

import logging

import asyncpg

logger = logging.getLogger(__name__)


class DBManager:
    """Менеджер для работы с БД. Singleton."""

    _instance: "DBManager | None" = None

    def __new__(cls, dsn: str) -> "DBManager":
        """Конструктор."""

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.dsn = dsn
            cls._instance._pool = None
        return cls._instance

    @classmethod
    def get(cls) -> "DBManager":
        """Получить объект синглтона."""

        if cls._instance is None:
            raise RuntimeError("DBManager is not initialized")
        return cls._instance

    async def init_pool(self) -> None:
        """Создание пула подключений."""

        self._pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=10)
        logger.info("DB pool initialized")

    async def close_pool(self) -> None:
        """Закрытие пула подключений."""

        if self._pool:
            await self._pool.close()
            self._pool = None
            DBManager._instance = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Пул подключений для исполнения запросов."""

        if self._pool is None:
            raise RuntimeError("DB pool is not initialized")
        return self._pool
