"""Tests for structured agent memory records."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.memory_record import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)

CREATED_AT = datetime(
    2026,
    8,
    3,
    9,
    0,
    tzinfo=UTC,
)


def make_memory(
    **overrides: object,
) -> MemoryRecord:
    """Create one valid semantic user memory."""

    values: dict[str, object] = {
        "memory_id": "mem-001",
        "kind": MemoryKind.SEMANTIC,
        "scope": MemoryScope.USER,
        "source": MemorySource.USER_STATEMENT,
        "content": (
            "The user prefers verified commands "
            "instead of guesses."
        ),
        "subject_id": "user-001",
        "tags": ["preference", "workflow"],
        "importance": 0.8,
        "confidence": 1.0,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    values.update(overrides)

    return MemoryRecord(**values)


def test_memory_accepts_valid_semantic_record() -> None:
    memory = make_memory()

    assert memory.memory_id == "mem-001"
    assert memory.kind is MemoryKind.SEMANTIC
    assert memory.scope is MemoryScope.USER
    assert memory.importance == 0.8


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        (
            "memory_id",
            "",
            "memory ID must not be blank",
        ),
        (
            "memory_id",
            "   ",
            "memory ID must not be blank",
        ),
        (
            "content",
            "",
            "memory content must not be blank",
        ),
        (
            "content",
            "   ",
            "memory content must not be blank",
        ),
        (
            "subject_id",
            "   ",
            "subject_id must not be blank",
        ),
    ],
)
def test_memory_rejects_blank_values(
    field_name: str,
    value: str,
    error: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=error,
    ):
        make_memory(**{field_name: value})


def test_memory_rejects_duplicate_tags_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="memory tags must be unique",
    ):
        make_memory(
            tags=[
                "Preference",
                "preference",
            ]
        )


def test_memory_rejects_blank_tag() -> None:
    with pytest.raises(
        ValidationError,
        match="memory tags must not be blank",
    ):
        make_memory(
            tags=["workflow", "   "]
        )


def test_session_scope_requires_session_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires session_id",
    ):
        make_memory(
            scope=MemoryScope.SESSION,
            subject_id=None,
            session_id=None,
        )


def test_user_scope_requires_subject_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires subject_id",
    ):
        make_memory(
            scope=MemoryScope.USER,
            subject_id=None,
        )


def test_project_scope_requires_project_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires project_id",
    ):
        make_memory(
            scope=MemoryScope.PROJECT,
            subject_id=None,
            project_id=None,
        )


def test_global_scope_requires_no_specific_identifier() -> None:
    memory = make_memory(
        scope=MemoryScope.GLOBAL,
        subject_id=None,
    )

    assert memory.scope is MemoryScope.GLOBAL


@pytest.mark.parametrize(
    "source",
    [
        MemorySource.TOOL_RESULT,
        MemorySource.AGENT_INFERENCE,
        MemorySource.IMPORTED_DOCUMENT,
    ],
)
def test_derived_source_requires_reference(
    source: MemorySource,
) -> None:
    with pytest.raises(
        ValidationError,
        match="requires source_reference",
    ):
        make_memory(
            source=source,
            source_reference=None,
        )


def test_tool_result_accepts_source_reference() -> None:
    memory = make_memory(
        source=MemorySource.TOOL_RESULT,
        source_reference="tool-run-123",
    )

    assert memory.source_reference == "tool-run-123"


def test_memory_rejects_naive_datetime() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        make_memory(
            created_at=CREATED_AT.replace(tzinfo=None)
        )


def test_memory_rejects_non_utc_datetime() -> None:
    non_utc = datetime.now().astimezone()

    if non_utc.utcoffset() == timedelta(0):
        pytest.skip(
            "local environment already uses UTC"
        )

    with pytest.raises(
        ValidationError,
        match="created_at must use UTC",
    ):
        make_memory(
            created_at=non_utc,
            updated_at=non_utc,
        )


def test_updated_at_must_not_precede_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="updated_at must not precede created_at",
    ):
        make_memory(
            updated_at=CREATED_AT
            - timedelta(seconds=1),
        )


def test_last_accessed_at_must_not_precede_creation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "last_accessed_at must not precede created_at"
        ),
    ):
        make_memory(
            last_accessed_at=CREATED_AT
            - timedelta(seconds=1),
        )


def test_expiration_must_be_after_creation() -> None:
    with pytest.raises(
        ValidationError,
        match="expires_at must be later than created_at",
    ):
        make_memory(
            expires_at=CREATED_AT,
        )


def test_memory_accepts_future_expiration() -> None:
    memory = make_memory(
        expires_at=CREATED_AT + timedelta(days=30),
    )

    assert memory.expires_at == (
        CREATED_AT + timedelta(days=30)
    )


def test_working_memory_can_be_session_scoped() -> None:
    memory = make_memory(
        kind=MemoryKind.WORKING,
        scope=MemoryScope.SESSION,
        subject_id=None,
        session_id="session-001",
        expires_at=CREATED_AT + timedelta(hours=1),
    )

    assert memory.kind is MemoryKind.WORKING
    assert memory.session_id == "session-001"


def test_procedural_memory_can_be_project_scoped() -> None:
    memory = make_memory(
        kind=MemoryKind.PROCEDURAL,
        scope=MemoryScope.PROJECT,
        subject_id=None,
        project_id="agentic-ai-lab",
        content=(
            "Run regression tests with "
            "python -m pytest -q."
        ),
    )

    assert memory.kind is MemoryKind.PROCEDURAL
    assert memory.project_id == "agentic-ai-lab"


def test_memory_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        make_memory(
            unknown_field="not allowed"
        )
