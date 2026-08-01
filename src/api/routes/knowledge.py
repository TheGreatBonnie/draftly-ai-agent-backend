from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from src.api.auth import get_verified_token
from src.database import execute, fetch_all, fetch_one
from src.knowledge.url_fetcher import fetch_url_content
from src.memory.chunking import store_document_chunks
from src.memory.vector_store import delete_embeddings_for_content

router = APIRouter()


class IngestKnowledgeRequest(BaseModel):
    title: str
    content: str
    doc_type: str = "reference"
    source_url: str | None = None


class FetchUrlRequest(BaseModel):
    url: HttpUrl


class FetchUrlResponse(BaseModel):
    url: str
    title: str
    content: str
    source_type: str


_fetch_timestamps: dict[str, list[float]] = {}
_FETCH_RATE_LIMIT = 10
_FETCH_RATE_WINDOW = 60.0


@router.post("/fetch-url", response_model=FetchUrlResponse)
async def fetch_url(
    request: FetchUrlRequest,
    token: dict = Depends(get_verified_token),
) -> FetchUrlResponse:
    """Fetch and extract content from a URL for knowledge base import."""
    import time

    org_id = token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    now = time.time()
    org_timestamps = _fetch_timestamps.setdefault(org_id, [])
    org_timestamps[:] = [t for t in org_timestamps if now - t < _FETCH_RATE_WINDOW]
    if len(org_timestamps) >= _FETCH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    org_timestamps.append(now)

    try:
        result = await fetch_url_content(str(request.url))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return FetchUrlResponse(
        url=result.url,
        title=result.title,
        content=result.content,
        source_type=result.source_type,
    )


@router.post("")
async def ingest_knowledge(
    request: IngestKnowledgeRequest,
    token: dict = Depends(get_verified_token),
) -> dict:
    """Ingest a company document into the knowledge base."""
    org_id = token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    if request.doc_type not in ("howto", "faq", "tutorial", "troubleshooting", "reference"):
        raise HTTPException(
            status_code=400,
            detail="doc_type must be one of: howto, faq, tutorial, troubleshooting, reference",
        )

    row = await fetch_one(
        """
        INSERT INTO documentation
            (org_id, title, content, doc_type, status, confidence_score)
        VALUES ($1, $2, $3, $4, 'approved', 1.0)
        RETURNING id::text
        """,
        org_id,
        request.title,
        request.content,
        request.doc_type,
    )
    assert row is not None
    doc_id = row["id"]

    metadata = {"source": "knowledge_upload", "doc_type": request.doc_type}
    if request.source_url:
        metadata["source_url"] = request.source_url

    await delete_embeddings_for_content(doc_id)
    await store_document_chunks(
        org_id=org_id,
        content_id=doc_id,
        title=request.title,
        content=request.content,
        metadata=metadata,
    )

    return {"id": doc_id, "title": request.title, "status": "approved"}


@router.get("")
async def list_knowledge(token: dict = Depends(get_verified_token)) -> list[dict]:
    """List all company knowledge documents."""
    org_id = token.get("org_id")
    if not org_id:
        return []

    rows = await fetch_all(
        "SELECT id::text, title, content, doc_type, version, status, "
        "confidence_score, created_at, updated_at "
        "FROM documentation WHERE org_id = $1 AND status = 'approved' "
        "ORDER BY created_at DESC",
        org_id,
    )
    return [dict(r) for r in rows]


@router.delete("/{doc_id}")
async def delete_knowledge(doc_id: str, token: dict = Depends(get_verified_token)) -> dict:
    """Delete a knowledge document and its embedding."""
    org_id = token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    existing = await fetch_one(
        "SELECT id::text FROM documentation WHERE id = $1 AND org_id = $2",
        doc_id,
        org_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    await delete_embeddings_for_content(doc_id)
    await execute("DELETE FROM documentation WHERE id = $1", doc_id)

    return {"status": "deleted"}
