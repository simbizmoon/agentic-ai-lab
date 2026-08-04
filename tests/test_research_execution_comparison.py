"""Tests for single-agent and multi-agent comparison."""

from datetime import UTC, datetime

import pytest

from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchStage,
    MultiAgentResearchStageResult,
    MultiAgentResearchStatus,
    MultiAgentResearchWorkflowResult,
)
from app.research.research_execution_comparison import (
    ResearchExecutionComparator,
    ResearchExecutionMode,
    ResearchExecutionPreference,
)
from app.research.research_execution_comparison_error import (
    ResearchExecutionComparisonError,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoopResult,
    ReviewRevisionLoopStatus,
    ReviewRevisionRound,
)
from app.research.single_agent_research_execution import (
    SingleAgentResearchExecution,
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
    *,
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    """Return one research-agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def manager_profile(
    role: ResearchAgentRole,
) -> ResearchAgentCapabilityProfile:
    """Return one manager delegation profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
    )

    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-manager-{role.value}",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[role],
    )


def capability(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    """Return one primary capability for a role."""

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
) -> ResearchAgentTaskAssignment:
    """Return one deterministic assignment."""

    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(role),
        assignee=identity(
            agent_id=agent_id,
            role=role,
        ),
        required_role=role,
        required_capabilities=[
            capability(role)
        ],
        title=f"Execute {role.value}",
        objective="Complete research work.",
        instructions=[
            "Return a structured result."
        ],
        expected_output_type="research_output",
        acceptance_criteria=[
            "Return one primary output."
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


def result(
    *,
    assignment_value: ResearchAgentTaskAssignment,
    result_id: str,
    source_count: int = 0,
    evidence_count: int = 0,
    claim_count: int = 0,
    tool_call_count: int = 1,
    input_tokens: int = 10,
    output_tokens: int = 10,
) -> ResearchAgentTaskResult:
    """Return one successful deterministic task result."""

    return ResearchAgentTaskResult(
        result_id=result_id,
        assignment=assignment_value,
        agent=assignment_value.assignee,
        status=ResearchAgentResultStatus.SUCCEEDED,
        summary="Research work completed.",
        outputs=[
            ResearchAgentOutputReference(
                name="research-output",
                output_type="research_output",
                reference_id=f"output-{result_id}",
                primary=True,
            )
        ],
        metrics=ResearchAgentExecutionMetrics(
            tool_call_count=tool_call_count,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            source_count=source_count,
            evidence_count=evidence_count,
            claim_count=claim_count,
        ),
        completed_at=datetime(
            2026,
            8,
            4,
            11,
            0,
            tzinfo=UTC,
        ),
    )


def single_execution(
    *,
    traceable_source_count: int = 0,
    traceable_evidence_count: int = 0,
    traceable_claim_count: int = 0,
    input_tokens: int = 20,
    output_tokens: int = 20,
) -> SingleAgentResearchExecution:
    """Return one normalized single-agent execution."""

    single_assignment = assignment(
        assignment_id="assignment-single-001",
        agent_id="agent-synthesis-001",
        role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
    )
    single_result = result(
        assignment_value=single_assignment,
        result_id="single-001",
        source_count=traceable_source_count,
        evidence_count=traceable_evidence_count,
        claim_count=traceable_claim_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return SingleAgentResearchExecution(
        request_id="research-001",
        workspace_id="workspace-001",
        result=single_result,
        execution_step_count=1,
        revision_round_count=0,
        traceable_source_count=(
            traceable_source_count
        ),
        traceable_evidence_count=(
            traceable_evidence_count
        ),
        traceable_claim_count=(
            traceable_claim_count
        ),
    )


def multi_execution() -> MultiAgentResearchWorkflowResult:
    """Return one complete multi-agent execution."""

    search_assignment = assignment(
        assignment_id="assignment-search-001",
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
    )
    reader_assignment = assignment(
        assignment_id="assignment-reader-001",
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
    )
    evidence_assignment = assignment(
        assignment_id="assignment-evidence-001",
        agent_id="agent-evidence-001",
        role=ResearchAgentRole.EVIDENCE_ANALYST,
    )
    claim_assignment = assignment(
        assignment_id="assignment-claim-001",
        agent_id="agent-claim-001",
        role=ResearchAgentRole.CLAIM_ANALYST,
    )
    synthesis_assignment = assignment(
        assignment_id="assignment-synthesis-001",
        agent_id="agent-synthesis-001",
        role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
    )
    review_assignment = assignment(
        assignment_id="assignment-review-001",
        agent_id="agent-quality-001",
        role=ResearchAgentRole.QUALITY_REVIEWER,
    )

    search_result = result(
        assignment_value=search_assignment,
        result_id="search-001",
        source_count=4,
        input_tokens=10,
        output_tokens=10,
    )
    reader_result = result(
        assignment_value=reader_assignment,
        result_id="reader-001",
        source_count=4,
        input_tokens=10,
        output_tokens=10,
    )
    evidence_result = result(
        assignment_value=evidence_assignment,
        result_id="evidence-001",
        source_count=4,
        evidence_count=6,
        input_tokens=10,
        output_tokens=10,
    )
    claim_result = result(
        assignment_value=claim_assignment,
        result_id="claim-001",
        source_count=4,
        evidence_count=6,
        claim_count=3,
        input_tokens=10,
        output_tokens=10,
    )
    synthesis_result = result(
        assignment_value=synthesis_assignment,
        result_id="synthesis-001",
        source_count=4,
        evidence_count=6,
        claim_count=3,
        input_tokens=10,
        output_tokens=10,
    )
    review_result = result(
        assignment_value=review_assignment,
        result_id="review-001",
        source_count=4,
        evidence_count=6,
        claim_count=3,
        input_tokens=10,
        output_tokens=10,
    )

    loop_round = ReviewRevisionRound(
        round_number=1,
        synthesis_assignment=synthesis_assignment,
        synthesis_result=synthesis_result,
        review_assignment=review_assignment,
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
        summary="The report was approved.",
    )

    return MultiAgentResearchWorkflowResult(
        request_id="research-001",
        workspace_id="workspace-001",
        status=MultiAgentResearchStatus.COMPLETED,
        stages=[
            MultiAgentResearchStageResult(
                stage=MultiAgentResearchStage.SEARCH,
                assignment=search_assignment,
                result=search_result,
            ),
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage.SOURCE_READING
                ),
                assignment=reader_assignment,
                result=reader_result,
            ),
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .EVIDENCE_EXTRACTION
                ),
                assignment=evidence_assignment,
                result=evidence_result,
            ),
            MultiAgentResearchStageResult(
                stage=(
                    MultiAgentResearchStage
                    .CLAIM_CONSTRUCTION
                ),
                assignment=claim_assignment,
                result=claim_result,
            ),
        ],
        review_revision_result=loop_result,
        final_result=review_result,
        summary="The workflow completed.",
    )


