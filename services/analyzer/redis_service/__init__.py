"""Менеджер для работы с Redis. Атрошенко Б. С."""

from redis.asyncio import Redis

from analyzer.app.config import settings


class RedisManager:
    def __init__(self, url: str):
        self.url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        self._client = Redis.from_url(self.url, decode_responses=False)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> Redis | None:
        return self._client


redis_manager = RedisManager(settings.REDIS_URL)
