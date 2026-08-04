"""Tests for the deterministic review and revision loop."""

from datetime import UTC, datetime

import pytest

from app.research.quality_reviewer_agent import (
    QualityReviewerAgent,
)
from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
    ResearchQualityReview,
    ResearchQualityReviewExecutionResult,
    ResearchQualityReviewExecutor,
    ResearchQualityScores,
    ResearchRevisionRequest,
    ResearchRevisionSeverity,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesisExecutionResult,
    ResearchSynthesisExecutor,
    ResearchSynthesisExecutorError,
    ResearchSynthesizedReport,
    ResearchSynthesizedSection,
)
from app.research.review_revision_loop import (
    ReviewRevisionLoop,
    ReviewRevisionLoopStatus,
)
from app.research.review_revision_loop_error import (
    ReviewRevisionLoopError,
)
from app.research.synthesis_specialist_agent import (
    SynthesisSpecialistAgent,
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


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentRole.QUALITY_REVIEWER,
        ],
    )


def synthesis_identity() -> ResearchAgentIdentity:
    """Return the synthesis specialist identity."""

    return identity(
        agent_id="agent-synthesis-001",
        role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
    )


def reviewer_identity() -> ResearchAgentIdentity:
    """Return the quality reviewer identity."""

    return identity(
        agent_id="agent-quality-001",
        role=ResearchAgentRole.QUALITY_REVIEWER,
    )


def synthesis_profile() -> ResearchAgentCapabilityProfile:
    """Return the synthesis specialist profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-synthesis-001",
        agent=synthesis_identity(),
        capabilities=[
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ],
    )


def reviewer_profile() -> ResearchAgentCapabilityProfile:
    """Return the quality reviewer profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-quality-001",
        agent=reviewer_identity(),
        capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
        ],
    )


def synthesis_assignment() -> ResearchAgentTaskAssignment:
    """Return the initial synthesis assignment."""

    return ResearchAgentTaskAssignment(
        assignment_id="assignment-synthesis-initial",
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(),
        assignee=synthesis_identity(),
        required_role=(
            ResearchAgentRole.SYNTHESIS_SPECIALIST
        ),
        required_capabilities=[
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ],
        title="Synthesize research report",
        objective="Create a complete research report.",
        instructions=[
            "Use verified claims.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="verified-claims",
                reference_type="verified_claim_set",
                reference_id="claim-set-001",
            )
        ],
        expected_output_type="research_report",
        acceptance_criteria=[
            "Return a structured research report."
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=3,
    )


def review_assignment_template() -> ResearchAgentTaskAssignment:
    """Return a quality-review assignment template."""

    return ResearchAgentTaskAssignment(
        assignment_id="assignment-review-template",
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(),
        assignee=reviewer_identity(),
        required_role=ResearchAgentRole.QUALITY_REVIEWER,
        required_capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
        ],
        title="Review research report",
        objective="Evaluate report quality.",
        instructions=[
            "Return an approval decision.",
        ],
        inputs=[
            ResearchAgentAssignmentInput(
                name="template-report",
                reference_type="research_report",
                reference_id="template-report",
            )
        ],
        expected_output_type="research_quality_review",
        acceptance_criteria=[
            "Return quality scores and a decision."
        ],
        status=ResearchAgentAssignmentStatus.CREATED,
        attempt_number=1,
        maximum_attempts=3,
    )


def report(
    *,
    report_id: str,
) -> ResearchSynthesizedReport:
    """Return one synthesized report."""

    return ResearchSynthesizedReport(
        report_id=report_id,
        title="Multi-Agent Research",
        executive_summary="Research summary.",
        sections=[
            ResearchSynthesizedSection(
                section_id=f"section-{report_id}",
                heading="Findings",
                content="Research findings.",
                claim_ids=["claim-001"],
                order=1,
            )
        ],
    )


class CountingSynthesisExecutor(
    ResearchSynthesisExecutor
):
    """Return a new deterministic report on every call."""

    def __init__(self) -> None:
        self.calls: list[
            ResearchAgentTaskAssignment
        ] = []

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        self.calls.append(assignment)
        call_number = len(self.calls)

        return ResearchSynthesisExecutionResult(
            requested_section_count=1,
            report=report(
                report_id=f"report-{call_number:03d}"
            ),
            tool_call_count=1,
        )


