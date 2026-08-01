from unittest.mock import AsyncMock, patch

import pytest

from src.knowledge.url_fetcher import _find_markdown_alternate, fetch_url_content

HTML_PAGE = (
    b"<html><head><title>Test Page</title></head>"
    b"<body><h1>Hello</h1><p>World</p></body></html>"
)
HTML_NOTION = (
    b"<html><head><title>Notion Page</title></head>"
    b"<body><p>Notion content</p></body></html>"
)


@pytest.mark.asyncio
async def test_detect_webpage():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (HTML_PAGE, "text/html")
        with patch(
            "src.knowledge.url_fetcher._extract_webpage",
            return_value=("Test Page", "Hello\nWorld"),
        ):
            result = await fetch_url_content("https://example.com/page")
            assert result.title == "Test Page"
            assert result.content == "Hello\nWorld"
            assert result.source_type == "webpage"
            assert result.url == "https://example.com/page"


@pytest.mark.asyncio
async def test_detect_pdf():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (b"%PDF-1.4 fake pdf bytes", "application/pdf")
        with patch(
            "src.knowledge.url_fetcher._extract_pdf",
            return_value=("PDF Title", "PDF content here"),
        ):
            result = await fetch_url_content("https://example.com/doc.pdf")
            assert result.title == "PDF Title"
            assert result.source_type == "pdf"


@pytest.mark.asyncio
async def test_detect_google_doc():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (b"Google doc exported text content", "text/plain")
        result = await fetch_url_content(
            "https://docs.google.com/document/d/abc123/edit"
        )
        assert result.source_type == "google_doc"
        assert result.content == "Google doc exported text content"


@pytest.mark.asyncio
async def test_detect_notion():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (HTML_NOTION, "text/html")
        with patch(
            "src.knowledge.url_fetcher._extract_webpage",
            return_value=("Notion Page", "Notion content"),
        ):
            result = await fetch_url_content(
                "https://mycompany.notion.so/Page-Title"
            )
            assert result.source_type == "notion"
            assert result.title == "Notion Page"


@pytest.mark.asyncio
async def test_fetch_failure():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("Connection refused")
        with pytest.raises(ValueError, match="Could not fetch URL"):
            await fetch_url_content("https://unreachable.example.com")


@pytest.mark.asyncio
async def test_no_content_extracted():
    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = (b"", "text/html")
        with patch(
            "src.knowledge.url_fetcher._extract_webpage",
            return_value=("", ""),
        ):
            with pytest.raises(ValueError, match="No readable content"):
                await fetch_url_content("https://example.com/empty")


def test_find_markdown_alternate():
    html = (
        b'<html><head>'
        b'<link rel="alternate" type="text/markdown" href="/docs/page.md"/>'
        b"</head></html>"
    )
    assert _find_markdown_alternate(html) == "/docs/page.md"


def test_find_markdown_alternate_reversed_attrs():
    html = (
        b'<html><head>'
        b'<link type="text/markdown" rel="alternate" href="/docs/page.md"/>'
        b"</head></html>"
    )
    assert _find_markdown_alternate(html) == "/docs/page.md"


def test_find_markdown_alternate_missing():
    html = b'<html><head><link rel="stylesheet" href="style.css"/></head></html>'
    assert _find_markdown_alternate(html) is None


@pytest.mark.asyncio
async def test_webpage_prefers_markdown_alternate():
    html_with_md_link = (
        b"<html><head>"
        b'<title>SPA Page</title>'
        b'<link rel="alternate" type="text/markdown" href="/docs/page.md"/>'
        b"</head><body></body></html>"
    )
    markdown_content = "# SPA Page\n\nSome content\n\n```python\nprint('hello')\n```"

    with patch(
        "src.knowledge.url_fetcher._fetch_bytes", new_callable=AsyncMock
    ) as mock_fetch:
        # First call: fetch the HTML page
        # Second call: fetch the markdown alternate
        mock_fetch.side_effect = [
            (html_with_md_link, "text/html"),
            (markdown_content.encode(), "text/markdown"),
        ]
        result = await fetch_url_content("https://docs.example.com/page")
        assert result.title == "SPA Page"
        assert "print('hello')" in result.content
        assert result.source_type == "webpage"
        # Verify the markdown URL was fetched (relative resolved to absolute)
        assert mock_fetch.call_count == 2
        md_url = mock_fetch.call_args_list[1][0][0]
        assert "docs.example.com" in md_url
        assert md_url.endswith("/docs/page.md")
