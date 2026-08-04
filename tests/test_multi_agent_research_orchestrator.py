"""Tests for the deterministic multi-agent orchestrator."""

from datetime import UTC, datetime

import pytest

from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchOrchestrator,
    MultiAgentResearchStage,
    MultiAgentResearchStatus,
)
from app.research.multi_agent_research_orchestrator_error import (
    MultiAgentResearchOrchestratorError,
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
    ResearchAgentAssignmentInput,
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
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    """Return one identity."""

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
        "agent-manager-001",
        ResearchAgentRole.MANAGER,
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


def capability_for_role(
    role: ResearchAgentRole,
) -> ResearchAgentCapability:
    """Return the primary capability for one role."""

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
    """Return one workflow assignment template."""

    capability = capability_for_role(role)

    return ResearchAgentTaskAssignment(
        assignment_id=assignment_id,
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(role),
        assignee=identity(agent_id, role),
        required_role=role,
        required_capabilities=[capability],
        title=f"Execute {role.value}",
        objective=f"Complete the {role.value} stage.",
        instructions=["Return a structured result."],
        inputs=[
            ResearchAgentAssignmentInput(
                name="template-input",
                reference_type="template",
                reference_id="template-001",
            )
        ],
        expected_output_type=f"{role.value}_output",
        acceptance_criteria=[
            "Return one primary output."
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


class StubAgent:
    """Return a configured task result."""

    def __init__(
        self,
        *,
        agent_id: str,
        role: ResearchAgentRole,
        status: ResearchAgentResultStatus = (
            ResearchAgentResultStatus.SUCCEEDED
        ),
        output_reference: str = "output-001",
    ) -> None:
        self._identity = identity(agent_id, role)
        self._status = status
        self._output_reference = output_reference
        self.calls: list[
            ResearchAgentTaskAssignment
        ] = []

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return stub identity."""

        return self._identity

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Return one deterministic result."""

        self.calls.append(assignment)

        failure = None
        outputs = []

        if self._status is ResearchAgentResultStatus.FAILED:
            failure = ResearchAgentFailure(
                category=ResearchAgentFailureCategory.INTERNAL,
                code="STUB_FAILURE",
                message="The stub agent failed.",
                retryable=False,
                failed_stage=self._identity.role.value,
            )
        else:
            outputs = [
                ResearchAgentOutputReference(
                    name=f"{self._identity.role.value}-output",
                    output_type=assignment.expected_output_type,
                    reference_id=self._output_reference,
                    primary=True,
                )
            ]

        return ResearchAgentTaskResult(
            result_id=(
                f"result-{self._identity.agent_id}-"
                f"{len(self.calls)}"
            ),
            assignment=assignment,
            agent=self._identity,
            status=self._status,
            summary="Stub execution result.",
            outputs=outputs,
            metrics=ResearchAgentExecutionMetrics(),
            failure=failure,
            completed_at=datetime(
                2026,
                8,
                4,
                10,
                0,
                tzinfo=UTC,
            ),
        )


class StubReviewRevisionLoop:
    """Return a configured review-revision result."""

    def __init__(
        self,
        status: ReviewRevisionLoopStatus,
    ) -> None:
        self._status = status
        self.calls: list[
            tuple[
                ResearchAgentTaskAssignment,
                ResearchAgentTaskAssignment,
            ]
        ] = []

    def run(
        self,
        *,
        initial_synthesis_assignment: (
            ResearchAgentTaskAssignment
        ),
        review_assignment_template: (
            ResearchAgentTaskAssignment
        ),
    ) -> ReviewRevisionLoopResult:
        """Return one deterministic loop result."""

        self.calls.append(
            (
                initial_synthesis_assignment,
                review_assignment_template,
            )
        )

        synthesis_agent = identity(
            "agent-synthesis-001",
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
        )
        synthesis_result = ResearchAgentTaskResult(
            result_id="result-synthesis-001",
            assignment=initial_synthesis_assignment,
            agent=synthesis_agent,
            status=(
                ResearchAgentResultStatus.SUCCEEDED
                if self._status
                is not ReviewRevisionLoopStatus.SYNTHESIS_FAILED
                else ResearchAgentResultStatus.FAILED
            ),
            summary="Synthesis result.",
            outputs=(
                [
                    ResearchAgentOutputReference(
                        name="research-report",
                        output_type="research_report",
                        reference_id="report-001",
                        primary=True,
                    )
                ]
                if self._status
                is not ReviewRevisionLoopStatus.SYNTHESIS_FAILED
                else []
            ),
            metrics=ResearchAgentExecutionMetrics(),
            failure=(
                None
                if self._status
                is not ReviewRevisionLoopStatus.SYNTHESIS_FAILED
                else ResearchAgentFailure(
                    category=(
                        ResearchAgentFailureCategory.INTERNAL
                    ),
                    code="SYNTHESIS_FAILED",
                    message="Synthesis failed.",
                    retryable=False,
                    failed_stage="synthesis",
                )
            ),
            completed_at=datetime(
                2026,
                8,
                4,
                10,
                1,
                tzinfo=UTC,
            ),
        )

        loop_round = ReviewRevisionRound(
            round_number=1,
            synthesis_assignment=(
                initial_synthesis_assignment
            ),
            synthesis_result=synthesis_result,
        )

        return ReviewRevisionLoopResult(
            loop_id="loop-001",
            status=self._status,
            rounds=[loop_round],
            maximum_revision_rounds=2,
            revision_rounds_used=0,
            final_synthesis_result=synthesis_result,
            summary="Stub loop result.",
        )


def templates() -> dict[str, ResearchAgentTaskAssignment]:
    """Return all workflow templates."""

    return {
        "search_assignment": assignment(
            assignment_id="assignment-search-001",
            agent_id="agent-search-001",
            role=ResearchAgentRole.SEARCH_SPECIALIST,
        ),
        "source_reader_template": assignment(
            assignment_id="assignment-reader-001",
            agent_id="agent-reader-001",
            role=ResearchAgentRole.SOURCE_READER,
        ),
        "evidence_template": assignment(
            assignment_id="assignment-evidence-001",
            agent_id="agent-evidence-001",
            role=ResearchAgentRole.EVIDENCE_ANALYST,
        ),
        "claim_template": assignment(
            assignment_id="assignment-claim-001",
            agent_id="agent-claim-001",
            role=ResearchAgentRole.CLAIM_ANALYST,
        ),
        "synthesis_template": assignment(
            assignment_id="assignment-synthesis-001",
            agent_id="agent-synthesis-001",
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
        ),
        "review_template": assignment(
            assignment_id="assignment-review-001",
            agent_id="agent-quality-001",
            role=ResearchAgentRole.QUALITY_REVIEWER,
        ),
    }


def orchestrator(
    *,
    search_status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
    reader_status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
    evidence_status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
    claim_status: ResearchAgentResultStatus = (
        ResearchAgentResultStatus.SUCCEEDED
    ),
    loop_status: ReviewRevisionLoopStatus = (
        ReviewRevisionLoopStatus.APPROVED
    ),
) -> tuple[
    MultiAgentResearchOrchestrator,
    StubAgent,
    StubAgent,
    StubAgent,
    StubAgent,
    StubReviewRevisionLoop,
]:
    """Return one configured orchestrator."""

    search = StubAgent(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        status=search_status,
        output_reference="source-set-001",
    )
    reader = StubAgent(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        status=reader_status,
        output_reference="document-set-001",
    )
    evidence = StubAgent(
        agent_id="agent-evidence-001",
        role=ResearchAgentRole.EVIDENCE_ANALYST,
        status=evidence_status,
        output_reference="evidence-set-001",
    )
    claim = StubAgent(
        agent_id="agent-claim-001",
        role=ResearchAgentRole.CLAIM_ANALYST,
        status=claim_status,
        output_reference="claim-set-001",
    )
    review_loop = StubReviewRevisionLoop(loop_status)

    value = MultiAgentResearchOrchestrator(
        search_agent=search,
        source_reader_agent=reader,
        evidence_analyst_agent=evidence,
        claim_analyst_agent=claim,
        review_revision_loop=review_loop,
    )

    return (
        value,
        search,
        reader,
        evidence,
        claim,
        review_loop,
    )


def test_orchestrator_completes_approved_workflow() -> None:
    (
        value,
        search,
        reader,
        evidence,
        claim,
        review_loop,
    ) = orchestrator()

    result = value.run(**templates())

    assert result.status is MultiAgentResearchStatus.COMPLETED
    assert result.completed is True
    assert len(result.stages) == 4
    assert [
        stage.stage
        for stage in result.stages
    ] == [
        MultiAgentResearchStage.SEARCH,
        MultiAgentResearchStage.SOURCE_READING,
        MultiAgentResearchStage.EVIDENCE_EXTRACTION,
        MultiAgentResearchStage.CLAIM_CONSTRUCTION,
    ]
    assert len(search.calls) == 1
    assert len(reader.calls) == 1
    assert len(evidence.calls) == 1
    assert len(claim.calls) == 1
    assert len(review_loop.calls) == 1


def test_orchestrator_connects_primary_outputs() -> None:
    value, _, reader, evidence, claim, review_loop = (
        orchestrator()
    )

    value.run(**templates())

    assert reader.calls[0].inputs[0].reference_id == (
        "source-set-001"
    )
    assert evidence.calls[0].inputs[0].reference_id == (
        "document-set-001"
    )
    assert claim.calls[0].inputs[0].reference_id == (
        "evidence-set-001"
    )

    synthesis_assignment, _ = review_loop.calls[0]

    assert synthesis_assignment.inputs[0].reference_id == (
        "claim-set-001"
    )


def test_orchestrator_stops_after_search_failure() -> None:
    value, _, reader, evidence, claim, review_loop = (
        orchestrator(
            search_status=ResearchAgentResultStatus.FAILED
        )
    )

    result = value.run(**templates())

    assert result.status is (
        MultiAgentResearchStatus.SEARCH_FAILED
    )
    assert len(result.stages) == 1
    assert not reader.calls
    assert not evidence.calls
    assert not claim.calls
    assert not review_loop.calls


def test_orchestrator_stops_after_reader_failure() -> None:
    value, _, _, evidence, claim, review_loop = (
        orchestrator(
            reader_status=ResearchAgentResultStatus.FAILED
        )
    )

    result = value.run(**templates())

    assert result.status is (
        MultiAgentResearchStatus.SOURCE_READING_FAILED
    )
    assert len(result.stages) == 2
    assert not evidence.calls
    assert not claim.calls
    assert not review_loop.calls


def test_orchestrator_stops_after_evidence_failure() -> None:
    value, _, _, _, claim, review_loop = orchestrator(
        evidence_status=ResearchAgentResultStatus.FAILED
    )

    result = value.run(**templates())

    assert result.status is (
        MultiAgentResearchStatus.EVIDENCE_FAILED
    )
    assert len(result.stages) == 3
    assert not claim.calls
    assert not review_loop.calls


def test_orchestrator_stops_after_claim_failure() -> None:
    value, _, _, _, _, review_loop = orchestrator(
        claim_status=ResearchAgentResultStatus.FAILED
    )

    result = value.run(**templates())

    assert result.status is (
        MultiAgentResearchStatus.CLAIM_FAILED
    )
    assert len(result.stages) == 4
    assert not review_loop.calls


@pytest.mark.parametrize(
    ("loop_status", "expected_status"),
    [
        (
            ReviewRevisionLoopStatus.REJECTED,
            MultiAgentResearchStatus.REPORT_REJECTED,
        ),
        (
            ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED,
            MultiAgentResearchStatus.REVISION_LIMIT_REACHED,
        ),
        (
            ReviewRevisionLoopStatus.SYNTHESIS_FAILED,
            MultiAgentResearchStatus.SYNTHESIS_FAILED,
        ),
        (
            ReviewRevisionLoopStatus.REVIEW_FAILED,
            MultiAgentResearchStatus.REVIEW_FAILED,
        ),
    ],
)
def test_orchestrator_maps_loop_status(
    loop_status: ReviewRevisionLoopStatus,
    expected_status: MultiAgentResearchStatus,
) -> None:
    value, *_ = orchestrator(loop_status=loop_status)

    result = value.run(**templates())

    assert result.status is expected_status


def test_orchestrator_requires_shared_request_id() -> None:
    value, *_ = orchestrator()
    values = templates()
    values["claim_template"] = (
        values["claim_template"].model_copy(
            update={"request_id": "research-other"}
        )
    )

    with pytest.raises(
        MultiAgentResearchOrchestratorError,
        match="all assignments must share request_id",
    ):
        value.run(**values)


def test_orchestrator_validates_target_agent() -> None:
    value, *_ = orchestrator()
    values = templates()
    values["evidence_template"] = (
        values["evidence_template"].model_copy(
            update={
                "assignee": identity(
                    "agent-evidence-other",
                    ResearchAgentRole.EVIDENCE_ANALYST,
                )
            }
        )
    )

    with pytest.raises(
        MultiAgentResearchOrchestratorError,
        match=(
            "evidence template must target "
            "its configured agent"
        ),
    ):
        value.run(**values)