class FailingSynthesisExecutor(
    ResearchSynthesisExecutor
):
    """Fail every synthesis execution."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        raise ResearchSynthesisExecutorError(
            "Synthesis failed.",
            retryable=False,
        )


def quality_scores(
    value: float,
) -> ResearchQualityScores:
    """Return uniform quality scores."""

    return ResearchQualityScores(
        completeness=value,
        evidence_coverage=value,
        citation_quality=value,
        source_quality=value,
        logical_consistency=value,
        clarity=value,
    )


def revision_review(
    *,
    review_id: str,
    report_id: str,
) -> ResearchQualityReview:
    """Return one revision-required review."""

    return ResearchQualityReview(
        review_id=review_id,
        report_id=report_id,
        decision=(
            ResearchQualityDecision.REVISION_REQUIRED
        ),
        scores=quality_scores(0.7),
        summary="The report requires revision.",
        revision_requests=[
            ResearchRevisionRequest(
                revision_id=f"revision-{review_id}",
                target_type="report",
                target_id=report_id,
                issue="Evidence coverage is incomplete.",
                required_action=(
                    "Add supporting evidence."
                ),
                severity=ResearchRevisionSeverity.MAJOR,
                required=True,
            )
        ],
    )


def approved_review(
    *,
    review_id: str,
    report_id: str,
) -> ResearchQualityReview:
    """Return one approved review."""

    return ResearchQualityReview(
        review_id=review_id,
        report_id=report_id,
        decision=ResearchQualityDecision.APPROVED,
        scores=quality_scores(0.95),
        summary="The report is approved.",
    )


def rejected_review(
    *,
    review_id: str,
    report_id: str,
) -> ResearchQualityReview:
    """Return one rejected review."""

    return ResearchQualityReview(
        review_id=review_id,
        report_id=report_id,
        decision=ResearchQualityDecision.REJECTED,
        scores=quality_scores(0.2),
        summary="The report is rejected.",
        rejection_reason=(
            "The report is fundamentally unsupported."
        ),
    )


class SequenceReviewExecutor(
    ResearchQualityReviewExecutor
):
    """Return configured review decisions in sequence."""

    def __init__(
        self,
        decisions: list[ResearchQualityDecision],
    ) -> None:
        self._decisions = decisions
        self.calls: list[
            ResearchAgentTaskAssignment
        ] = []

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        self.calls.append(assignment)
        call_number = len(self.calls)
        decision = self._decisions[
            min(
                call_number - 1,
                len(self._decisions) - 1,
            )
        ]
        report_id = f"report-{call_number:03d}"
        review_id = f"review-{call_number:03d}"

        if decision is ResearchQualityDecision.APPROVED:
            review = approved_review(
                review_id=review_id,
                report_id=report_id,
            )
        elif (
            decision
            is ResearchQualityDecision.REVISION_REQUIRED
        ):
            review = revision_review(
                review_id=review_id,
                report_id=report_id,
            )
        else:
            review = rejected_review(
                review_id=review_id,
                report_id=report_id,
            )

        return ResearchQualityReviewExecutionResult(
            review=review,
            tool_call_count=1,
        )


class EmptyReviewExecutor(
    ResearchQualityReviewExecutor
):
    """Return no review."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        return ResearchQualityReviewExecutionResult()


def synthesis_agent(
    executor: ResearchSynthesisExecutor,
) -> SynthesisSpecialistAgent:
    """Return one deterministic synthesis agent."""

    result_counter = iter(range(1, 100))
    output_counter = iter(range(1, 100))

    return SynthesisSpecialistAgent(
        profile=synthesis_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            9,
            0,
            tzinfo=UTC,
        ),
        result_id_factory=(
            lambda: (
                f"result-synthesis-{next(result_counter):03d}"
            )
        ),
        output_reference_id_factory=(
            lambda: (
                f"report-output-{next(output_counter):03d}"
            )
        ),
    )


def quality_agent(
    executor: ResearchQualityReviewExecutor,
) -> QualityReviewerAgent:
    """Return one deterministic quality reviewer."""

    result_counter = iter(range(1, 100))
    output_counter = iter(range(1, 100))

    return QualityReviewerAgent(
        profile=reviewer_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            9,
            1,
            tzinfo=UTC,
        ),
        result_id_factory=(
            lambda: (
                f"result-review-{next(result_counter):03d}"
            )
        ),
        output_reference_id_factory=(
            lambda: (
                f"review-output-{next(output_counter):03d}"
            )
        ),
    )


def loop(
    *,
    synthesis_executor: ResearchSynthesisExecutor,
    review_executor: ResearchQualityReviewExecutor,
    maximum_revision_rounds: int = 2,
) -> ReviewRevisionLoop:
    """Return one deterministic review and revision loop."""

    return ReviewRevisionLoop(
        synthesis_agent=synthesis_agent(
            synthesis_executor
        ),
        quality_reviewer=quality_agent(
            review_executor
        ),
        maximum_revision_rounds=(
            maximum_revision_rounds
        ),
        loop_id_factory=lambda: "review-loop-001",
        synthesis_assignment_id_factory=(
            lambda round_number: (
                f"assignment-revision-{round_number:03d}"
            )
        ),
        review_assignment_id_factory=(
            lambda round_number: (
                f"assignment-review-{round_number:03d}"
            )
        ),
    )


def run_loop(
    value: ReviewRevisionLoop,
):
    """Run one loop using standard assignments."""

    return value.run(
        initial_synthesis_assignment=(
            synthesis_assignment()
        ),
        review_assignment_template=(
            review_assignment_template()
        ),
    )


