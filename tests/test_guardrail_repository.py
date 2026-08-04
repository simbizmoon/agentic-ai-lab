"""Tests for guardrail records and repositories."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.application.guardrail_record import (
    ApplicationGuardrailDecision,
    ApplicationGuardrailRecord,
    ApplicationGuardrailScope,
    ApplicationGuardrailSeverity,
    ApplicationGuardrailViolationRecord,
)
from app.application.guardrail_repository_error import (
    ApplicationGuardrailAlreadyExistsError,
    ApplicationGuardrailNotFoundError,
    ApplicationGuardrailVersionConflictError,
)
from app.application.guardrail_repository_query import (
    ApplicationGuardrailQuery,
    ApplicationGuardrailSortDirection,
    ApplicationGuardrailSortField,
)
from app.application.in_memory_guardrail_repository import (
    InMemoryApplicationGuardrailRepository,
)

BASE_TIME = datetime(
    2026,
    8,
    5,
    3,
    50,
    tzinfo=UTC,
)


def violation(
    *,
    violation_id: str = "violation-001",
    blocking: bool = True,
) -> ApplicationGuardrailViolationRecord:
    """Return one persistent guardrail violation."""

    return ApplicationGuardrailViolationRecord(
        violation_id=violation_id,
        policy_id="policy-001",
        code="TOOL_NOT_ALLOWED",
        message="The requested tool is not allowed.",
        severity=(
            ApplicationGuardrailSeverity.HIGH
            if blocking
            else ApplicationGuardrailSeverity.MEDIUM
        ),
        blocking=blocking,
        retryable=False,
        remediation="Use an allowed tool.",
        reference_ids=["tool-request-001"],
    )


def record(
    *,
    guardrail_evaluation_id: str,
    scope: ApplicationGuardrailScope = (
        ApplicationGuardrailScope.TOOL
    ),
    decision: ApplicationGuardrailDecision = (
        ApplicationGuardrailDecision.ALLOWED
    ),
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    target_id: str = "source-search",
    target_type: str = "tool_call",
    evaluated_offset: int = 0,
    violations: list[
        ApplicationGuardrailViolationRecord
    ] | None = None,
    record_version: int = 1,
) -> ApplicationGuardrailRecord:
    """Return one persistent guardrail record."""

    items = violations or []

    return ApplicationGuardrailRecord(
        guardrail_evaluation_id=guardrail_evaluation_id,
        scope=scope,
        evaluator_name="tool-permission-guardrail",
        evaluator_version="1.0.0",
        request_id=request_id,
        workspace_id=workspace_id,
        execution_id="execution-001",
        assignment_id="assignment-001",
        agent_id="agent-search-001",
        target_id=target_id,
        target_type=target_type,
        decision=decision,
        violations=items,
        total_violation_count=len(items),
        blocking_violation_count=sum(
            item.blocking
            for item in items
        ),
        warning_violation_count=sum(
            not item.blocking
            for item in items
        ),
        result_payload={
            "decision": decision.value,
        },
        evaluated_at=(
            BASE_TIME
            + timedelta(seconds=evaluated_offset)
        ),
        record_version=record_version,
        summary="Guardrail evaluation completed.",
    )


def repository_with_records(
) -> InMemoryApplicationGuardrailRepository:
    """Return one populated repository."""

    return InMemoryApplicationGuardrailRepository(
        [
            record(
                guardrail_evaluation_id="guardrail-001",
                evaluated_offset=1,
            ),
            record(
                guardrail_evaluation_id="guardrail-002",
                decision=ApplicationGuardrailDecision.WARNED,
                evaluated_offset=2,
                violations=[
                    violation(
                        violation_id="warning-001",
                        blocking=False,
                    )
                ],
            ),
            record(
                guardrail_evaluation_id="guardrail-003",
                decision=ApplicationGuardrailDecision.BLOCKED,
                evaluated_offset=3,
                violations=[
                    violation(
                        violation_id="blocking-001",
                        blocking=True,
                    )
                ],
            ),
            record(
                guardrail_evaluation_id="guardrail-004",
                scope=ApplicationGuardrailScope.INPUT,
                request_id="research-002",
                workspace_id="workspace-002",
                target_id="assignment-002",
                target_type="assignment",
                evaluated_offset=4,
            ),
        ]
    )


def test_allowed_record_properties() -> None:
    value = record(
        guardrail_evaluation_id="guardrail-001"
    )

    assert value.allowed is True
    assert value.blocking_violations == []


def test_blocked_record_properties() -> None:
    value = record(
        guardrail_evaluation_id="guardrail-001",
        decision=ApplicationGuardrailDecision.BLOCKED,
        violations=[violation()],
    )

    assert value.allowed is False
    assert len(value.blocking_violations) == 1


def test_allowed_record_rejects_violations() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "allowed decision must not include violations"
        ),
    ):
        record(
            guardrail_evaluation_id="guardrail-invalid",
            violations=[
                violation(blocking=False)
            ],
        )


def test_warned_record_rejects_blocking_violation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "warned decision requires only nonblocking "
            "violations"
        ),
    ):
        record(
            guardrail_evaluation_id="guardrail-invalid",
            decision=ApplicationGuardrailDecision.WARNED,
            violations=[violation(blocking=True)],
        )


def test_blocked_record_requires_blocking_violation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "blocked decision requires a blocking violation"
        ),
    ):
        record(
            guardrail_evaluation_id="guardrail-invalid",
            decision=ApplicationGuardrailDecision.BLOCKED,
            violations=[
                violation(blocking=False)
            ],
        )


def test_violation_counts_must_match() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "total_violation_count must equal "
            "the number of violations"
        ),
    ):
        ApplicationGuardrailRecord(
            guardrail_evaluation_id="guardrail-invalid",
            scope=ApplicationGuardrailScope.TOOL,
            evaluator_name="tool-guardrail",
            evaluator_version="1.0.0",
            request_id="research-001",
            workspace_id="workspace-001",
            target_id="source-search",
            target_type="tool_call",
            decision=ApplicationGuardrailDecision.WARNED,
            violations=[violation(blocking=False)],
            total_violation_count=0,
            blocking_violation_count=0,
            warning_violation_count=1,
            evaluated_at=BASE_TIME,
            summary="Invalid counts.",
        )


def test_create_and_case_insensitive_get() -> None:
    repository = InMemoryApplicationGuardrailRepository()
    stored = record(
        guardrail_evaluation_id="Guardrail-001"
    )

    repository.create(stored)

    assert repository.get("guardrail-001") == stored
    assert repository.exists("GUARDRAIL-001") is True


def test_duplicate_record_is_rejected() -> None:
    repository = InMemoryApplicationGuardrailRepository(
        [
            record(
                guardrail_evaluation_id="Guardrail-001"
            )
        ]
    )

    with pytest.raises(
        ApplicationGuardrailAlreadyExistsError,
        match=(
            "application guardrail evaluation already "
            "exists: guardrail-001"
        ),
    ):
        repository.create(
            record(
                guardrail_evaluation_id="guardrail-001"
            )
        )


def test_require_missing_record_fails() -> None:
    repository = InMemoryApplicationGuardrailRepository()

    with pytest.raises(
        ApplicationGuardrailNotFoundError,
        match=(
            "application guardrail evaluation was not found: "
            "guardrail-missing"
        ),
    ):
        repository.require("guardrail-missing")


def test_update_uses_optimistic_concurrency() -> None:
    repository = InMemoryApplicationGuardrailRepository()
    original = record(
        guardrail_evaluation_id="guardrail-001"
    )
    repository.create(original)

    updated = original.model_copy(
        update={
            "summary": "Updated guardrail result.",
            "record_version": 2,
        }
    )

    value = repository.update(
        updated,
        expected_version=1,
    )

    assert value.record_version == 2
    assert repository.require(
        "guardrail-001"
    ).summary == "Updated guardrail result."


def test_update_rejects_stale_version() -> None:
    original = record(
        guardrail_evaluation_id="guardrail-001",
        record_version=2,
    )
    repository = InMemoryApplicationGuardrailRepository(
        [original]
    )

    updated = original.model_copy(
        update={"record_version": 3}
    )

    with pytest.raises(
        ApplicationGuardrailVersionConflictError,
        match=(
            "application guardrail version conflict: "
            "expected 1, stored 2"
        ),
    ):
        repository.update(
            updated,
            expected_version=1,
        )


def test_default_list_is_evaluated_at_descending() -> None:
    page = repository_with_records().list(
        ApplicationGuardrailQuery()
    )

    assert [
        item.guardrail_evaluation_id
        for item in page.items
    ] == [
        "guardrail-004",
        "guardrail-003",
        "guardrail-002",
        "guardrail-001",
    ]


def test_filter_by_scope_and_decision() -> None:
    page = repository_with_records().list(
        ApplicationGuardrailQuery(
            scopes=[ApplicationGuardrailScope.TOOL],
            decisions=[
                ApplicationGuardrailDecision.BLOCKED,
            ],
        )
    )

    assert len(page.items) == 1
    assert (
        page.items[0].guardrail_evaluation_id
        == "guardrail-003"
    )


def test_filter_by_context() -> None:
    page = repository_with_records().list(
        ApplicationGuardrailQuery(
            request_id="research-002",
            workspace_id="workspace-002",
            target_id="assignment-002",
            target_type="assignment",
        )
    )

    assert len(page.items) == 1
    assert (
        page.items[0].guardrail_evaluation_id
        == "guardrail-004"
    )


def test_filter_blocking_records() -> None:
    repository = repository_with_records()

    blocking = repository.list(
        ApplicationGuardrailQuery(
            blocking_only=True
        )
    )
    nonblocking = repository.list(
        ApplicationGuardrailQuery(
            blocking_only=False
        )
    )

    assert [
        item.guardrail_evaluation_id
        for item in blocking.items
    ] == ["guardrail-003"]

    assert {
        item.guardrail_evaluation_id
        for item in nonblocking.items
    } == {
        "guardrail-001",
        "guardrail-002",
        "guardrail-004",
    }


def test_sort_violation_count_ascending() -> None:
    page = repository_with_records().list(
        ApplicationGuardrailQuery(
            sort_field=(
                ApplicationGuardrailSortField
                .TOTAL_VIOLATIONS
            ),
            sort_direction=(
                ApplicationGuardrailSortDirection.ASCENDING
            ),
        )
    )

    assert page.items[0].total_violation_count == 0
    assert page.items[-1].total_violation_count == 1


def test_pagination_and_count() -> None:
    repository = repository_with_records()

    page = repository.list(
        ApplicationGuardrailQuery(
            page=2,
            page_size=2,
        )
    )

    assert page.total_items == 4
    assert page.total_pages == 2
    assert len(page.items) == 2
    assert repository.count(
        ApplicationGuardrailQuery()
    ) == 4


def test_query_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="evaluated_from must be timezone-aware",
    ):
        ApplicationGuardrailQuery(
            evaluated_from=datetime(  # noqa: DTZ001
                2026,
                8,
                5,
                3,
                50,
            )
        )


def test_clear_removes_all_records() -> None:
    repository = repository_with_records()

    repository.clear()

    assert repository.count(
        ApplicationGuardrailQuery()
    ) == 0
