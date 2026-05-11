"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-05-01
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id              SERIAL PRIMARY KEY,
            external_id     INT UNIQUE NOT NULL,
            customer_name   TEXT,
            text            TEXT NOT NULL,
            rating          SMALLINT,
            created_at      TIMESTAMPTZ NOT NULL,
            product_id      INT,
            sentiment       TEXT,
            rating_mismatch BOOLEAN DEFAULT FALSE,
            processed_at    TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_created_at  ON reviews (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_sentiment    ON reviews (sentiment)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id  ON reviews (product_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS issue_clusters (
            id          SERIAL PRIMARY KEY,
            label       TEXT NOT NULL,
            status      TEXT DEFAULT 'open',
            created_at  TIMESTAMPTZ DEFAULT now(),
            updated_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_issue_clusters_status ON issue_clusters (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS review_entities (
            id          SERIAL PRIMARY KEY,
            review_id   INT REFERENCES reviews(id),
            entity      TEXT NOT NULL,
            is_issue    BOOLEAN DEFAULT FALSE,
            cluster_id  INT REFERENCES issue_clusters(id),
            embedding   BYTEA
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_re_review_id  ON review_entities (review_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_re_cluster_id ON review_entities (cluster_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_re_is_issue   ON review_entities (is_issue)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS dispatched_events (
            id          SERIAL PRIMARY KEY,
            event_id    UUID UNIQUE NOT NULL,
            event_type  TEXT NOT NULL,
            review_id   INT REFERENCES reviews(id),
            description TEXT,
            metadata    JSONB DEFAULT '{}',
            sent_at     TIMESTAMPTZ DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dispatched_events")
    op.execute("DROP TABLE IF EXISTS review_entities")
    op.execute("DROP TABLE IF EXISTS issue_clusters")
    op.execute("DROP TABLE IF EXISTS reviews")
