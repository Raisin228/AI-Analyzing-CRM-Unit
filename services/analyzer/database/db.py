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
            cls._instance.pool = None
        return cls._instance

    @classmethod
    def get(cls) -> "DBManager":
        """Получить объект синглтона."""

        if cls._instance is None:
            raise RuntimeError("DBManager is not initialized")
        return cls._instance

    @classmethod
    async def init_pool(cls) -> None:
        """Создание пула подключений."""

        cls._instance.pool = await asyncpg.create_pool(cls._instance.dsn, min_size=2, max_size=10)
        logger.info("DB pool initialized")

    @classmethod
    async def close_pool(cls) -> None:
        """Закрытие пула подключений."""

        if cls._instance.pool:
            await cls._instance.pool.close()
            cls._instance.pool = None
            cls._instance = None
