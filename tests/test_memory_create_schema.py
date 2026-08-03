"""Tests for agent memory creation values."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
    MemorySource,
)

FUTURE = datetime(
    2026,
    9,
    1,
    0,
    0,
    tzinfo=UTC,
)


def valid_request(
    **overrides: object,
) -> MemoryCreate:
    """Create one valid semantic user-memory request."""

    values: dict[str, object] = {
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": "The user prefers verified commands.",
        "subject_id": "user-001",
        "tags": ["preference"],
        "importance": 0.8,
        "confidence": 1.0,
    }
    values.update(overrides)

    return MemoryCreate(**values)


def test_create_accepts_valid_request() -> None:
    request = valid_request()

    assert request.kind is MemoryKind.SEMANTIC
    assert request.subject_id == "user-001"


@pytest.mark.parametrize(
    "content",
    ["", "   ", "\n\t"],
)
def test_create_rejects_blank_content(
    content: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="memory content must not be blank",
    ):
        valid_request(content=content)


def test_create_rejects_duplicate_tags() -> None:
    with pytest.raises(
        ValidationError,
        match="memory tags must be unique",
    ):
        valid_request(
            tags=["Preference", "preference"]
        )


def test_create_rejects_blank_optional_identifier() -> None:
    with pytest.raises(
        ValidationError,
        match="subject_id must not be blank",
    ):
        valid_request(subject_id="   ")


def test_session_scope_requires_session_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires session_id",
    ):
        valid_request(
            scope=MemoryScope.SESSION,
            subject_id=None,
            session_id=None,
        )


def test_project_scope_requires_project_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires project_id",
    ):
        valid_request(
            scope=MemoryScope.PROJECT,
            subject_id=None,
            project_id=None,
        )


def test_derived_source_requires_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="requires source_reference",
    ):
        valid_request(
            source=MemorySource.AGENT_INFERENCE,
        )


def test_create_accepts_utc_expiration() -> None:
    request = valid_request(expires_at=FUTURE)

    assert request.expires_at == FUTURE


def test_create_rejects_naive_expiration() -> None:
    with pytest.raises(
        ValidationError,
        match="expires_at must be timezone-aware",
    ):
        valid_request(
            expires_at=FUTURE.replace(tzinfo=None)
        )


def test_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        valid_request(memory_id="caller-must-not-set-this")
