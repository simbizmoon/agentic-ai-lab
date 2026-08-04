"""Tests for research-agent task result and failure schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.research_agent import (
    ResearchAgentIdentity,
    ResearchAgentRole,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentStatus,
    ResearchAgentTaskAssignment,
)
from app.schemas.research_agent_capability import (
    ResearchAgentCapability,
    ResearchAgentCapabilityProfile,
)
from app.schemas.research_agent_result import (
    ResearchAgentExecutionMetrics,
    ResearchAgentFailure,
    ResearchAgentFailureCategory,
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)


def identity(
    *,
    agent_id: str,
    role: ResearchAgentRole,
    name: str,
) -> ResearchAgentIdentity:
    """Return one valid research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager capability profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )


def assignee() -> ResearchAgentIdentity:
    """Return one search specialist."""

    return identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one valid task assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "research_task_id": "task-001",
        "assigner_profile": manager_profile(),
        "assignee": assignee(),
        "required_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "required_capabilities": [
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        "title": "Search sources",
        "objective": "Find authoritative sources.",
        "instructions": [
            "Use the approved query set."
        ],
        "expected_output_type": (
            "research_source_candidate_set"
        ),
        "acceptance_criteria": [
            "Return at least one candidate."
        ],
        "status": (
            ResearchAgentAssignmentStatus.IN_PROGRESS
        ),
        "attempt_number": 1,
        "maximum_attempts": 2,
        "created_at": datetime(
            2026,
            8,
            4,
            4,
            30,
            tzinfo=UTC,
        ),
    }
    values.update(overrides)

    return ResearchAgentTaskAssignment.model_validate(
        values
    )


def output_reference(
    **overrides: object,
) -> ResearchAgentOutputReference:
    """Return one valid output reference."""

    values: dict[str, object] = {
        "name": "source-candidates",
        "output_type": (
            "research_source_candidate_set"
        ),
        "reference_id": "candidate-set-001",
        "primary": True,
        "metadata": {
            "workspace_layer": "candidate_set",
        },
    }
    values.update(overrides)

    return ResearchAgentOutputReference.model_validate(
        values
    )


def retryable_failure() -> ResearchAgentFailure:
    """Return one retryable failure."""

    return ResearchAgentFailure(
        category=ResearchAgentFailureCategory.TOOL,
        code="SEARCH_PROVIDER_UNAVAILABLE",
        message="The source provider was unavailable.",
        retryable=True,
        retry_reason=(
            "A temporary provider outage may recover."
        ),
        failed_stage="source_search",
        details={
            "provider": "test-provider",
        },
    )


def result(
    **overrides: object,
) -> ResearchAgentTaskResult:
    """Return one successful agent result."""

    values: dict[str, object] = {
        "result_id": "result-001",
        "assignment": assignment(),
        "agent": assignee(),
        "status": ResearchAgentResultStatus.SUCCEEDED,
        "summary": "Found one authoritative source.",
        "outputs": [
            output_reference(),
        ],
        "payload": {
            "candidate_count": 1,
        },
        "metrics": ResearchAgentExecutionMetrics(
            duration_ms=120,
            tool_call_count=1,
            input_token_count=20,
            output_token_count=30,
            source_count=1,
        ),
        "completed_at": datetime(
            2026,
            8,
            4,
            4,
            31,
            tzinfo=UTC,
        ),
        "metadata": {
            "executor": "fake-search-agent",
        },
    }
    values.update(overrides)

    return ResearchAgentTaskResult.model_validate(
        values
    )


def test_output_reference_accepts_valid_values() -> None:
    value = output_reference()

    assert value.reference_id == "candidate-set-001"
    assert value.primary is True


@pytest.mark.parametrize(
    "field_name",
    [
        "name",
        "output_type",
        "reference_id",
    ],
)
def test_output_reference_rejects_blank_text(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        output_reference(**{field_name: " "})


def test_metrics_calculates_total_tokens() -> None:
    metrics = ResearchAgentExecutionMetrics(
        input_token_count=20,
        output_token_count=30,
    )

    assert metrics.total_token_count == 50


def test_failure_accepts_retryable_values() -> None:
    value = retryable_failure()

    assert value.retryable is True
    assert value.failed_stage == "source_search"


def test_retryable_failure_requires_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retryable failure must include retry_reason"
        ),
    ):
        ResearchAgentFailure(
            category=ResearchAgentFailureCategory.TOOL,
            code="TOOL_FAILED",
            message="Tool failed.",
            retryable=True,
        )


