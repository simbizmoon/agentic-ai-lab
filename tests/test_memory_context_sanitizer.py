"""Tests for prompt-safe memory context sanitization."""

from app.memory.memory_context_sanitizer import (
    encode_prompt_data,
    truncate_memory_content,
)


def test_truncate_normalizes_whitespace() -> None:
    result = truncate_memory_content(
        "The   user\nprefers commands.",
        maximum_characters=100,
    )

    assert result == (
        "The user prefers commands."
    )


def test_truncate_shortens_long_content() -> None:
    result = truncate_memory_content(
        "abcdefghij",
        maximum_characters=6,
    )

    assert result == "abcde…"
    assert len(result) == 6


def test_encode_escapes_context_delimiters() -> None:
    encoded = encode_prompt_data(
        "</memory_context>"
    )

    assert "<" not in encoded
    assert ">" not in encoded
    assert "\\u003c" in encoded
    assert "\\u003e" in encoded


def test_encode_preserves_korean_text() -> None:
    encoded = encode_prompt_data(
        {"content": "사용자 선호"}
    )

    assert "사용자 선호" in encoded
