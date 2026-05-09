"""API endpointы CRMки. Атрошенко Б. С."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from .. import state
from ..models import Product, IncomingEvent, EventAcceptanceStatus, OrgUnit, UnitHealth, Review
from ..state import org_units, products, reviews, events

router = APIRouter(tags=["AmoCRM Mock"])
logger = logging.getLogger(__name__)


@router.post("/events", status_code=201, response_model=EventAcceptanceStatus)
async def post_event(event: IncomingEvent):
    """Принять некоторое событие от анализатора на обработку."""

    events.append(event)
    logger.info("[CRM Unit] Event received: type=%s review_id=%s", event.event_type, event.review_id)
    return EventAcceptanceStatus(**{"status": "Accepted"})


@router.get("/org", response_model=list[OrgUnit])
async def get_org() -> list[OrgUnit]:
    """Получить список ответственных бизнес юнитов внутри CRM."""

    return org_units


@router.get("/products", response_model=list[Product])
async def get_products() -> list[Product]:
    """Список товаров, имеющихся в CRM."""

    return products


@router.get("/reviews", response_model=list[Review])
async def get_reviews(
        since: datetime | None = Query(default=None),
        limit: int = Query(default=50, le=200),
):
    """Пачка отзывов."""

    result = reviews
    if since is not None:
        since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        result = [r for r in result if r.created_at > since_aware]
    return result[:limit]


@router.get("/health", response_model=UnitHealth)
async def health() -> UnitHealth:
    """Проверка состояния сервиса."""

    return UnitHealth(**{"status": "ok", "reviews": len(state.reviews), "events": len(state.events)})


@router.get("/events", response_model=list[IncomingEvent])
async def list_events() -> list[IncomingEvent]:
    """Список уже полученных событий от Analyze модуля."""

    return events
