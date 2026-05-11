"""entity categories — replace free-form entities with fixed enum

Revision ID: 002
Revises: 001
Create Date: 2026-05-11
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_CATEGORIES = ("delivery", "courier", "payment", "product_quality", "support", "app", "other")


def upgrade() -> None:
    op.execute("CREATE TYPE entity_category AS ENUM (%s)" % ", ".join(f"'{c}'" for c in _CATEGORIES))

    op.execute("DROP TABLE IF EXISTS review_entities")
    op.execute("DROP TABLE IF EXISTS issue_clusters")

    op.execute("""
        CREATE TABLE issue_clusters (
            id         SERIAL PRIMARY KEY,
            category   entity_category NOT NULL,
            status     TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON issue_clusters (status)")
    op.execute("CREATE UNIQUE INDEX ON issue_clusters (category) WHERE status = 'open'")

    op.execute("""
        CREATE TABLE review_entities (
            id         SERIAL PRIMARY KEY,
            review_id  INT NOT NULL REFERENCES reviews(id),
            category   entity_category NOT NULL,
            is_issue   BOOLEAN NOT NULL DEFAULT FALSE,
            cluster_id INT REFERENCES issue_clusters(id)
        )
    """)
    op.execute("CREATE INDEX ON review_entities (review_id)")
    op.execute("CREATE INDEX ON review_entities (cluster_id)")
    op.execute("CREATE INDEX ON review_entities (category, is_issue)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS review_entities")
    op.execute("DROP TABLE IF EXISTS issue_clusters")
    op.execute("DROP TYPE IF EXISTS entity_category")

    op.execute("""
        CREATE TABLE issue_clusters (
            id         SERIAL PRIMARY KEY,
            label      TEXT NOT NULL,
            status     TEXT DEFAULT 'open',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE review_entities (
            id         SERIAL PRIMARY KEY,
            review_id  INT REFERENCES reviews(id),
            entity     TEXT NOT NULL,
            is_issue   BOOLEAN DEFAULT FALSE,
            cluster_id INT REFERENCES issue_clusters(id),
            embedding  BYTEA
        )
    """)
