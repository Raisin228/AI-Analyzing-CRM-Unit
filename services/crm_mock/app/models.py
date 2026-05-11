"""Модельки ответа и запроса данных для CRM mock модуля. Атрошенко Б. С."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class EventType(str, Enum):
    """Возможные типы для событий."""

    critical_negative = "critical_negative"
    sentiment_mismatch = "sentiment_mismatch"
    recurring_issue = "recurring_issue"
    volume_anomaly = "volume_anomaly"
    topic_shift = "topic_shift"


class Review(BaseModel):
    """Формат одного возможного отзыва."""

    id: UUID
    customer_name: str
    text: str
    rating: int
    created_at: datetime
    product_id: UUID
    is_processed: bool = False


class Product(BaseModel):
    """Товары имеющиеся в CRM."""

    id: UUID
    name: str
    category: str


class OrgUnit(BaseModel):
    """Структура для одного бизнес юнита внутри CRM."""

    id: UUID
    name: str
    responsible_email: str


class IncomingEvent(BaseModel):
    """События, которые возможно принять в CRM."""

    event_type: EventType
    review_id: Optional[UUID] = None
    description: str


class EventAcceptanceStatus(BaseModel):
    """Событие успешно получено."""

    status: Literal["Accepted", "Declined"]


class UnitHealth(BaseModel):
    """Состояние БЮ."""

    status: Literal["ok"]
    reviews: int
    events: int
