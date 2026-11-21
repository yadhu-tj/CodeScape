from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        Index("idx_nodes_repo_id", "repo_id"),
        Index("idx_nodes_qualified_name", "repo_id", "qualified_name"),
        Index(
            "idx_nodes_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    qualified_name: Mapped[str] = mapped_column(String(350))
    file_path: Mapped[str] = mapped_column(String(350))
    start_line: Mapped[int]
    end_line: Mapped[int]
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)
    route_path: Mapped[str | None] = mapped_column(String(250))
    complexity: Mapped[int] = mapped_column(server_default=text("1"))
    body_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
