from __future__ import annotations

import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.memory.vector_store import store_embedding

logger = structlog.get_logger()

_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks suitable for embedding."""
    if not text.strip():
        return []
    chunks = _text_splitter.split_text(text)
    return [c for c in chunks if c.strip()]


async def store_document_chunks(
    org_id: str,
    content_id: str,
    title: str,
    content: str,
    metadata: dict | None = None,
) -> int:
    """Chunk a document and store each chunk as a separate embedding.

    Returns the number of chunks stored.
    """
    full_text = f"{title}\n\n{content}"
    chunks = chunk_text(full_text)

    if not chunks:
        logger.warning("empty_document_chunks", content_id=content_id)
        return 0

    base_metadata = metadata or {}
    stored = 0

    for i, chunk in enumerate(chunks):
        chunk_metadata = {
            "org_id": org_id,
            "content_type": "documentation",
            "content_id": content_id,
            **base_metadata,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        await store_embedding(
            org_id=org_id,
            content_type="documentation",
            content_id=content_id,
            content_text=chunk,
            metadata=chunk_metadata,
        )
        stored += 1

    logger.info(
        "document_chunks_stored",
        content_id=content_id,
        chunks=stored,
        total_chars=len(full_text),
    )
    return stored
