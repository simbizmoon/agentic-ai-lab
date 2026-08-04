"""Tests for source critic and citation verifier agents."""

from datetime import UTC, datetime

import pytest

from app.research.citation_verifier_agent import (
    CitationVerifierAgent,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
    ResearchCitationVerification,
    ResearchCitationVerificationFailure,
    ResearchCitationVerifierExecutionResult,
    ResearchCitationVerifierExecutor,
    ResearchCitationVerifierExecutorError,
)
from app.research.research_review_agent_error import (
    CitationVerifierAgentError,
    SourceCriticAgentError,
)
from app.research.research_source_critic_executor import (
    ResearchSourceCriticExecutionResult,
    ResearchSourceCriticExecutor,
    ResearchSourceCriticExecutorError,
    ResearchSourceCriticFailure,
    ResearchSourceCritique,
    ResearchSourceDecision,
)
from app.research.source_critic_agent import (
    SourceCriticAgent,
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
    ResearchAgentResultStatus,
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


def specialist_profile(
    role: ResearchAgentRole,
    capability: ResearchAgentCapability,
) -> ResearchAgentCapabilityProfile:
    """Return one specialist profile."""

    return ResearchAgentCapabilityProfile(
        profile_id=f"profile-{role.value}",
        agent=identity(
            f"agent-{role.value}-001",
            role,
        ),
        capabilities=[capability],
    )


def assignment(
    *,
    role: ResearchAgentRole,
    capability: ResearchAgentCapability,
) -> ResearchAgentTaskAssignment:
    """Return one executable review assignment."""

    return ResearchAgentTaskAssignment(
        assignment_id=f"assignment-{role.value}-001",
        request_id="research-001",
        workspace_id="workspace-001",
        assigner_profile=manager_profile(role),
        assignee=identity(
            f"agent-{role.value}-001",
            role,
        ),
        required_role=role,
        required_capabilities=[capability],
        title="Review research artifact",
        objective="Perform an independent review.",
        instructions=["Return structured review results."],
        inputs=[
            ResearchAgentAssignmentInput(
                name="artifact-001",
                reference_type="research_artifact",
                reference_id="artifact-001",
            )
        ],
        expected_output_type="research_review_set",
        acceptance_criteria=[
            "Return a deterministic decision."
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


class SuccessfulSourceCriticExecutor(
    ResearchSourceCriticExecutor
):
    """Return one source critique."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceCriticExecutionResult:
        return ResearchSourceCriticExecutionResult(
            requested_source_count=1,
            critiques=[
                ResearchSourceCritique(
                    critique_id="critique-001",
                    source_id="source-001",
                    decision=ResearchSourceDecision.APPROVED,
                    authority_score=0.9,
                    relevance_score=0.95,
                    recency_score=0.8,
                    transparency_score=0.9,
                    overall_score=0.89,
                    rationale="The source is authoritative.",
                )
            ],
            tool_call_count=1,
        )


class PartialSourceCriticExecutor(
    ResearchSourceCriticExecutor
):
    """Return one critique and one failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceCriticExecutionResult:
        return ResearchSourceCriticExecutionResult(
            requested_source_count=2,
            critiques=[
                ResearchSourceCritique(
                    critique_id="critique-001",
                    source_id="source-001",
                    decision=ResearchSourceDecision.APPROVED,
                    authority_score=0.9,
                    relevance_score=0.9,
                    recency_score=0.9,
                    transparency_score=0.9,
                    overall_score=0.9,
                    rationale="Approved.",
                )
            ],
            failures=[
                ResearchSourceCriticFailure(
                    source_id="source-002",
                    code="SOURCE_UNAVAILABLE",
                    message="Source unavailable.",
                )
            ],
        )


class FailingSourceCriticExecutor(
    ResearchSourceCriticExecutor
):
    """Raise one source critic executor error."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceCriticExecutionResult:
        raise ResearchSourceCriticExecutorError(
            "Critic unavailable.",
            retryable=True,
        )


class SuccessfulCitationExecutor(
    ResearchCitationVerifierExecutor
):
    """Return one verified citation."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchCitationVerifierExecutionResult:
        return ResearchCitationVerifierExecutionResult(
            requested_citation_count=1,
            verifications=[
                ResearchCitationVerification(
                    verification_id="verification-001",
                    claim_id="claim-001",
                    citation_id="citation-001",
                    evidence_id="evidence-001",
                    source_id="source-001",
                    decision=ResearchCitationDecision.VERIFIED,
                    entailment_score=0.95,
                    traceability_score=1.0,
                    citation_accuracy_score=0.95,
                    rationale="The citation supports the claim.",
                )
            ],
            tool_call_count=1,
        )


class PartialCitationExecutor(
    ResearchCitationVerifierExecutor
):
    """Return one verification and one failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchCitationVerifierExecutionResult:
        return ResearchCitationVerifierExecutionResult(
            requested_citation_count=2,
            verifications=[
                ResearchCitationVerification(
                    verification_id="verification-001",
                    claim_id="claim-001",
                    citation_id="citation-001",
                    evidence_id="evidence-001",
                    source_id="source-001",
                    decision=ResearchCitationDecision.VERIFIED,
                    entailment_score=0.9,
                    traceability_score=0.9,
                    citation_accuracy_score=0.9,
                    rationale="Verified.",
                )
            ],
            failures=[
                ResearchCitationVerificationFailure(
                    citation_id="citation-002",
                    code="EVIDENCE_MISSING",
                    message="Evidence missing.",
                )
            ],
        )


class FailingCitationExecutor(
    ResearchCitationVerifierExecutor
):
    """Raise one citation verifier executor error."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchCitationVerifierExecutionResult:
        raise ResearchCitationVerifierExecutorError(
            "Verifier unavailable.",
            retryable=True,
        )


def source_critic(
    executor: ResearchSourceCriticExecutor,
) -> SourceCriticAgent:
    """Return deterministic source critic."""

    return SourceCriticAgent(
        profile=specialist_profile(
            ResearchAgentRole.SOURCE_CRITIC,
            ResearchAgentCapability.EVALUATE_SOURCES,
        ),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            7,
            30,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-critic-001",
        output_reference_id_factory=(
            lambda: "source-review-set-001"
        ),
    )


def citation_verifier(
    executor: ResearchCitationVerifierExecutor,
) -> CitationVerifierAgent:
    """Return deterministic citation verifier."""

    return CitationVerifierAgent(
        profile=specialist_profile(
            ResearchAgentRole.CITATION_VERIFIER,
            ResearchAgentCapability.VERIFY_CITATIONS,
        ),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            7,
            31,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-citation-001",
        output_reference_id_factory=(
            lambda: "citation-review-set-001"
        ),
    )


def test_source_critic_returns_success() -> None:
    value = source_critic(
        SuccessfulSourceCriticExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SOURCE_CRITIC,
            capability=(
                ResearchAgentCapability.EVALUATE_SOURCES
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.SUCCEEDED
    assert len(value.payload["critiques"]) == 1
    assert value.primary_output() is not None


def test_source_critic_returns_partial() -> None:
    value = source_critic(
        PartialSourceCriticExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SOURCE_CRITIC,
            capability=(
                ResearchAgentCapability.EVALUATE_SOURCES
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.PARTIAL
    assert value.failure is not None
    assert value.failure.code == "PARTIAL_SOURCE_REVIEW"


def test_source_critic_converts_executor_error() -> None:
    value = source_critic(
        FailingSourceCriticExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SOURCE_CRITIC,
            capability=(
                ResearchAgentCapability.EVALUATE_SOURCES
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.FAILED
    assert value.failure is not None
    assert value.failure.retryable is True


def test_citation_verifier_returns_success() -> None:
    value = citation_verifier(
        SuccessfulCitationExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CITATION_VERIFIER,
            capability=(
                ResearchAgentCapability.VERIFY_CITATIONS
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.SUCCEEDED
    assert len(value.payload["verifications"]) == 1
    assert value.primary_output() is not None


def test_citation_verifier_returns_partial() -> None:
    value = citation_verifier(
        PartialCitationExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CITATION_VERIFIER,
            capability=(
                ResearchAgentCapability.VERIFY_CITATIONS
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.PARTIAL
    assert value.failure is not None
    assert value.failure.code == (
        "PARTIAL_CITATION_VERIFICATION"
    )


def test_citation_verifier_converts_executor_error() -> None:
    value = citation_verifier(
        FailingCitationExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CITATION_VERIFIER,
            capability=(
                ResearchAgentCapability.VERIFY_CITATIONS
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.FAILED
    assert value.failure is not None
    assert value.failure.retryable is True


def test_source_critic_rejects_wrong_role() -> None:
    profile = specialist_profile(
        ResearchAgentRole.SOURCE_READER,
        ResearchAgentCapability.EVALUATE_SOURCES,
    )

    with pytest.raises(
        SourceCriticAgentError,
        match="source critic must have source_critic role",
    ):
        SourceCriticAgent(
            profile=profile,
            executor=SuccessfulSourceCriticExecutor(),
        )


def test_citation_verifier_rejects_wrong_role() -> None:
    profile = specialist_profile(
        ResearchAgentRole.CLAIM_ANALYST,
        ResearchAgentCapability.VERIFY_CITATIONS,
    )

    with pytest.raises(
        CitationVerifierAgentError,
        match=(
            "citation verifier must have "
            "citation_verifier role"
        ),
    ):
        CitationVerifierAgent(
            profile=profile,
            executor=SuccessfulCitationExecutor(),
        )


def test_review_agents_reject_empty_inputs() -> None:
    source_assignment = assignment(
        role=ResearchAgentRole.SOURCE_CRITIC,
        capability=ResearchAgentCapability.EVALUATE_SOURCES,
    ).model_copy(update={"inputs": []})

    with pytest.raises(
        SourceCriticAgentError,
        match="source review assignment must include",
    ):
        source_critic(
            SuccessfulSourceCriticExecutor()
        ).execute(source_assignment)

    citation_assignment = assignment(
        role=ResearchAgentRole.CITATION_VERIFIER,
        capability=ResearchAgentCapability.VERIFY_CITATIONS,
    ).model_copy(update={"inputs": []})

    with pytest.raises(
        CitationVerifierAgentError,
        match=(
            "citation verification assignment must include"
        ),
    ):
        citation_verifier(
            SuccessfulCitationExecutor()
        ).execute(citation_assignment)