def test_loop_approves_first_report() -> None:
    synthesis_executor = CountingSynthesisExecutor()
    review_executor = SequenceReviewExecutor(
        [ResearchQualityDecision.APPROVED]
    )

    value = run_loop(
        loop(
            synthesis_executor=synthesis_executor,
            review_executor=review_executor,
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.APPROVED
    )
    assert value.approved is True
    assert value.revision_rounds_used == 0
    assert len(value.rounds) == 1
    assert len(synthesis_executor.calls) == 1
    assert len(review_executor.calls) == 1


def test_loop_revises_then_approves() -> None:
    synthesis_executor = CountingSynthesisExecutor()
    review_executor = SequenceReviewExecutor(
        [
            ResearchQualityDecision.REVISION_REQUIRED,
            ResearchQualityDecision.APPROVED,
        ]
    )

    value = run_loop(
        loop(
            synthesis_executor=synthesis_executor,
            review_executor=review_executor,
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.APPROVED
    )
    assert value.revision_rounds_used == 1
    assert len(value.rounds) == 2
    assert len(synthesis_executor.calls) == 2
    assert len(review_executor.calls) == 2

    revision_assignment = synthesis_executor.calls[1]

    assert revision_assignment.assignment_id == (
        "assignment-revision-001"
    )
    assert revision_assignment.parent_assignment_id == (
        "assignment-synthesis-initial"
    )
    assert revision_assignment.attempt_number == 2
    assert revision_assignment.metadata[
        "revision_round"
    ] == "1"

    reference_types = {
        item.reference_type
        for item in revision_assignment.inputs
    }

    assert "research_report" in reference_types
    assert "research_quality_review" in reference_types


def test_loop_stops_when_report_rejected() -> None:
    value = run_loop(
        loop(
            synthesis_executor=(
                CountingSynthesisExecutor()
            ),
            review_executor=SequenceReviewExecutor(
                [ResearchQualityDecision.REJECTED]
            ),
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.REJECTED
    )
    assert value.approved is False
    assert len(value.rounds) == 1


def test_loop_stops_at_revision_limit() -> None:
    synthesis_executor = CountingSynthesisExecutor()
    review_executor = SequenceReviewExecutor(
        [ResearchQualityDecision.REVISION_REQUIRED]
    )

    value = run_loop(
        loop(
            synthesis_executor=synthesis_executor,
            review_executor=review_executor,
            maximum_revision_rounds=2,
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED
    )
    assert value.exhausted is True
    assert value.revision_rounds_used == 2
    assert len(value.rounds) == 3
    assert len(synthesis_executor.calls) == 3
    assert len(review_executor.calls) == 3


def test_zero_revision_limit_reviews_once() -> None:
    value = run_loop(
        loop(
            synthesis_executor=(
                CountingSynthesisExecutor()
            ),
            review_executor=SequenceReviewExecutor(
                [
                    ResearchQualityDecision
                    .REVISION_REQUIRED
                ]
            ),
            maximum_revision_rounds=0,
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.REVISION_LIMIT_REACHED
    )
    assert value.revision_rounds_used == 0
    assert len(value.rounds) == 1


def test_loop_stops_when_synthesis_fails() -> None:
    value = run_loop(
        loop(
            synthesis_executor=(
                FailingSynthesisExecutor()
            ),
            review_executor=SequenceReviewExecutor(
                [ResearchQualityDecision.APPROVED]
            ),
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.SYNTHESIS_FAILED
    )
    assert value.final_review_result is None
    assert len(value.rounds) == 1


def test_loop_stops_when_review_fails() -> None:
    value = run_loop(
        loop(
            synthesis_executor=(
                CountingSynthesisExecutor()
            ),
            review_executor=EmptyReviewExecutor(),
        )
    )

    assert value.status is (
        ReviewRevisionLoopStatus.REVIEW_FAILED
    )
    assert value.final_review_result is not None
    assert len(value.rounds) == 1


def test_loop_rejects_negative_revision_limit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "maximum_revision_rounds must be nonnegative"
        ),
    ):
        loop(
            synthesis_executor=(
                CountingSynthesisExecutor()
            ),
            review_executor=SequenceReviewExecutor(
                [ResearchQualityDecision.APPROVED]
            ),
            maximum_revision_rounds=-1,
        )


def test_loop_validates_request_identity() -> None:
    template = review_assignment_template().model_copy(
        update={
            "request_id": "research-other",
        }
    )
    value = loop(
        synthesis_executor=CountingSynthesisExecutor(),
        review_executor=SequenceReviewExecutor(
            [ResearchQualityDecision.APPROVED]
        ),
    )

    with pytest.raises(
        ReviewRevisionLoopError,
        match=(
            "synthesis and review assignments must share "
            "request_id"
        ),
    ):
        value.run(
            initial_synthesis_assignment=(
                synthesis_assignment()
            ),
            review_assignment_template=template,
        )


def test_loop_rejects_blank_loop_id() -> None:
    value = ReviewRevisionLoop(
        synthesis_agent=synthesis_agent(
            CountingSynthesisExecutor()
        ),
        quality_reviewer=quality_agent(
            SequenceReviewExecutor(
                [ResearchQualityDecision.APPROVED]
            )
        ),
        loop_id_factory=lambda: " ",
    )

    with pytest.raises(
        ReviewRevisionLoopError,
        match="loop_id factory returned blank value",
    ):
        run_loop(value)
