from __future__ import annotations

import json
import uuid
from typing import cast

import structlog
from langchain_cockroachdb import (  # type: ignore[import-untyped]
    AsyncCockroachDBVectorStore,
    CockroachDBEngine,
    CSPANNIndex,
    DistanceStrategy,
)
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from src.config import settings

logger = structlog.get_logger()

_engine: CockroachDBEngine | None = None
_vector_store: AsyncCockroachDBVectorStore | None = None


def _normalize_url(url: str) -> str:
    """Rewrite postgresql:// to cockroachdb:// for the library."""
    if url.startswith("postgresql://"):
        return "cockroachdb://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "cockroachdb://" + url[len("postgres://"):]
    return url


async def get_vector_store() -> AsyncCockroachDBVectorStore:
    global _engine, _vector_store
    if _vector_store is not None:
        return _vector_store

    url = _normalize_url(settings.cockroachdb_url)

    _engine = CockroachDBEngine.from_connection_string(url)

    await _engine.ainit_vectorstore_table(
        table_name="embeddings",
        vector_dimension=3072,
    )

    embeddings = OpenAIEmbeddings(  # type: ignore[call-arg]
        openai_api_key=settings.requesty_api_key,
        openai_api_base=settings.requesty_base_url,
        model=settings.embedding_model,
    )

    _vector_store = AsyncCockroachDBVectorStore(
        engine=_engine,
        embeddings=embeddings,
        collection_name="embeddings",
        distance_strategy=DistanceStrategy.COSINE,
        namespace_column=None,
    )

    try:
        await _vector_store.aapply_vector_index(
            CSPANNIndex(distance_strategy=DistanceStrategy.COSINE),
        )
        logger.info("cspann_index_created")
    except Exception:
        logger.debug("cspann_index_already_exists")

    return _vector_store


async def embed_text(text: str) -> list[float]:
    store = await get_vector_store()
    return cast(list[float], await store.embeddings.aembed_query(text))


async def store_embedding(
    org_id: str,
    content_type: str,
    content_id: str,
    content_text: str,
    metadata: dict | None = None,
) -> str:
    store = await get_vector_store()

    full_metadata = {
        "org_id": org_id,
        "content_type": content_type,
        "content_id": content_id,
        **(metadata or {}),
    }

    doc_id = str(uuid.uuid4())
    embedding = await store.embeddings.aembed_query(content_text)

    # Use parameterized INSERT via engine directly — the library's
    # _insert_batch uses text() with string interpolation which breaks
    # when content contains %(name)s patterns (SQLAlchemy bind params).
    if _engine is None:
        raise RuntimeError("vector store engine not initialized")
    async with _engine.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.embeddings (id, content, embedding, metadata) "
                "VALUES (:id, :content, :embedding, CAST(:metadata AS jsonb))"
            ),
            {
                "id": doc_id,
                "content": content_text,
                "embedding": json.dumps(embedding),
                "metadata": json.dumps(full_metadata),
            },
        )

    logger.info("embedding_stored", id=doc_id, content_type=content_type)
    return doc_id


async def search_similar(
    org_id: str,
    query_text: str,
    content_type: str | None = None,
    k: int = 10,
) -> list[dict]:
    store = await get_vector_store()

    filter_dict: dict = {"org_id": org_id}
    if content_type:
        filter_dict["content_type"] = content_type

    results = await store.asimilarity_search_with_score(
        query_text,
        k=k,
        filter=filter_dict,
    )

    return [
        {
            "id": doc.id or "",
            "content_type": doc.metadata.get("content_type", ""),
            "content_id": doc.metadata.get("content_id", ""),
            "content_text": doc.page_content,
            "metadata": doc.metadata,
            "similarity": 1.0 - score,
        }
        for doc, score in results
    ]


async def delete_embedding(embedding_id: str) -> None:
    store = await get_vector_store()
    await store.adelete([embedding_id])
    logger.info("embedding_deleted", id=embedding_id)


async def delete_embeddings_for_content(content_id: str) -> None:
    """Delete all embeddings for a given content_id (e.g., all chunks of a document)."""
    store = await get_vector_store()

    results = await store.asimilarity_search_with_score(
        " ",
        k=1000,
        filter={"content_id": content_id},
    )

    ids = [doc.id for doc, _ in results if doc.id]
    if ids:
        await store.adelete(ids)
    logger.info("embeddings_deleted_for_content", content_id=content_id, count=len(ids))
