from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    source_url: Mapped[str | None] = mapped_column(String(500))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    local_path: Mapped[str] = mapped_column(String(500))
    image_tag: Mapped[str] = mapped_column(String(150), server_default="codescape-sandbox:latest")
    status: Mapped[str] = mapped_column(String(30), server_default="ready")
    embedding_status: Mapped[str] = mapped_column(String(30), server_default="disabled")
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
