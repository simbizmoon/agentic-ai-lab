"""Tests for deterministic output guardrail evaluation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.guardrails.guardrail_result import (
    GuardrailDecision,
)
from app.guardrails.output_guardrail_evaluator import (
    OutputGuardrailEvaluator,
)
from app.guardrails.output_guardrail_evaluator_error import (
    OutputGuardrailEvaluatorError,
)
from app.guardrails.output_guardrail_snapshot import (
    OutputGuardrailSnapshot,
)
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
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)


def identity(
    *,
    agent_id: str = "agent-search-001",
) -> ResearchAgentIdentity:
    """Return one search-specialist identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name="Search specialist",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        description="Find authoritative sources.",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager profile."""

    manager = ResearchAgentIdentity(
        agent_id="agent-manager-001",
        name="Research manager",
        role=ResearchAgentRole.MANAGER,
        description="Coordinate research.",
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


def assignment(
    *,
    assignment_id: str = "assignment-search-001",
    request_id: str = "research-001",
    workspace_id: str = "workspace-001",
    assignee: ResearchAgentIdentity | None = None,
) -> ResearchAgentTaskAssignment:
    """Return one completed search assignment."""

    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id=request_id,
        workspace_id=workspace_id,
        assigner_profile=manager_profile(),
        assignee=assignee or identity(),
        required_role=ResearchAgentRole.SEARCH_SPECIALIST,
        required_capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        title="Search sources",
        objective="Find authoritative sources.",
        instructions=[
            "Return normalized source candidates.",
        ],
        expected_output_type=(
            "research_source_candidate_set"
        ),
        acceptance_criteria=[
            "Return at least one source candidate.",
        ],
        status=ResearchAgentAssignmentStatus.COMPLETED,
        attempt_number=1,
        maximum_attempts=2,
    )


def output(
    *,
    reference_id: str = "source-set-001",
    output_type: str = "research_source_candidate_set",
    primary: bool = True,
) -> ResearchAgentOutputReference:
    """Return one output reference."""

    return ResearchAgentOutputReference(
        name="source candidates",
        output_type=output_type,
        reference_id=reference_id,
        primary=primary,
    )


def result(
    *,
    assignment_value: ResearchAgentTaskAssignment | None = None,
    agent: ResearchAgentIdentity | None = None,
    status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
    outputs: list[
        ResearchAgentOutputReference
    ] | None = None,
) -> ResearchAgentTaskResult:
    """Return one research-agent result."""

    assignment_value = assignment_value or assignment()

    return ResearchAgentTaskResult(
        result_id="result-search-001",
        assignment=assignment_value,
        agent=agent or assignment_value.assignee,
        status=status,
        summary="Search stage completed.",
        outputs=(
            outputs
            if outputs is not None
            else [output()]
        ),
        failure=(
            ResearchAgentFailure(
                category=next(
                    iter(
                        ResearchAgentFailure
                        .model_fields["category"]
                        .annotation
                    )
                ),
                code="TEST_FAILURE",
                message="The test execution failed.",
                retryable=False,
            )
            if status is ResearchAgentResultStatus.FAILED
            else None
        ),
        metrics=ResearchAgentExecutionMetrics(),
        completed_at=datetime(
            2026,
            8,
            4,
            17,
            30,
            tzinfo=UTC,
        ),
    )


def snapshot(
    *,
    result_value: ResearchAgentTaskResult | None = None,
    expected_assignment: (
        ResearchAgentTaskAssignment | None
    ) = None,
    expected_request_id: str = "research-001",
    expected_workspace_id: str = "workspace-001",
    require_primary_output: bool = True,
    require_exactly_one_primary_output: bool = True,
    enforce_expected_output_type: bool = True,
) -> OutputGuardrailSnapshot:
    """Return one output guardrail snapshot."""

    expected_assignment = (
        expected_assignment or assignment()
    )

    return OutputGuardrailSnapshot(
        result=result_value
        or result(
            assignment_value=expected_assignment
        ),
        expected_assignment=expected_assignment,
        expected_request_id=expected_request_id,
        expected_workspace_id=expected_workspace_id,
        require_primary_output=require_primary_output,
        require_exactly_one_primary_output=(
            require_exactly_one_primary_output
        ),
        enforce_expected_output_type=(
            enforce_expected_output_type
        ),
    )


def evaluator() -> OutputGuardrailEvaluator:
    """Return one deterministic output evaluator."""

    return OutputGuardrailEvaluator(
        evaluation_id_factory=(
            lambda: "output-guardrail-evaluation-001"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_valid_success_result_is_allowed() -> None:
    value = evaluator().evaluate(snapshot())

    assert value.decision is GuardrailDecision.ALLOWED
    assert value.allowed is True
    assert value.violations == []


def test_assignment_mismatch_is_blocked() -> None:
    expected = assignment()
    actual = assignment(
        assignment_id="assignment-other"
    )

    value = evaluator().evaluate(
        snapshot(
            result_value=result(
                assignment_value=actual
            ),
            expected_assignment=expected,
        )
    )

    assert value.decision is GuardrailDecision.BLOCKED
    assert any(
        violation.code == "RESULT_ASSIGNMENT_MISMATCH"
        for violation in value.violations
    )


def test_result_schema_rejects_agent_mismatch() -> None:
    expected = assignment()
    other_agent = identity(agent_id="agent-search-002")

    with pytest.raises(
        ValidationError,
        match=(
            "result agent must match assignment assignee"
        ),
    ):
        result(
            assignment_value=expected,
            agent=other_agent,
        )


def test_request_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(expected_request_id="research-other")
    )

    assert any(
        violation.code
        == "RESULT_REQUEST_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_workspace_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            expected_workspace_id="workspace-other"
        )
    )

    assert any(
        violation.code
        == "RESULT_WORKSPACE_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_result_schema_rejects_success_without_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match="successful result must include output",
    ):
        result(outputs=[])


def test_missing_primary_output_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            result_value=result(
                outputs=[
                    output(primary=False),
                ]
            ),
        )
    )

    assert any(
        violation.code == "PRIMARY_OUTPUT_MISSING"
        for violation in value.violations
    )


def test_primary_output_requirement_can_be_disabled() -> None:
    value = evaluator().evaluate(
        snapshot(
            result_value=result(
                outputs=[
                    output(primary=False),
                ]
            ),
            require_primary_output=False,
            require_exactly_one_primary_output=False,
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_result_schema_rejects_multiple_primary_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "result must not contain multiple primary outputs"
        ),
    ):
        result(
            outputs=[
                output(reference_id="output-001"),
                output(reference_id="output-002"),
            ]
        )


def test_wrong_primary_output_type_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            result_value=result(
                outputs=[
                    output(output_type="wrong_output_type"),
                ]
            ),
        )
    )

    assert any(
        violation.code
        == "PRIMARY_OUTPUT_TYPE_MISMATCH"
        for violation in value.violations
    )


def test_output_type_check_can_be_disabled() -> None:
    value = evaluator().evaluate(
        snapshot(
            result_value=result(
                outputs=[
                    output(output_type="wrong_output_type"),
                ]
            ),
            enforce_expected_output_type=False,
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_result_schema_rejects_duplicate_output_references() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "outputs must not contain duplicate references"
        ),
    ):
        result(
            outputs=[
                output(
                    reference_id="output-001",
                    primary=True,
                ),
                output(
                    reference_id="OUTPUT-001",
                    primary=False,
                ),
            ]
        )


def test_result_schema_rejects_failed_result_outputs() -> None:
    with pytest.raises(
        ValidationError,
        match="failed result must not include outputs",
    ):
        result(
            status=ResearchAgentResultStatus.FAILED,
            outputs=[output()],
        )


def test_snapshot_rejects_invalid_primary_configuration() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "exactly-one primary output requires "
            "require_primary_output"
        ),
    ):
        snapshot(
            require_primary_output=False,
            require_exactly_one_primary_output=True,
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = OutputGuardrailEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        OutputGuardrailEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(snapshot())
