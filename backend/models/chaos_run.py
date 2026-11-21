from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChaosRun(Base):
    __tablename__ = "chaos_runs"
    __table_args__ = (Index("idx_chaos_runs_node_id", "node_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    blamed_node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), server_default="queued")
    classification: Mapped[str | None] = mapped_column(String(40))
    test_code: Mapped[str | None] = mapped_column(Text)
    report: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    log_ref: Mapped[str | None] = mapped_column(Text)
    seed_key: Mapped[str | None] = mapped_column(String(150), unique=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
