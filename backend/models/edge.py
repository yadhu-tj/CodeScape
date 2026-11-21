from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (
        Index("idx_edges_repo_id", "repo_id"),
        Index("idx_edges_src_node_id", "src_node_id"),
        Index("idx_edges_dst_node_id", "dst_node_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    src_node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    dst_node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(20))
    call_site_line: Mapped[int | None]
    raw_callee_expr: Mapped[str | None] = mapped_column(Text)