def test_non_retryable_failure_rejects_retry_reason() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "non-retryable failure must not include "
            "retry_reason"
        ),
    ):
        ResearchAgentFailure(
            category=ResearchAgentFailureCategory.INTERNAL,
            code="INTERNAL_ERROR",
            message="Internal failure.",
            retryable=False,
            retry_reason="Retry later.",
        )


def test_successful_result_accepts_output() -> None:
    value = result()

    assert value.succeeded is True
    assert value.can_retry is False
    assert value.primary_output() is not None


def test_result_rejects_wrong_agent() -> None:
    wrong_agent = identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "result agent must match assignment assignee"
        ),
    ):
        result(agent=wrong_agent)


def test_successful_result_requires_output() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "successful result must include output"
        ),
    ):
        result(outputs=[])


def test_successful_result_rejects_failure() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "successful result must not include failure"
        ),
    ):
        result(failure=retryable_failure())


def test_failed_result_requires_failure() -> None:
    with pytest.raises(
        ValidationError,
        match="failed result must include failure",
    ):
        result(
            status=ResearchAgentResultStatus.FAILED,
            outputs=[],
        )


def test_failed_result_rejects_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match="failed result must not include outputs",
    ):
        result(
            status=ResearchAgentResultStatus.FAILED,
            failure=retryable_failure(),
        )


def test_failed_result_can_retry() -> None:
    value = result(
        status=ResearchAgentResultStatus.FAILED,
        outputs=[],
        failure=retryable_failure(),
    )

    assert value.succeeded is False
    assert value.can_retry is True
    assert value.primary_output() is None


def test_retryable_failure_requires_remaining_attempts() -> None:
    final_assignment = assignment(
        attempt_number=2,
        maximum_attempts=2,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "retryable failure requires remaining attempts"
        ),
    ):
        result(
            assignment=final_assignment,
            status=ResearchAgentResultStatus.FAILED,
            outputs=[],
            failure=retryable_failure(),
        )


def test_partial_result_requires_output_and_failure() -> None:
    value = result(
        status=ResearchAgentResultStatus.PARTIAL,
        failure=retryable_failure(),
    )

    assert value.outputs
    assert value.failure is not None


def test_cancelled_result_requires_cancelled_failure() -> None:
    wrong_failure = ResearchAgentFailure(
        category=ResearchAgentFailureCategory.INTERNAL,
        code="CANCELLED",
        message="Execution was cancelled.",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "cancelled result failure category "
            "must be cancelled"
        ),
    ):
        result(
            status=ResearchAgentResultStatus.CANCELLED,
            outputs=[],
            failure=wrong_failure,
        )


def test_cancelled_result_accepts_cancelled_failure() -> None:
    failure = ResearchAgentFailure(
        category=ResearchAgentFailureCategory.CANCELLED,
        code="USER_CANCELLED",
        message="The assignment was cancelled.",
    )

    value = result(
        status=ResearchAgentResultStatus.CANCELLED,
        outputs=[],
        failure=failure,
    )

    assert value.status is ResearchAgentResultStatus.CANCELLED


def test_result_rejects_duplicate_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "outputs must not contain duplicate references"
        ),
    ):
        result(
            outputs=[
                output_reference(),
                output_reference(
                    name="duplicate",
                    primary=False,
                ),
            ]
        )


def test_result_rejects_multiple_primary_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "result must not contain multiple primary outputs"
        ),
    ):
        result(
            outputs=[
                output_reference(),
                output_reference(
                    name="second-output",
                    output_type="other_output",
                    reference_id="other-001",
                    primary=True,
                ),
            ]
        )


def test_primary_output_returns_only_output() -> None:
    value = result(
        outputs=[
            output_reference(primary=False)
        ]
    )

    primary = value.primary_output()

    assert primary is not None
    assert primary.reference_id == "candidate-set-001"


def test_primary_output_returns_none_for_ambiguous_outputs() -> None:
    value = result(
        outputs=[
            output_reference(primary=False),
            output_reference(
                name="secondary",
                output_type="search_metadata",
                reference_id="metadata-001",
                primary=False,
            ),
        ]
    )

    assert value.primary_output() is None


def test_result_rejects_blank_payload_key() -> None:
    with pytest.raises(
        ValidationError,
        match="payload keys must not be blank",
    ):
        result(
            payload={
                " ": "value",
            }
        )


def test_result_is_frozen() -> None:
    value = result()

    with pytest.raises(ValidationError):
        value.summary = "Changed"
