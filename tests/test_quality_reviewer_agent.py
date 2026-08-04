"""Tests for the deterministic quality reviewer agent."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.research.quality_reviewer_agent import (
    QualityReviewerAgent,
)
from app.research.quality_reviewer_agent_error import (
    QualityReviewerAgentError,
)
from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
    ResearchQualityReview,
    ResearchQualityReviewExecutionResult,
    ResearchQualityReviewExecutor,
    ResearchQualityReviewExecutorError,
    ResearchQualityScores,
    ResearchRevisionRequest,
    ResearchRevisionSeverity,
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
    ResearchAgentFailureCategory,
    ResearchAgentResultStatus,
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
    """Return one manager delegation profile."""

    manager = identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
    )

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-quality",
        agent=manager,
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.QUALITY_REVIEWER,
        ],
    )


def reviewer() -> ResearchAgentIdentity:
    """Return one quality reviewer identity."""

    return identity(
        agent_id="agent-quality-001",
        role=ResearchAgentRole.QUALITY_REVIEWER,
    )


def reviewer_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return one quality reviewer profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-quality-001",
        agent=agent or reviewer(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.EVALUATE_REPORT,
                ResearchAgentCapability.REQUEST_REVISION,
                ResearchAgentCapability.APPROVE_RESULT,
            ]
        ),
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one executable quality review assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-quality-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "assigner_profile": manager_profile(),
        "assignee": reviewer(),
        "required_role": (
            ResearchAgentRole.QUALITY_REVIEWER
        ),
        "required_capabilities": [
            ResearchAgentCapability.EVALUATE_REPORT,
        ],
        "title": "Review final research report",
        "objective": (
            "Evaluate report quality independently."
        ),
        "instructions": [
            "Check evidence and citation quality.",
            "Return a deterministic decision.",
        ],
        "inputs": [
            ResearchAgentAssignmentInput(
                name="report-001",
                reference_type="research_report",
                reference_id="report-001",
            )
        ],
        "expected_output_type": (
            "research_quality_review"
        ),
        "acceptance_criteria": [
            "Return quality scores.",
            "Return an approval decision.",
        ],
        "status": (
            ResearchAgentAssignmentStatus.IN_PROGRESS
        ),
        "attempt_number": 1,
        "maximum_attempts": 2,
    }
    values.update(overrides)

    return ResearchAgentTaskAssignment.model_validate(
        values
    )


def scores(
    *,
    value: float = 0.9,
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


def approved_review() -> ResearchQualityReview:
    """Return one approved report review."""

    return ResearchQualityReview(
        review_id="review-001",
        report_id="report-001",
        decision=ResearchQualityDecision.APPROVED,
        scores=scores(),
        summary="The report meets all quality requirements.",
        strengths=[
            "Claims are traceable to evidence.",
            "The report is logically organized.",
        ],
    )


def revision_review() -> ResearchQualityReview:
    """Return one review requiring revision."""

    return ResearchQualityReview(
        review_id="review-002",
        report_id="report-001",
        decision=(
            ResearchQualityDecision.REVISION_REQUIRED
        ),
        scores=scores(value=0.7),
        summary="The report requires stronger citations.",
        revision_requests=[
            ResearchRevisionRequest(
                revision_id="revision-001",
                target_type="claim",
                target_id="claim-002",
                issue="The claim lacks a verified citation.",
                required_action=(
                    "Add a verified evidence citation."
                ),
                severity=ResearchRevisionSeverity.MAJOR,
                required=True,
            )
        ],
    )


class ApprovedExecutor(ResearchQualityReviewExecutor):
    """Return one approved quality review."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        return ResearchQualityReviewExecutionResult(
            review=approved_review(),
            tool_call_count=1,
            duration_ms=100,
            input_token_count=20,
            output_token_count=10,
            metadata={
                "provider": "test-quality-reviewer",
            },
        )


class RevisionExecutor(ResearchQualityReviewExecutor):
    """Return one revision-required review."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        return ResearchQualityReviewExecutionResult(
            review=revision_review(),
            tool_call_count=1,
        )


class EmptyExecutor(ResearchQualityReviewExecutor):
    """Return no quality review."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        return ResearchQualityReviewExecutionResult()


class FailingExecutor(ResearchQualityReviewExecutor):
    """Raise a structured quality-review failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        raise ResearchQualityReviewExecutorError(
            "Quality provider is temporarily unavailable.",
            code="QUALITY_PROVIDER_UNAVAILABLE",
            retryable=True,
        )


class RuntimeFailingExecutor(ResearchQualityReviewExecutor):
    """Raise an unexpected runtime failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        raise RuntimeError("Unexpected quality failure.")


def agent(
    executor: ResearchQualityReviewExecutor,
    *,
    profile: ResearchAgentCapabilityProfile | None = None,
) -> QualityReviewerAgent:
    """Return one deterministic quality reviewer."""

    return QualityReviewerAgent(
        profile=profile or reviewer_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            8,
            30,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-quality-001",
        output_reference_id_factory=(
            lambda: "quality-review-output-001"
        ),
    )


def test_quality_scores_calculate_overall_score() -> None:
    value = scores(value=0.8)

    assert value.overall_score == pytest.approx(0.8)


def test_quality_review_reports_approval_state() -> None:
    value = approved_review()

    assert value.approved is True
    assert value.requires_revision is False


def test_revision_review_requires_required_revision() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "revision-required review must include "
            "a required revision"
        ),
    ):
        ResearchQualityReview(
            review_id="review-invalid",
            report_id="report-001",
            decision=(
                ResearchQualityDecision.REVISION_REQUIRED
            ),
            scores=scores(),
            summary="Revision required.",
            revision_requests=[],
        )