def test_comparison_normalizes_execution_metrics() -> None:
    comparison = ResearchExecutionComparator().compare(
        single_agent=single_execution(),
        multi_agent=multi_execution(),
    )

    assert comparison.single_agent.mode is (
        ResearchExecutionMode.SINGLE_AGENT
    )
    assert comparison.multi_agent.mode is (
        ResearchExecutionMode.MULTI_AGENT
    )
    assert (
        comparison.single_agent.participating_agent_count
        == 1
    )
    assert (
        comparison.multi_agent.participating_agent_count
        == 6
    )
    assert comparison.multi_agent.execution_step_count == 6
    assert comparison.multi_agent.source_count == 4
    assert comparison.multi_agent.evidence_count == 6
    assert comparison.multi_agent.claim_count == 3


def test_multi_agent_has_complete_traceability() -> None:
    comparison = ResearchExecutionComparator().compare(
        single_agent=single_execution(),
        multi_agent=multi_execution(),
    )

    assert (
        comparison.single_agent.traceability_score
        == pytest.approx(0.25)
    )
    assert (
        comparison.multi_agent.traceability_score
        == pytest.approx(1.0)
    )


def test_comparison_prefers_multi_agent_for_traceability() -> None:
    comparison = ResearchExecutionComparator().compare(
        single_agent=single_execution(),
        multi_agent=multi_execution(),
    )

    assert comparison.preferred_mode is (
        ResearchExecutionPreference.MULTI_AGENT
    )
    assert len(comparison.observations) >= 4


def test_comparison_can_prefer_single_agent() -> None:
    comparison = ResearchExecutionComparator().compare(
        single_agent=single_execution(
            traceable_source_count=4,
            traceable_evidence_count=6,
            traceable_claim_count=3,
            input_tokens=5,
            output_tokens=5,
        ),
        multi_agent=multi_execution(),
    )

    assert comparison.preferred_mode is (
        ResearchExecutionPreference.SINGLE_AGENT
    )


def test_single_execution_validates_request_id() -> None:
    execution = single_execution()

    with pytest.raises(
        ValueError,
        match=(
            "result assignment must share request_id"
        ),
    ):
        SingleAgentResearchExecution(
            request_id="research-other",
            workspace_id="workspace-001",
            result=execution.result,
        )


def test_comparison_requires_shared_request_id() -> None:
    execution = multi_execution().model_copy(
        update={
            "request_id": "research-other",
        }
    )

    with pytest.raises(
        ResearchExecutionComparisonError,
        match="executions must share request_id",
    ):
        ResearchExecutionComparator().compare(
            single_agent=single_execution(),
            multi_agent=execution,
        )


def test_comparison_requires_shared_workspace_id() -> None:
    execution = multi_execution().model_copy(
        update={
            "workspace_id": "workspace-other",
        }
    )

    with pytest.raises(
        ResearchExecutionComparisonError,
        match="executions must share workspace_id",
    ):
        ResearchExecutionComparator().compare(
            single_agent=single_execution(),
            multi_agent=execution,
        )


def test_comparison_reports_token_usage() -> None:
    comparison = ResearchExecutionComparator().compare(
        single_agent=single_execution(
            input_tokens=20,
            output_tokens=30,
        ),
        multi_agent=multi_execution(),
    )

    assert comparison.single_agent.total_token_count == 50
    assert comparison.multi_agent.total_token_count == 120
    assert any(
        "120 tokens" in observation
        for observation in comparison.observations
    )
