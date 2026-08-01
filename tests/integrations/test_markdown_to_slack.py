from src.integrations.markdown_to_slack import markdown_to_rich_text_blocks


def test_empty_input():
    assert markdown_to_rich_text_blocks("") == []


def test_heading():
    result = markdown_to_rich_text_blocks("# Hello World")
    assert len(result) == 1
    section = result[0]
    assert section["type"] == "rich_text_section"
    assert section["elements"][0]["text"] == "Hello World"
    assert section["elements"][0]["style"]["bold"] is True


def test_heading_levels():
    result = markdown_to_rich_text_blocks("## H2\n### H3\n#### H4")
    assert len(result) == 3
    for section in result:
        assert section["type"] == "rich_text_section"
        assert section["elements"][0]["style"]["bold"] is True


def test_fenced_code_block():
    md = "```python\nprint('hello')\n```"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    assert result[0]["type"] == "rich_text_preformatted"
    assert result[0]["language"] == "python"
    assert result[0]["elements"][0]["text"] == "print('hello')"


def test_fenced_code_block_no_language():
    md = "```\nsome code\n```"
    result = markdown_to_rich_text_blocks(md)
    assert result[0]["type"] == "rich_text_preformatted"
    assert "language" not in result[0]


def test_fenced_code_block_multiline():
    md = "```\nline1\nline2\nline3\n```"
    result = markdown_to_rich_text_blocks(md)
    assert result[0]["elements"][0]["text"] == "line1\nline2\nline3"


def test_bullet_list():
    md = "- item one\n- item two\n- item three"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    lst = result[0]
    assert lst["type"] == "rich_text_list"
    assert lst["style"] == "bullet"
    assert len(lst["elements"]) == 3
    assert lst["elements"][0]["elements"][0]["text"] == "item one"


def test_bullet_list_asterisk():
    md = "* first\n* second"
    result = markdown_to_rich_text_blocks(md)
    assert result[0]["type"] == "rich_text_list"
    assert result[0]["style"] == "bullet"
    assert len(result[0]["elements"]) == 2


def test_ordered_list():
    md = "1. first\n2. second\n3. third"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    lst = result[0]
    assert lst["type"] == "rich_text_list"
    assert lst["style"] == "ordered"
    assert len(lst["elements"]) == 3
    assert lst["elements"][0]["elements"][0]["text"] == "first"


def test_blockquote():
    md = "> This is a quote\n> continued"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    assert result[0]["type"] == "rich_text_quote"
    assert "This is a quote" in result[0]["elements"][0]["text"]


def test_paragraph():
    md = "This is a paragraph."
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    assert result[0]["type"] == "rich_text_section"
    assert result[0]["elements"][0]["text"] == "This is a paragraph."


def test_inline_bold():
    result = markdown_to_rich_text_blocks("Some **bold** text")
    elements = result[0]["elements"]
    assert elements[0]["text"] == "Some "
    assert elements[1]["text"] == "bold"
    assert elements[1]["style"]["bold"] is True
    assert elements[2]["text"] == " text"


def test_inline_bold_underscore():
    result = markdown_to_rich_text_blocks("Some __bold__ text")
    elements = result[0]["elements"]
    assert elements[1]["text"] == "bold"
    assert elements[1]["style"]["bold"] is True


def test_inline_italic():
    result = markdown_to_rich_text_blocks("Some *italic* text")
    elements = result[0]["elements"]
    assert elements[1]["text"] == "italic"
    assert elements[1]["style"]["italic"] is True


def test_inline_code():
    result = markdown_to_rich_text_blocks("Use `print()` here")
    elements = result[0]["elements"]
    assert elements[1]["text"] == "print()"
    assert elements[1]["style"]["code"] is True


def test_inline_strikethrough():
    result = markdown_to_rich_text_blocks("Some ~~deleted~~ text")
    elements = result[0]["elements"]
    assert elements[1]["text"] == "deleted"
    assert elements[1]["style"]["strike"] is True


def test_inline_link():
    result = markdown_to_rich_text_blocks("Visit [Google](https://google.com)")
    elements = result[0]["elements"]
    link = elements[1]
    assert link["type"] == "link"
    assert link["text"] == "Google"
    assert link["url"] == "https://google.com"


def test_horizontal_rule():
    md = "before\n---\nafter"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 2
    assert result[0]["type"] == "rich_text_section"
    assert result[1]["type"] == "rich_text_section"


def test_mixed_content():
    md = """# Title

Some paragraph text.

- bullet one
- bullet two

```python
code here
```

> a quote"""

    result = markdown_to_rich_text_blocks(md)
    types = [r["type"] for r in result]
    assert "rich_text_section" in types
    assert "rich_text_list" in types
    assert "rich_text_preformatted" in types
    assert "rich_text_quote" in types


def test_list_then_paragraph():
    md = "- item one\n- item two\n\nA paragraph."
    result = markdown_to_rich_text_blocks(md)
    assert result[0]["type"] == "rich_text_list"
    assert result[1]["type"] == "rich_text_section"


def test_paragraph_then_list():
    md = "A paragraph.\n\n- item one\n- item two"
    result = markdown_to_rich_text_blocks(md)
    assert result[0]["type"] == "rich_text_section"
    assert result[1]["type"] == "rich_text_list"


def test_inline_bold_in_list():
    md = "- **bold item**\n- normal item"
    result = markdown_to_rich_text_blocks(md)
    lst = result[0]
    bold_elem = lst["elements"][0]["elements"][0]
    assert bold_elem["text"] == "bold item"
    assert bold_elem["style"]["bold"] is True


def test_unterminated_code_block():
    md = "```\nsome code\nmore code"
    result = markdown_to_rich_text_blocks(md)
    assert len(result) == 1
    assert result[0]["type"] == "rich_text_preformatted"
    assert "some code" in result[0]["elements"][0]["text"]