def test_approved_review_rejects_required_revision() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "approved review must not include "
            "required revisions"
        ),
    ):
        ResearchQualityReview(
            review_id="review-invalid",
            report_id="report-001",
            decision=ResearchQualityDecision.APPROVED,
            scores=scores(),
            summary="Approved.",
            revision_requests=[
                ResearchRevisionRequest(
                    revision_id="revision-001",
                    target_type="report",
                    target_id="report-001",
                    issue="Issue.",
                    required_action="Fix issue.",
                    severity=ResearchRevisionSeverity.MINOR,
                    required=True,
                )
            ],
        )


def test_quality_reviewer_returns_approved_result() -> None:
    value = agent(ApprovedExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.payload["decision"] == "approved"
    assert value.payload["approved"] is True
    assert value.payload["requires_revision"] is False
    assert value.metrics.total_token_count == 30
    assert value.primary_output() is not None


def test_quality_reviewer_returns_revision_result() -> None:
    value = agent(RevisionExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.payload["decision"] == (
        "revision_required"
    )
    assert value.payload["approved"] is False
    assert value.payload["requires_revision"] is True
    assert value.payload["revision_count"] == 1


def test_quality_reviewer_fails_when_review_missing() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.code == (
        "NO_QUALITY_REVIEW_PRODUCED"
    )


def test_quality_reviewer_converts_executor_error() -> None:
    value = agent(FailingExecutor()).execute(
        assignment()
    )

    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.TOOL
    )
    assert value.failure.code == (
        "QUALITY_PROVIDER_UNAVAILABLE"
    )
    assert value.failure.retryable is True


def test_quality_reviewer_converts_runtime_error() -> None:
    value = agent(RuntimeFailingExecutor()).execute(
        assignment()
    )

    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.INTERNAL
    )
    assert value.failure.code == (
        "UNEXPECTED_QUALITY_REVIEW_ERROR"
    )


def test_quality_reviewer_requires_correct_role() -> None:
    wrong = identity(
        agent_id="agent-claim-001",
        role=ResearchAgentRole.CLAIM_ANALYST,
    )

    with pytest.raises(
        QualityReviewerAgentError,
        match=(
            "quality reviewer must have "
            "quality_reviewer role"
        ),
    ):
        agent(
            ApprovedExecutor(),
            profile=reviewer_profile(agent=wrong),
        )


def test_quality_reviewer_requires_capability() -> None:
    profile = reviewer_profile(
        capabilities=[
            ResearchAgentCapability.APPROVE_RESULT,
        ]
    )

    with pytest.raises(
        QualityReviewerAgentError,
        match=(
            "quality reviewer requires "
            "evaluate_report capability"
        ),
    ):
        agent(
            ApprovedExecutor(),
            profile=profile,
        )


def test_quality_reviewer_rejects_wrong_assignee() -> None:
    other = identity(
        agent_id="agent-quality-002",
        role=ResearchAgentRole.QUALITY_REVIEWER,
    )

    with pytest.raises(
        QualityReviewerAgentError,
        match=(
            "assignment assignee must match "
            "quality reviewer"
        ),
    ):
        agent(ApprovedExecutor()).execute(
            assignment(assignee=other)
        )


@pytest.mark.parametrize(
    "status",
    [
        ResearchAgentAssignmentStatus.CREATED,
        ResearchAgentAssignmentStatus.COMPLETED,
        ResearchAgentAssignmentStatus.FAILED,
        ResearchAgentAssignmentStatus.CANCELLED,
    ],
)
def test_quality_reviewer_rejects_status(
    status: ResearchAgentAssignmentStatus,
) -> None:
    with pytest.raises(
        QualityReviewerAgentError,
        match="assignment status is not executable",
    ):
        agent(ApprovedExecutor()).execute(
            assignment(status=status)
        )


def test_quality_review_assignment_requires_inputs() -> None:
    with pytest.raises(
        QualityReviewerAgentError,
        match=(
            "quality review assignment must include "
            "report inputs"
        ),
    ):
        agent(ApprovedExecutor()).execute(
            assignment(inputs=[])
        )


def test_quality_review_assignment_requires_capability() -> None:
    profile = reviewer_profile(
        capabilities=[
            ResearchAgentCapability.EVALUATE_REPORT,
            ResearchAgentCapability.APPROVE_RESULT,
        ]
    )

    with pytest.raises(
        QualityReviewerAgentError,
        match=(
            "quality review assignment must require "
            "evaluate_report capability"
        ),
    ):
        agent(
            ApprovedExecutor(),
            profile=profile,
        ).execute(
            assignment(
                required_capabilities=[
                    ResearchAgentCapability.APPROVE_RESULT,
                ]
            )
        )


def test_quality_reviewer_rejects_blank_result_id() -> None:
    reviewer_agent = QualityReviewerAgent(
        profile=reviewer_profile(),
        executor=ApprovedExecutor(),
        result_id_factory=lambda: " ",
    )

    with pytest.raises(
        QualityReviewerAgentError,
        match="result_id factory returned blank value",
    ):
        reviewer_agent.execute(assignment())


def test_quality_reviewer_exposes_identity() -> None:
    reviewer_agent = agent(ApprovedExecutor())

    assert reviewer_agent.identity.agent_id == (
        "agent-quality-001"
    )
    assert reviewer_agent.profile.profile_id == (
        "profile-quality-001"
    )
