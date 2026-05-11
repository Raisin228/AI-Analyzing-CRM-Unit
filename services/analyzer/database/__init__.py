"""Пакет для работы с БД. Атрошенко Б. С."""

from .db import DBManager
from .queries import DAO

__all__ = ["DBManager", "DAO"]
