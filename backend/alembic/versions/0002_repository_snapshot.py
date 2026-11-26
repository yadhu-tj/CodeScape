"""Record repository snapshot provenance and embedding status."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repos", sa.Column("source_sha256", sa.String(64), nullable=True))
    op.add_column(
        "repos",
        sa.Column("embedding_status", sa.String(30), server_default="disabled", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("repos", "embedding_status")
    op.drop_column("repos", "source_sha256")
