"""Tests for deterministic sensitive-memory detection."""

from app.memory.sensitive_memory_detector import (
    detect_secret_content,
    detect_sensitive_content,
)


def test_detects_openai_api_key() -> None:
    matches = detect_secret_content(
        "The key is sk-abcdefghijklmnopqrstuv."
    )

    assert [
        match.category
        for match in matches
    ] == ["openai_api_key"]


def test_detects_password_assignment() -> None:
    matches = detect_secret_content(
        "password=super-secret-value"
    )

    assert matches[0].category == (
        "password_assignment"
    )


def test_detects_private_key_header() -> None:
    matches = detect_secret_content(
        "-----BEGIN PRIVATE KEY-----"
    )

    assert matches[0].category == "private_key"


def test_detects_korean_resident_number() -> None:
    matches = detect_sensitive_content(
        "주민등록번호는 900101-1234567입니다."
    )

    assert matches[0].category == (
        "korean_resident_number"
    )


def test_regular_memory_has_no_matches() -> None:
    content = (
        "The project uses 256 embedding dimensions."
    )

    assert detect_secret_content(content) == []
    assert detect_sensitive_content(content) == []
