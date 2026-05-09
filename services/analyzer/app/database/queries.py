"""SQL-запросы к PostgreSQL."""

import json
import logging
from typing import Optional
from uuid import UUID

from analyzer.app.database.db import pool

logger = logging.getLogger(__name__)


# ── reviews ──────────────────────────────────────────────────────────────────

async def insert_review(
        external_id: int,
        customer_name: str,
        text: str,
        rating: int,
        created_at,
        product_id: int,
        sentiment: str,
        rating_mismatch: bool,
        processed_at,
) -> Optional[int]:
    async with pool().acquire() as conn:
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


# ── review_entities ───────────────────────────────────────────────────────────

async def insert_entity(
        review_id: int,
        entity: str,
        is_issue: bool,
        embedding_bytes: Optional[bytes] = None,
) -> int:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO review_entities (review_id, entity, is_issue, embedding)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            review_id, entity, is_issue, embedding_bytes,
        )
        return row["id"]


async def update_entity_cluster(entity_id: int, cluster_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE review_entities SET cluster_id = $1 WHERE id = $2",
            cluster_id, entity_id,
        )


async def get_entity_cluster(entity_id: int) -> Optional[int]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT cluster_id FROM review_entities WHERE id = $1",
            entity_id,
        )
        return row["cluster_id"] if row else None


async def get_all_issue_embeddings() -> list[tuple[int, bytes]]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, embedding FROM review_entities WHERE is_issue = TRUE AND embedding IS NOT NULL"
        )
        return [(r["id"], r["embedding"]) for r in rows]


# ── issue_clusters ────────────────────────────────────────────────────────────

async def insert_cluster(label: str) -> int:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO issue_clusters (label) VALUES ($1) RETURNING id",
            label,
        )
        return row["id"]


async def get_cluster_status(cluster_id: int) -> Optional[str]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM issue_clusters WHERE id = $1",
            cluster_id,
        )
        return row["status"] if row else None


async def touch_cluster(cluster_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE issue_clusters SET updated_at = now() WHERE id = $1",
            cluster_id,
        )


async def get_stale_open_clusters() -> list[int]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id
            FROM issue_clusters
            WHERE status = 'open'
              AND created_at < now() - interval '3 days'
            """
        )
        return [r["id"] for r in rows]


async def get_last_cluster_sentiments(cluster_id: int, n: int = 5) -> list[str]:
    async with pool().acquire() as conn:
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


async def close_cluster(cluster_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE issue_clusters SET status = 'closed', updated_at = now() WHERE id = $1",
            cluster_id,
        )


# ── anomaly queries ───────────────────────────────────────────────────────────

async def count_negative_last_24h() -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM reviews
            WHERE sentiment = 'negative'
              AND created_at >= now() - interval '24 hours'
            """
        )


async def count_negative_by_day_7d() -> list[int]:
    """Returns daily negative counts for the 7 days preceding the last 24h."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT COUNT(*) AS cnt
            FROM reviews
            WHERE sentiment = 'negative'
              AND created_at >= now() - interval '8 days'
              AND created_at < now() - interval '1 day'
            GROUP BY date_trunc('day', created_at)
            ORDER BY 1
            """
        )
        return [r["cnt"] for r in rows]


async def issue_entity_counts_24h() -> dict[str, int]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT re.entity, COUNT(*) AS cnt
            FROM review_entities re
                     JOIN reviews r ON r.id = re.review_id
            WHERE re.is_issue = TRUE
              AND r.created_at >= now() - interval '24 hours'
            GROUP BY re.entity
            """
        )
        return {r["entity"]: r["cnt"] for r in rows}


async def issue_entity_counts_7d() -> dict[str, int]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT re.entity, COUNT(*) AS cnt
            FROM review_entities re
                     JOIN reviews r ON r.id = re.review_id
            WHERE re.is_issue = TRUE
              AND r.created_at >= now() - interval '8 days'
              AND r.created_at < now() - interval '1 day'
            GROUP BY re.entity
            """
        )
        return {r["entity"]: r["cnt"] for r in rows}


# ── dispatched_events ─────────────────────────────────────────────────────────

async def event_already_sent(event_id: UUID) -> bool:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM dispatched_events WHERE event_id = $1",
            event_id,
        )
        return row is not None


async def insert_dispatched_event(
        event_id: UUID,
        event_type: str,
        review_id: Optional[int],
        description: str,
        metadata: dict,
) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dispatched_events (event_id, event_type, review_id, description, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (event_id) DO NOTHING
            """,
            event_id, event_type, review_id, description, json.dumps(metadata),
        )
