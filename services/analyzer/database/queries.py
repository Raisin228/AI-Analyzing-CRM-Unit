"""SQL-запросы к PostgreSQL. Атрошенко Б. С."""

import json
import logging
from typing import Optional
from uuid import UUID

from .db import DBManager

logger = logging.getLogger(__name__)


class DAO:
    # ── reviews ──────────────────────────────────────────────────────────────

    @classmethod
    async def insert_review(
            cls,
            external_id: str,
            customer_name: str,
            text: str,
            rating: int,
            created_at,
            product_id: str,
            sentiment: str,
            rating_mismatch: bool,
            processed_at,
    ) -> Optional[int]:
        async with DBManager.get().pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO reviews
                (external_id, customer_name, text, rating, created_at,
                 product_id, sentiment, rating_mismatch, processed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (external_id) DO NOTHING
                RETURNING id
                """,
                external_id, customer_name, text, rating, created_at,
                product_id, sentiment, rating_mismatch, processed_at,
            )
            return row["id"] if row else None

    # ── review_entities ───────────────────────────────────────────────────────

    @classmethod
    async def insert_entity(cls, review_id: int, category: str, is_issue: bool) -> int:
        async with DBManager.get().pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO review_entities (review_id, category, is_issue)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                review_id, category, is_issue,
            )
            return row["id"]

    @classmethod
    async def update_entity_cluster(cls, entity_id: int, cluster_id: int) -> None:
        async with DBManager.get().pool.acquire() as conn:
            await conn.execute(
                "UPDATE review_entities SET cluster_id = $1 WHERE id = $2",
                cluster_id, entity_id,
            )

    # ── issue_clusters ────────────────────────────────────────────────────────

    @classmethod
    async def insert_cluster(cls, category: str) -> int:
        async with DBManager.get().pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO issue_clusters (category) VALUES ($1) RETURNING id",
                category,
            )
            return row["id"]

    @classmethod
    async def get_open_cluster_by_category(cls, category: str) -> Optional[int]:
        async with DBManager.get().pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM issue_clusters WHERE category = $1 AND status = 'open'",
                category,
            )
            return row["id"] if row else None

    @classmethod
    async def touch_cluster(cls, cluster_id: int) -> None:
        async with DBManager.get().pool.acquire() as conn:
            await conn.execute(
                "UPDATE issue_clusters SET updated_at = now() WHERE id = $1",
                cluster_id,
            )

    @classmethod
    async def get_stale_open_clusters(cls) -> list[int]:
        async with DBManager.get().pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM issue_clusters
                WHERE status = 'open'
                  AND created_at < now() - interval '3 days'
                """
            )
            return [r["id"] for r in rows]

    @classmethod
    async def get_last_cluster_sentiments(cls, cluster_id: int, n: int = 5) -> list[str]:
        async with DBManager.get().pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.sentiment
                FROM reviews r
                    JOIN review_entities re ON re.review_id = r.id
                WHERE re.cluster_id = $1
                  AND r.sentiment IS NOT NULL
                ORDER BY r.created_at DESC
                LIMIT $2
                """,
                cluster_id, n,
            )
            return [r["sentiment"] for r in rows]

    @classmethod
    async def close_cluster(cls, cluster_id: int) -> None:
        async with DBManager.get().pool.acquire() as conn:
            await conn.execute(
                "UPDATE issue_clusters SET status = 'closed', updated_at = now() WHERE id = $1",
                cluster_id,
            )

    # ─ anomaly queries ─

    @classmethod
    async def count_negative_last_24h(cls) -> int:
        """
        Получить кол-во негативных отзывов за последние 24 часа.

        :return: кол-во негативных отзывов.
        """

        async with DBManager.get().pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT COUNT(*) FROM reviews
                WHERE sentiment = 'negative'
                  AND created_at >= now() - interval '24 hours'
                """
            )

    @classmethod
    async def count_negative_by_day_7d(cls) -> list[int]:
        """
        Получить кол-во негативных отзывов за последние 7 дней.

        :return: кол-во негативных отзывов.
        """

        async with DBManager.get().pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT COUNT(*) AS cnt FROM reviews
                WHERE sentiment = 'negative'
                  AND created_at >= now() - interval '8 days'
                  AND created_at < now() - interval '1 day'
                GROUP BY date_trunc('day', created_at)
                ORDER BY 1
                """
            )
            return [r["cnt"] for r in rows]

    @classmethod
    async def issue_category_counts_24h(cls) -> dict[str, int]:
        """
        Считаю кол-во созданных сущностей-отзывов по каждой категории.

        :return: словарь: "категория": кол-во обращений за последние сутки.
        """

        async with DBManager.get().pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT re.category, COUNT(*) AS cnt
                FROM review_entities re
                    JOIN reviews r ON r.id = re.review_id
                WHERE re.is_issue = TRUE
                  AND r.created_at >= now() - interval '24 hours'
                GROUP BY re.category
                """
            )
            return {r["category"]: r["cnt"] for r in rows}

    @classmethod
    async def issue_category_counts_7d(cls) -> dict[str, int]:
        """
        Считаю кол-во созданных сущностей-отзывов по каждой категории.

        :return: словарь: "категория": кол-во обращений за последнюю неделю.
        """

        async with DBManager.get().pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT re.category, COUNT(*) AS cnt
                FROM review_entities re
                    JOIN reviews r ON r.id = re.review_id
                WHERE re.is_issue = TRUE
                  AND r.created_at >= now() - interval '8 days'
                  AND r.created_at < now() - interval '1 day'
                GROUP BY re.category
                """
            )
            return {r["category"]: r["cnt"] for r in rows}

    # ── dispatched_events ─────────────────────────────────────────────────────

    @classmethod
    async def insert_dispatched_event(
            cls,
            event_id: UUID,
            event_type: str,
            review_id: Optional[str],
            description: str,
            metadata: dict,
    ) -> None:
        async with DBManager.get().pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO dispatched_events (event_id, event_type, review_id, description, metadata)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (event_id) DO NOTHING
                """,
                event_id, event_type, review_id, description, json.dumps(metadata),
            )
