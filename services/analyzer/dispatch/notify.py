"""Отправить событие из Analyzer в CRM. Атрошенко Б. С."""

import logging
import uuid
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from analyzer.app.config import settings
from analyzer.database import DAO

logger = logging.getLogger(__name__)


class Notifier:

    @staticmethod
    async def send_event(
            event_type: str,
            review_id: Optional[str],
            description: str,
            metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Отправить событие в CRM'ку.

        :param event_type: тип события.
        :param review_id: ID отзыва.
        :param description: Краткое описание отзыва.
        :param metadata: степень уверенности классификации.
        :return:
        """

        event_id = uuid.uuid4()
        metadata = metadata or {}

        payload = {
            "event_type": event_type,
            "review_id": review_id,
            "description": description,
            "metadata": metadata,
        }

        try:
            await Notifier._post_with_retry(payload)
        except Exception as exc:
            logger.error("Failed to dispatch event %s after retries: %s", event_type, exc)
            return

        await DAO.insert_dispatched_event(
            event_id=event_id,
            event_type=event_type,
            review_id=review_id,
            description=description,
            metadata=metadata,
        )
        logger.info("Dispatched event type=%s review_id=%s", event_type, review_id)

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _post_with_retry(payload: dict) -> None:
        """
        Закидываю событие в CRMку по API.

        :param payload: данные для фиксации события.
        :return:
        """
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{settings.CRM_URL}/events", json=payload)
            resp.raise_for_status()
