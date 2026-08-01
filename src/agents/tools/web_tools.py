from __future__ import annotations

from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import tool


@tool
def search_web(query: str, max_results: int = 5) -> dict:
    """Search the web for relevant documentation, tutorials, and articles.

    Args:
        query: The search query (be specific and detailed)
        max_results: Number of results to return (default: 5)

    Returns:
        Search results with titles, URLs, and content excerpts.
    """
    if not query.strip():
        return {"error": "Empty query"}

    try:
        wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results)
        results = wrapper.results(query, max_results=max_results)
        return {
            "results": [
                {
                    "title": r["title"],
                    "url": r["link"],
                    "content": r["snippet"],
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"error": f"Search failed: {e}"}


WEB_TOOLS = [search_web]
