"""Пулер для опросов CRMки. Атрошенко Б. С."""

import json
import logging
from typing import Optional

import httpx
from aiokafka import AIOKafkaProducer

from ..app.config import settings
from ..redis_service import RedisManager

logger = logging.getLogger(__name__)

_CURSOR_KEY = "crm:last_cursor"


class KafkaManager:
    """Кафка манагер."""

    _producer = None

    def __new__(cls, kafka_host: str) -> "KafkaManager":
        """Конструктор."""

        if cls._producer is None:
            cls._producer = super().__new__(cls)
            cls._producer.host = kafka_host
        return cls._producer

    @classmethod
    async def init_producer(cls) -> None:
        """Инициализатор Продюсера."""

        cls._producer = AIOKafkaProducer(bootstrap_servers=cls._producer.host)
        await cls._producer.start()
        logger.info("Kafka producer started")

    @classmethod
    async def close_producer(cls) -> None:
        """Закрыть Продюсера."""

        if cls._producer:
            await cls._producer.stop()

    @classmethod
    async def poll_crm(cls) -> None:
        """Опрашиваем CRMку при помощи курсора, который хранится в Redis."""

        cursor: Optional[str] = None
        if RedisManager.get().client:
            raw = await RedisManager.get().client.get(_CURSOR_KEY)
            if raw:
                cursor = raw.decode()

        params: dict = {"limit": 50}
        if cursor:
            params["since"] = cursor

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{settings.CRM_URL}/reviews", params=params)
                resp.raise_for_status()
                reviews = resp.json()
        except Exception as exc:
            logger.error("CRM poll failed: %s", exc)
            return

        if not reviews:
            return

        logger.info("Polled %d new reviews from CRM", len(reviews))

        for review in reviews:
            value = json.dumps(review, default=str).encode()
            await cls._producer.send_and_wait(settings.KAFKA_TOPIC, value=value)

        max_created = max(r["created_at"] for r in reviews)
        if RedisManager.get().client:
            await RedisManager.get().client.set(_CURSOR_KEY, max_created)
