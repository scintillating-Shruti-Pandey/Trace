"""Initial corpus, vector, stage and evaluation schema from engineering spec section 4.5."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in (
        "stage_status",
        "eval_results",
        "eval_runs",
        "eval_gold",
        "eval_queries",
        "vec_image",
        "vec_chunk",
        "vec_segment_visual",
        "vec_segment_text",
        "evidence_links",
        "images",
        "chunks",
        "segments",
        "assets",
    ):
        op.execute(f"DROP TABLE {table}")
