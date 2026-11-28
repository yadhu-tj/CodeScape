"""Repository ingestion, graph retrieval, and local symbol search."""

from collections import Counter
from collections.abc import AsyncIterator
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ == "backend.routes":
    from ..models import Edge, Node, Repo
    from ..schemas.common import api_response
    from ..services.ingestion_service import ingest_repository
    from ..services.repository_snapshot import RepositoryInputError
else:
    from models import Edge, Node, Repo
    from schemas.common import api_response
    from services.ingestion_service import ingest_repository
    from services.repository_snapshot import RepositoryInputError


router = APIRouter(prefix="/api/v1/repos", tags=["repositories"])
REPO_FIELDS = (
    Repo.id, Repo.name, Repo.source_url, Repo.commit_sha, Repo.source_sha256, Repo.status,
    Repo.embedding_status, Repo.ingested_at,
)
NODE_FIELDS = (
    Node.id, Node.qualified_name, Node.kind, Node.route_path, Node.file_path,
    Node.start_line, Node.end_line, Node.signature, Node.complexity,
)
EDGE_FIELDS = (
    Edge.id, Edge.src_node_id, Edge.dst_node_id, Edge.kind, Edge.confidence,
    Edge.call_site_line, Edge.raw_callee_expr,
)


class IngestionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    source: str | None = Field(default=None, min_length=1, max_length=500)
    embed: bool = False
    import_root: str = Field(default=".", min_length=1, max_length=350)


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(min_length=1, max_length=250)


async def session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.sessions() as db:
        yield db


async def _repo(db: AsyncSession, repo_id: int) -> dict:
    row = (await db.execute(select(*REPO_FIELDS).where(Repo.id == repo_id))).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Repository not found")
    return dict(row)


@router.post("", status_code=201)
async def create_repo(request: Request, payload: IngestionRequest | None = None,
                      db: AsyncSession = Depends(session)):
    payload = payload or IngestionRequest()
    try:
        repo = await ingest_repository(
            payload.source, db, settings=request.app.state.settings, embed=payload.embed,
            import_root=payload.import_root,
        )
    except RepositoryInputError as exc:
        raise HTTPException(400, str(exc)) from None
    data = {field.key: getattr(repo, field.key) for field in REPO_FIELDS}
    return api_response(data, "Repository ingested", status_code=201)


@router.get("")
async def list_repos(db: AsyncSession = Depends(session)):
    rows = (await db.execute(select(*REPO_FIELDS).order_by(Repo.id))).mappings()
    return api_response([dict(row) for row in rows])


@router.get("/{repo_id}/graph")
async def graph(repo_id: int, db: AsyncSession = Depends(session)):
    repo = await _repo(db, repo_id)
    nodes = [dict(row) for row in (await db.execute(
        select(*NODE_FIELDS).where(Node.repo_id == repo_id).order_by(Node.id)
    )).mappings()]
    edges = [dict(row) for row in (await db.execute(
        select(*EDGE_FIELDS).where(Edge.repo_id == repo_id).order_by(Edge.id)
    )).mappings()]
    return api_response({
        "repo": repo, "nodes": nodes, "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_by_kind": dict(Counter(node["kind"] for node in nodes)),
            "edges_by_kind": dict(Counter(edge["kind"] for edge in edges)),
            "calls_by_confidence": dict(Counter(
                edge["confidence"] for edge in edges if edge["kind"] == "calls"
            )),
            "route_count": sum(node["route_path"] is not None for node in nodes),
        },
    })


@router.post("/{repo_id}/search")
async def lexical_search(repo_id: int, payload: SearchRequest, db: AsyncSession = Depends(session)):
    await _repo(db, repo_id)
    terms = list(dict.fromkeys(re.findall(r"\w+", payload.query.lower())))[:16]
    matches = []
    if terms:
        names = [Node.qualified_name.icontains(term, autoescape=True) for term in terms]
        source_text = [
            or_(Node.signature.icontains(term, autoescape=True), Node.docstring.icontains(term, autoescape=True),
                Node.route_path.icontains(term, autoescape=True))
            for term in terms
        ]
        score = sum(case((name, 4), (excerpt, 1), else_=0) for name, excerpt in zip(names, source_text))
        rows = await db.execute(
            select(*NODE_FIELDS).where(
                Node.repo_id == repo_id, Node.kind.in_(("function", "class")), or_(*names, *source_text)
            ).order_by(score.desc(), Node.id).limit(10)
        )
        matches = [dict(row) for row in rows.mappings()]
    return api_response({
        "search_mode": "lexical_fallback", "anchor_node": matches[0] if matches else None,
        "secondary_matches": matches[1:],
    }, "Local symbol search" if matches else "No matching symbols")
