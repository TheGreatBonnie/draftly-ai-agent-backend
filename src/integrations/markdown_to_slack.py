from __future__ import annotations

import re


def _parse_inline(text: str) -> list[dict]:
    """Parse inline markdown formatting into Slack rich_text inline elements."""
    elements: list[dict] = []
    pos = 0

    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("link", re.compile(r"\[([^\]]+)\]\(([^)]+)\)")),
        ("bold", re.compile(r"\*\*(.+?)\*\*|__(.+?)__")),
        (
            "italic",
            re.compile(
                r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)"
                r"|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)"
            ),
        ),
        ("strike", re.compile(r"~~(.+?)~~")),
        ("code", re.compile(r"`([^`]+)`")),
    ]

    while pos < len(text):
        earliest: tuple[int, str, re.Match[str]] | None = None

        for kind, pattern in patterns:
            match = pattern.search(text, pos)
            if match and (earliest is None or match.start() < earliest[0]):
                earliest = (match.start(), kind, match)

        if earliest is None:
            if pos < len(text):
                elements.append({"type": "text", "text": text[pos:]})
            break

        start, kind, match = earliest

        if start > pos:
            elements.append({"type": "text", "text": text[pos:start]})

        if kind == "link":
            elements.append({"type": "link", "text": match.group(1), "url": match.group(2)})
        elif kind == "bold":
            bold_text = match.group(1) or match.group(2)
            elements.append({"type": "text", "text": bold_text, "style": {"bold": True}})
        elif kind == "italic":
            italic_text = match.group(1) or match.group(2)
            elements.append({"type": "text", "text": italic_text, "style": {"italic": True}})
        elif kind == "strike":
            elements.append({"type": "text", "text": match.group(1), "style": {"strike": True}})
        elif kind == "code":
            elements.append({"type": "text", "text": match.group(1), "style": {"code": True}})

        pos = match.end()

    return elements


def _make_section(text: str) -> dict:
    """Create a rich_text_section from text with inline parsing."""
    return {
        "type": "rich_text_section",
        "elements": _parse_inline(text) if text else [{"type": "text", "text": ""}],
    }


def _flush_section(
    lines: list[str], result: list[dict],
) -> None:
    """Flush accumulated paragraph lines as a rich_text_section."""
    if not lines:
        return
    paragraph = "\n".join(lines)
    lines.clear()
    result.append(_make_section(paragraph))


def _flush_list(
    items: list[str], style: str, result: list[dict],
) -> None:
    """Flush accumulated list items as a rich_text_list."""
    if not items:
        return
    result.append({
        "type": "rich_text_list",
        "style": style,
        "elements": [
            {"type": "rich_text_section", "elements": _parse_inline(item)}
            for item in items
        ],
    })
    items.clear()


def _flush_quote(
    lines: list[str], result: list[dict],
) -> None:
    """Flush accumulated blockquote lines as a rich_text_quote."""
    if not lines:
        return
    quote_text = "\n".join(lines)
    lines.clear()
    result.append({
        "type": "rich_text_quote",
        "elements": _parse_inline(quote_text),
    })


def markdown_to_rich_text_blocks(markdown: str) -> list[dict]:
    """Convert markdown string to Slack rich_text block elements.

    Returns a list of rich_text sub-elements (rich_text_section,
    rich_text_list, rich_text_preformatted, rich_text_quote) that
    should be placed inside a ``{"type": "rich_text", "elements": ...}`` block.
    """
    if not markdown:
        return []

    result: list[dict] = []
    lines = markdown.split("\n")

    para_lines: list[str] = []
    list_items: list[str] = []
    list_style: str = "bullet"
    quote_lines: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    code_lang = ""

    def _flush_para() -> None:
        _flush_section(para_lines, result)

    def _flush_lst() -> None:
        _flush_list(list_items, list_style, result)

    def _flush_qt() -> None:
        _flush_quote(quote_lines, result)

    for line in lines:
        stripped = line.strip()

        # Fenced code block toggle
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                _flush_para()
                _flush_lst()
                _flush_qt()
                result.append({
                    "type": "rich_text_preformatted",
                    "elements": [{"type": "text", "text": "\n".join(code_lines)}],
                    **({"language": code_lang} if code_lang else {}),
                })
                code_lines.clear()
                code_lang = ""
                continue
            else:
                in_code_block = True
                _flush_para()
                _flush_lst()
                _flush_qt()
                code_lang = stripped[3:].strip()
                continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            _flush_para()
            _flush_lst()
            _flush_qt()
            continue

        # Empty line — flush all active blocks
        if not stripped:
            _flush_para()
            _flush_lst()
            _flush_qt()
            continue

        # Headings
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            _flush_para()
            _flush_lst()
            _flush_qt()
            heading_text = heading_match.group(2)
            result.append({
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": heading_text, "style": {"bold": True}}],
            })
            continue

        # Unordered list
        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            _flush_para()
            _flush_qt()
            if list_style != "bullet":
                _flush_lst()
            list_style = "bullet"
            list_items.append(bullet_match.group(1))
            continue

        # Ordered list
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_match:
            _flush_para()
            _flush_qt()
            if list_style != "ordered":
                _flush_lst()
            list_style = "ordered"
            list_items.append(ordered_match.group(1))
            continue

        # Blockquote
        quote_match = re.match(r"^>\s?(.*)$", stripped)
        if quote_match:
            _flush_para()
            _flush_lst()
            quote_lines.append(quote_match.group(1))
            continue

        # Default — paragraph text
        _flush_lst()
        _flush_qt()
        para_lines.append(stripped)

    # Flush any remaining state
    _flush_para()
    _flush_lst()
    _flush_qt()
    if in_code_block and code_lines:
        result.append({
            "type": "rich_text_preformatted",
            "elements": [{"type": "text", "text": "\n".join(code_lines)}],
            **({"language": code_lang} if code_lang else {}),
        })

    return result
