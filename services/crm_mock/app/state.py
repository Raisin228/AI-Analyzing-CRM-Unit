"""Импровизированное хранилище состояний [Отзывы, события, продукты, структура организации]. Атрошенко Б. С."""

from .models import IncomingEvent, Review
from .seeder import ORG_UNITS, PRODUCTS

reviews: list[Review] = []
events: list[IncomingEvent] = []
products = PRODUCTS
org_units = ORG_UNITS
