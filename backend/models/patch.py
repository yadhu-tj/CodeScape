from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("chaos_runs.id", ondelete="CASCADE"))
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    replacement_code: Mapped[str] = mapped_column(Text)
    unified_diff: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), server_default="proposed")
    verification_report: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seed_key: Mapped[str | None] = mapped_column(String(150), unique=True)
