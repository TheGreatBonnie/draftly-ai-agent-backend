from __future__ import annotations

from langchain_core.tools import tool

from src.memory.episodic import search_threads
from src.memory.organizational import search_memory
from src.memory.reviewer import get_reviewer_memory
from src.memory.vector_store import search_similar


@tool
async def search_semantic_memory(org_id: str, query: str, k: int = 5) -> str:
    """Search documentation and support threads by semantic similarity using vector embeddings."""
    results = await search_similar(org_id, query, k=k)
    if not results:
        return "No similar content found."
    return "\n".join(
        f"[{r['content_type']}] (similarity: {r['similarity']:.2f}) {r['content_text'][:300]}"
        for r in results
    )


@tool
async def search_episodic_memory(org_id: str, query: str, k: int = 5) -> str:
    """Search historical support conversations for similar questions."""
    results = await search_threads(org_id, query, limit=k)
    if not results:
        return "No similar threads found."
    return "\n".join(
        f"[{r['source']}] {r.get('title', 'Untitled')}: {r.get('question_summary', '')[:200]}"
        for r in results
    )


@tool
async def search_organizational_memory(org_id: str, key: str) -> str:
    """Search organizational knowledge base for best practices and known solutions."""
    results = await search_memory(org_id, key_pattern=key, limit=5)
    if not results:
        return "No organizational memory found."
    return "\n".join(f"[{r['memory_type']}] {r['key']}: {str(r['value'])[:200]}" for r in results)


@tool
async def get_reviewer_context(org_id: str) -> str:
    """Get reviewer feedback history to understand writing preferences and common edits."""
    results = await get_reviewer_memory(org_id, limit=5)
    if not results:
        return "No reviewer history found."
    return "\n".join(f"[reviewer] {r['key']}: {str(r['value'])[:200]}" for r in results)


MEMORY_TOOLS = [
    search_semantic_memory,
    search_episodic_memory,
    search_organizational_memory,
    get_reviewer_context,
]
