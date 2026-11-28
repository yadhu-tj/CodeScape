"""Persist a repository graph before attempting optional provider enrichment."""

import asyncio
from dataclasses import asdict
import logging
import math

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ == "backend.services":
    from ..config import Settings
    from ..models import Edge, Node, Repo
    from ..utils.redaction import redact_code_excerpt
else:
    from config import Settings
    from models import Edge, Node, Repo
    from utils.redaction import redact_code_excerpt

from .ai_provider import AIProvider, GeminiProvider
from .python_graph import analyze_snapshot
from .repository_snapshot import acquire_snapshot, discard_snapshot


BATCH_SIZE = 32
EMBEDDING_TIMEOUT_SECONDS = 90
logger = logging.getLogger(__name__)


async def _persist_graph(source: str | None, db: AsyncSession, settings: Settings,
                         embedding_status: str, import_root: str) -> Repo:
    snapshot = await asyncio.to_thread(
        acquire_snapshot, source, settings.REPOS_STORAGE_PATH,
        settings.REPOS_IMPORT_ROOT, settings.REPOS_GIT_HOSTS,
    )
    try:
        graph = await asyncio.to_thread(analyze_snapshot, snapshot.path, import_root)
        async with db.begin():
            repo = Repo(
                name=snapshot.name, local_path=str(snapshot.path), source_url=snapshot.source_url,
                commit_sha=snapshot.commit_sha, source_sha256=snapshot.source_sha256,
                embedding_status=embedding_status,
            )
            db.add(repo)
            await db.flush()
            nodes = [Node(repo_id=repo.id, **asdict(symbol)) for symbol in graph.symbols]
            db.add_all(nodes)
            await db.flush()
            await asyncio.to_thread(graph.resolve_references)
            edges = [
                {
                    "repo_id": repo.id, "src_node_id": nodes[edge.source].id,
                    "dst_node_id": nodes[edge.destination].id if edge.destination is not None else None,
                    "kind": edge.kind, "confidence": edge.confidence,
                    "call_site_line": edge.line, "raw_callee_expr": edge.expression,
                }
                for edge in graph.references
            ]
            for offset in range(0, len(edges), 1_000):
                await db.execute(insert(Edge), edges[offset:offset + 1_000])
    except Exception:
        await asyncio.to_thread(discard_snapshot, snapshot.path, settings.REPOS_STORAGE_PATH)
        raise
    return repo


async def _embed_repository(repo_id: int, db: AsyncSession, provider: AIProvider,
                            dimensions: int) -> str:
    async with db.begin():
        result = await db.execute(
            select(Node.id, Node.qualified_name, Node.signature, Node.docstring, Node.body_text)
            .where(Node.repo_id == repo_id, Node.kind.in_(("function", "class")))
            .order_by(Node.id)
        )
        rows = result.all()
    if not rows:
        return "not_applicable"
    updates = []
    async with asyncio.timeout(EMBEDDING_TIMEOUT_SECONDS):
        for offset in range(0, len(rows), BATCH_SIZE):
            batch = rows[offset:offset + BATCH_SIZE]
            excerpts = [
                redact_code_excerpt("\n".join((row.qualified_name, row.signature or "",
                                               row.docstring or "", row.body_text)))
                for row in batch
            ]
            vectors = await provider.embed_texts(excerpts)
            if len(vectors) != len(batch) or any(
                len(vector) != dimensions or not all(map(math.isfinite, vector)) for vector in vectors
            ):
                raise ValueError("The embedding provider returned invalid vectors.")
            updates.extend({"id": row.id, "embedding": vector}
                           for row, vector in zip(batch, vectors, strict=True))
    async with db.begin():
        for offset in range(0, len(updates), BATCH_SIZE):
            await db.execute(update(Node), updates[offset:offset + BATCH_SIZE])
        await db.execute(update(Repo).where(Repo.id == repo_id).values(embedding_status="ready"))
    return "ready"


async def ingest_repository(repo_path_or_url: str | None, db: AsyncSession, *,
                            settings: Settings | None = None, embed: bool = False,
                            import_root: str = ".") -> Repo:
    settings = settings or Settings()
    status = "disabled"
    if embed and not settings.DEMO_MODE:
        status = "pending" if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY else "unavailable"
    # A disconnected client must not leave a partial snapshot or an open transaction.
    persist = asyncio.create_task(_persist_graph(repo_path_or_url, db, settings, status, import_root))
    try:
        repo = await asyncio.shield(persist)
    except asyncio.CancelledError:
        repo = await persist
        if status == "pending":
            async with db.begin():
                repo.embedding_status = "cancelled"
        raise
    if status != "pending":
        return repo

    repo_id = repo.id
    provider = None
    try:
        provider = GeminiProvider(settings)
        status = await _embed_repository(repo_id, db, provider, settings.EMBEDDING_DIMENSIONS)
    except asyncio.CancelledError:
        status = "cancelled"
        raise
    except Exception as exc:
        logger.warning("Repository %s embedding failed (%s).", repo_id, type(exc).__name__)
        status = "failed"
    finally:
        try:
            if status != "ready":
                async with db.begin():
                    await db.execute(update(Repo).where(Repo.id == repo_id).values(embedding_status=status))
                    await db.refresh(repo)
        finally:
            if provider is not None:
                try:
                    await provider.close()
                except Exception as exc:
                    logger.warning("Embedding client cleanup failed (%s).", type(exc).__name__)
    return repo
