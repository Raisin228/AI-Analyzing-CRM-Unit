"""Управление подключением к Redis. Атрошенко Б. С."""

import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Класс для управления Redis."""

    def __init__(self, url: str):
        """Инициализатор."""

        self.url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        """Подключение."""

        self._client = Redis.from_url(self.url, decode_responses=False)
        logger.info("Redis connected")

    async def disconnect(self) -> None:
        """Отключение."""

        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> Redis:
        """Получить клиента."""

        if self._client is None:
            raise RuntimeError("Redis is not connected")

        return self._client
