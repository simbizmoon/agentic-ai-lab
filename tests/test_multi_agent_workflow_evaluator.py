"""Tests for deterministic multi-agent workflow evaluation."""

from datetime import UTC, datetime

import pytest

from app.evals.multi_agent_workflow_evaluator import (
    MultiAgentWorkflowEvaluator,
)
from app.evals.multi_agent_workflow_evaluator_error import (
    MultiAgentWorkflowEvaluatorError,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchStage,
    MultiAgentResearchStageResult,
    MultiAgentResearchStatus,
    MultiAgentResearchWorkflowResult,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoopResult,
    ReviewRevisionLoopStatus,
    ReviewRevisionRound,
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
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)


def identity(
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    """Return one agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def capability(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    """Return primary capability for one role."""

    mapping = {
        ResearchAgentRole.SEARCH_SPECIALIST: (
            ResearchAgentCapability.SEARCH_SOURCES
        ),
        ResearchAgentRole.SOURCE_READER: (
            ResearchAgentCapability.READ_SOURCES
        ),
        ResearchAgentRole.EVIDENCE_ANALYST: (
            ResearchAgentCapability.EXTRACT_EVIDENCE
        ),
        ResearchAgentRole.CLAIM_ANALYST: (
            ResearchAgentCapability.BUILD_CLAIMS
        ),
        ResearchAgentRole.SYNTHESIS_SPECIALIST: (
            ResearchAgentCapability.SYNTHESIZE_REPORT
        ),
        ResearchAgentRole.QUALITY_REVIEWER: (
            ResearchAgentCapability.EVALUATE_REPORT
        ),
    }

    return mapping[role]


def assignment(
    *,
    assignment_id: str,
    agent_id: str,
    role: ResearchAgentRole,
    parent_assignment_id: str | None = None,
) -> ResearchAgentTaskAssignment:
    """Return one deterministic assignment."""

    manager = identity(
        "agent-manager-001",
        ResearchAgentRole.MANAGER,
    )
    assignee = identity(agent_id, role)

    manager_profile = ResearchAgentCapabilityProfile(
        profile_id=f"profile-manager-{role.value}",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[role],
    )

    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile,
        assignee=assignee,
        required_role=role,
        required_capabilities=[capability(role)],
        title=f"Execute {role.value}",
        objective="Complete the workflow stage.",
        instructions=["Return a structured result."],
        expected_output_type="research_output",
        acceptance_criteria=["Return one primary output."],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
        parent_assignment_id=parent_assignment_id,
    )


def result(
    assignment_value: ResearchAgentTaskAssignment,
    *,
    result_id: str,
    status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
) -> ResearchAgentTaskResult:
    """Return one deterministic task result."""

    return ResearchAgentTaskResult(
        result_id=result_id,
        assignment=assignment_value,
        agent=assignment_value.assignee,
        status=status,
        summary="Workflow stage completed.",
        outputs=(
            [
                ResearchAgentOutputReference(
                    name="workflow-output",
                    output_type="research_output",
                    reference_id=f"output-{result_id}",
                    primary=True,
                )
            ]
            if status is not ResearchAgentResultStatus.FAILED
            else []
        ),
        metrics=ResearchAgentExecutionMetrics(),
        completed_at=datetime(
            2026,
            8,
            4,
            17,
            0,
            tzinfo=UTC,
        ),
    )


def valid_workflow() -> MultiAgentResearchWorkflowResult:
    """Return one valid completed workflow."""

    search = assignment(
        assignment_id="assignment-search",
        agent_id="agent-search",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
    )
    reader = assignment(
        assignment_id="assignment-reader",
        agent_id="agent-reader",
        role=ResearchAgentRole.SOURCE_READER,
        parent_assignment_id=search.assignment_id,
    )
    evidence = assignment(
        assignment_id="assignment-evidence",
        agent_id="agent-evidence",
        role=ResearchAgentRole.EVIDENCE_ANALYST,
        parent_assignment_id=reader.assignment_id,
    )
    claim = assignment(
        assignment_id="assignment-claim",
        agent_id="agent-claim",
        role=ResearchAgentRole.CLAIM_ANALYST,
        parent_assignment_id=evidence.assignment_id,
    )
    synthesis = assignment(
        assignment_id="assignment-synthesis",
        agent_id="agent-synthesis",
        role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
        parent_assignment_id=claim.assignment_id,
    )
    review = assignment(
        assignment_id="assignment-review",
        agent_id="agent-review",
        role=ResearchAgentRole.QUALITY_REVIEWER,
        parent_assignment_id=synthesis.assignment_id,
    )

    synthesis_result = result(
        synthesis,
        result_id="result-synthesis",
    )
    review_result = result(
        review,
        result_id="result-review",
    )

    loop_round = ReviewRevisionRound(
        round_number=1,
        synthesis_assignment=synthesis,
        synthesis_result=synthesis_result,
        review_assignment=review,
        review_result=review_result,
    )
    loop_result = ReviewRevisionLoopResult(
        loop_id="review-loop-001",
        status=ReviewRevisionLoopStatus.APPROVED,
        rounds=[loop_round],
        maximum_revision_rounds=2,
        revision_rounds_used=0,
        final_synthesis_result=synthesis_result,
        final_review_result=review_result,
        summary="Report approved.",
    )

    return MultiAgentResearchWorkflowResult(
        request_id="research-001",
        workspace_id="workspace-001",
        status=MultiAgentResearchStatus.COMPLETED,
        stages=[
            MultiAgentResearchStageResult(
                stage=MultiAgentResearchStage.SEARCH,
                assignment=search,
                result=result(
                    search,
                    result_id="result-search",
                ),
            ),
            MultiAgentResearchStageResult(
                stage=MultiAgentResearchStage.SOURCE_READING,
                assignment=reader,
                result=result(
                    reader,
                    result_id="result-reader",
                ),
            ),
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .EVIDENCE_EXTRACTION
                ),
                assignment=evidence,
                result=result(
                    evidence,
                    result_id="result-evidence",
                ),
            ),
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .CLAIM_CONSTRUCTION
                ),
                assignment=claim,
                result=result(
                    claim,
                    result_id="result-claim",
                ),
            ),
        ],
        review_revision_result=loop_result,
        final_result=review_result,
        summary="Workflow completed.",
    )


def evaluator(
    *,
    minimum_score: float = 1.0,
) -> MultiAgentWorkflowEvaluator:
    """Return one deterministic workflow evaluator."""

    return MultiAgentWorkflowEvaluator(
        minimum_score=minimum_score,
        evaluation_id_factory=(
            lambda: "workflow-evaluation-001"
        ),
        finding_id_factory=(
            lambda index: f"finding-{index:03d}"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_valid_workflow_passes() -> None:
    value = evaluator().evaluate(valid_workflow())

    assert value.passed is True
    assert value.score.score == pytest.approx(1.0)
    assert value.expected_stage_count == 4
    assert value.actual_stage_count == 4
    assert value.valid_stage_count == 4
    assert value.valid_transition_count == 3
    assert value.review_round_count == 1
    assert value.violations == []


def test_invalid_parent_link_fails() -> None:
    workflow = valid_workflow()
    values = workflow.model_dump(mode="python")
    values["stages"][1]["assignment"][
        "parent_assignment_id"
    ] = "assignment-wrong"
    workflow = MultiAgentResearchWorkflowResult.model_validate(
        values
    )

    value = evaluator().evaluate(workflow)

    assert value.passed is False
    assert any(
        violation.code == "WORKFLOW_PARENT_LINK_INVALID"
        for violation in value.violations
    )


def test_invalid_review_parent_fails() -> None:
    workflow = valid_workflow()
    values = workflow.model_dump(mode="python")
    values["review_revision_result"]["rounds"][0][
        "review_assignment"
    ]["parent_assignment_id"] = "assignment-wrong"
    workflow = MultiAgentResearchWorkflowResult.model_validate(
        values
    )

    value = evaluator().evaluate(workflow)

    assert value.passed is False
    assert any(
        violation.code == "REVIEW_PARENT_LINK_INVALID"
        for violation in value.violations
    )


def test_invalid_round_sequence_fails() -> None:
    workflow = valid_workflow()
    values = workflow.model_dump(mode="python")
    values["review_revision_result"]["rounds"][0][
        "round_number"
    ] = 2
    workflow = MultiAgentResearchWorkflowResult.model_validate(
        values
    )

    value = evaluator().evaluate(workflow)

    assert value.passed is False
    assert any(
        violation.code
        == "REVIEW_ROUND_SEQUENCE_INVALID"
        for violation in value.violations
    )


def test_invalid_termination_status_fails() -> None:
    workflow = valid_workflow().model_copy(
        update={
            "status": (
                MultiAgentResearchStatus.REPORT_REJECTED
            )
        }
    )

    value = evaluator().evaluate(workflow)

    assert value.passed is False
    assert any(
        violation.code == "WORKFLOW_TERMINATION_INVALID"
        for violation in value.violations
    )


def test_evaluator_rejects_invalid_minimum_score() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "minimum_score must be between 0 and 1"
        ),
    ):
        MultiAgentWorkflowEvaluator(
            minimum_score=1.1
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = MultiAgentWorkflowEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        MultiAgentWorkflowEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(valid_workflow())
