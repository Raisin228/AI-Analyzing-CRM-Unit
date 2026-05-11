"""Управление подключением к Redis. Атрошенко Б. С."""

import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Класс для управления Redis."""

    _instance: "RedisManager | None" = None

    def __new__(cls, url: str) -> "RedisManager":
        """Конструктор."""

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.url = url
            cls._instance.client = None
        return cls._instance

    @classmethod
    def get(cls) -> "RedisManager":
        """Получить объект синглтона."""

        if cls._instance is None:
            raise RuntimeError("RedisManager is not initialized")
        return cls._instance

    @classmethod
    async def connect(cls) -> None:
        """Подключение."""

        cls._instance.client = Redis.from_url(cls._instance.url, decode_responses=False)
        logger.info("Redis connected")

    @classmethod
    async def disconnect(cls) -> None:
        """Отключение."""

        if cls._instance.client:
            await cls._instance.client.close()
            cls._instance.client = None
            cls._instance = None
