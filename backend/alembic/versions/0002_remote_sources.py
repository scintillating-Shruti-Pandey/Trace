"""Register remote source provenance separately from locally ingested assets."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE remote_sources (
            id UUID PRIMARY KEY,
            repo TEXT NOT NULL,
            revision TEXT NOT NULL,
            path TEXT NOT NULL,
            source_uri TEXT NOT NULL,
            license TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('assembly', 'repair')),
            duration_s DOUBLE PRECISION NOT NULL CHECK (duration_s BETWEEN 120 AND 900),
            trial_group TEXT NOT NULL,
            verification JSONB NOT NULL,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (repo, revision, path)
        )
    """)


def downgrade():
    op.drop_table("remote_sources")
