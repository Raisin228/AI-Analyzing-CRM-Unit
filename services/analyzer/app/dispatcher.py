import logging
import uuid
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from .config import settings
from database.queries import dao

logger = logging.getLogger(__name__)


async def send_event(
    event_type: str,
    review_id: Optional[int],
    description: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    event_id = uuid.uuid4()
    metadata = metadata or {}

    if await dao.event_already_sent(event_id):
        return

    payload = {
        "event_type": event_type,
        "review_id": review_id or 0,
        "description": description,
        "metadata": metadata,
    }

    try:
        await _post_with_retry(payload)
    except Exception as exc:
        logger.error("Failed to dispatch event %s after retries: %s", event_type, exc)
        return

    await dao.insert_dispatched_event(
        event_id=event_id,
        event_type=event_type,
        review_id=review_id,
        description=description,
        metadata=metadata,
    )
    logger.info("Dispatched event type=%s review_id=%s", event_type, review_id)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def _post_with_retry(payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{settings.CRM_URL}/events", json=payload)
        resp.raise_for_status()
