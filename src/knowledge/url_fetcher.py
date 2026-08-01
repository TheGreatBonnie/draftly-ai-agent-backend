from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura


@dataclass
class FetchUrlResult:
    url: str
    title: str
    content: str
    source_type: str  # "webpage" | "pdf" | "google_doc" | "notion"


def _detect_source_type(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if "docs.google.com" in host and "/document/" in parsed.path:
        return "google_doc"
    if re.search(r"(^|\.)notion\.(so|site)$", host):
        return "notion"
    if parsed.path.lower().endswith(".pdf"):
        return "pdf"
    return "webpage"


def _to_google_doc_export_url(url: str) -> str:
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError("Invalid Google Docs URL")
    doc_id = match.group(1)
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


async def _fetch_bytes(url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        return resp.content, content_type


def _find_markdown_alternate(html: bytes) -> str | None:
    """Check for a <link rel="alternate" type="text/markdown" href="..."> tag."""
    decoded = html.decode(errors="replace")
    match = re.search(
        r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']text/markdown["\'][^>]+href=["\']([^"\']+)["\']',
        decoded,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    match = re.search(
        r'<link[^>]+type=["\']text/markdown["\'][^>]+rel=["\']alternate["\'][^>]+href=["\']([^"\']+)["\']',
        decoded,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None


def _extract_webpage(html: bytes) -> tuple[str, str]:
    text = trafilatura.extract(
        html, include_comments=False, include_tables=True, include_formatting=True
    ) or ""
    metadata = trafilatura.extract(html, include_comments=False, output_format="json") or "{}"
    try:
        meta = json.loads(metadata)
        title = meta.get("title", "")
    except (json.JSONDecodeError, AttributeError):
        title = ""
    if not title:
        title_match = re.search(
            r"<title[^>]*>([^<]+)</title>", html.decode(errors="replace"), re.IGNORECASE
        )
        title = title_match.group(1).strip() if title_match else ""
    return title, text.strip()


def _title_from_markdown(text: str) -> str:
    """Extract title from the first heading in markdown content."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _extract_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    import fitz  # type: ignore[import-untyped]

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    title = doc.metadata.get("title", "") if doc.metadata else ""
    pages = [page.get_text() for page in doc]
    doc.close()
    content = "\n".join(pages).strip()
    if not title:
        title = content[:80].split("\n")[0] if content else ""
    return title, content


async def fetch_url_content(url: str) -> FetchUrlResult:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    source_type = _detect_source_type(url)

    try:
        if source_type == "google_doc":
            export_url = _to_google_doc_export_url(url)
            content_bytes, _ = await _fetch_bytes(export_url)
            content = content_bytes.decode(errors="replace").strip()
            title = content.split("\n")[0][:200] if content else ""
            if not content:
                raise ValueError("No readable content found at URL")
            return FetchUrlResult(url=url, title=title, content=content, source_type=source_type)

        content_bytes, content_type = await _fetch_bytes(url)

        if source_type == "pdf" or "pdf" in content_type:
            title, content = _extract_pdf(content_bytes)
            source_type = "pdf"
        else:
            # Check for a markdown alternate link (common in Mintlify/Next.js doc sites)
            # This preserves code blocks that SPA HTML rendering strips from raw HTML
            md_path = _find_markdown_alternate(content_bytes)
            if md_path:
                from urllib.parse import urljoin

                md_url = urljoin(url, md_path)
                md_bytes, _ = await _fetch_bytes(md_url)
                content = md_bytes.decode(errors="replace").strip()
                title = _title_from_markdown(content)
                if not title:
                    # Fallback: extract from <title> tag
                    title_match = re.search(
                        r"<title[^>]*>([^<]+)</title>",
                        content_bytes.decode(errors="replace"),
                        re.IGNORECASE,
                    )
                    title = title_match.group(1).strip() if title_match else ""
            else:
                title, content = _extract_webpage(content_bytes)

        if not content:
            raise ValueError("No readable content found at URL")

        return FetchUrlResult(url=url, title=title, content=content, source_type=source_type)

    except ValueError:
        raise
    except httpx.HTTPStatusError:
        raise ValueError("Could not fetch URL: HTTP error")
    except Exception as e:
        raise ValueError(f"Could not fetch URL: {e}")
