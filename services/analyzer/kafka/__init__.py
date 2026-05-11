"""Пакет с логикой Kafka. Атрошенко Б. С."""

from .producer import KafkaManager
from .consumer import Consumer

__all__ = ["KafkaManager", "Consumer"]
