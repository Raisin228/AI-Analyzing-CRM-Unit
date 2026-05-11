import json
import logging
from typing import Optional

import httpx
from aiokafka import AIOKafkaProducer

from .config import settings
from ..redis_service import RedisManager

logger = logging.getLogger(__name__)

_producer: Optional[AIOKafkaProducer] = None
_CURSOR_KEY = "crm:last_cursor"


async def init_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
    await _producer.start()
    logger.info("Kafka producer started")


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()


async def poll_crm() -> None:
    redis = redis_service.client()
    cursor: Optional[str] = None
    if redis:
        raw = await redis.get(_CURSOR_KEY)
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
        await _producer.send_and_wait(settings.KAFKA_TOPIC, value=value)

    max_created = max(r["created_at"] for r in reviews)
    if redis:
        await redis.set(_CURSOR_KEY, max_created)
