from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        Index("idx_run_events_run_seq", "run_id", "seq"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("chaos_runs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(BigInteger)
    event: Mapped[str] = mapped_column(String(80))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
