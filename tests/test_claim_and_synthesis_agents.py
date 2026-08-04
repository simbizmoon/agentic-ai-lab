"""Tests for claim analyst and synthesis specialist agents."""

from datetime import UTC, datetime

import pytest

from app.research.claim_analyst_agent import ClaimAnalystAgent
from app.research.research_claim_executor import (
    ResearchClaimConstructionFailure,
    ResearchClaimExecutionResult,
    ResearchClaimExecutor,
    ResearchClaimExecutorError,
    ResearchConstructedCitation,
    ResearchConstructedClaim,
)
from app.research.research_claim_synthesis_agent_error import (
    ClaimAnalystAgentError,
    SynthesisSpecialistAgentError,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesisExecutionResult,
    ResearchSynthesisExecutor,
    ResearchSynthesisExecutorError,
    ResearchSynthesisFailure,
    ResearchSynthesizedReport,
    ResearchSynthesizedSection,
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
from app.schemas.research_agent_result import (
    ResearchAgentResultStatus,
)


def identity(
    agent_id: str,
    role: ResearchAgentRole,
) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=role.value,
        role=role,
        description=f"{role.value} agent.",
    )


def manager_profile(
    role: ResearchAgentRole,
) -> ResearchAgentCapabilityProfile:
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
        title="Build research output",
        objective="Produce structured research output.",
        instructions=["Use traceable research artifacts."],
        inputs=[
            ResearchAgentAssignmentInput(
                name="input-001",
                reference_type="research_artifact",
                reference_id="artifact-001",
            )
        ],
        expected_output_type="research_output",
        acceptance_criteria=[
            "Return a structured output."
        ],
        status=ResearchAgentAssignmentStatus.IN_PROGRESS,
        attempt_number=1,
        maximum_attempts=2,
    )


def constructed_claim() -> ResearchConstructedClaim:
    citation = ResearchConstructedCitation(
        citation_id="citation-001",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        location_reference="paragraph-2",
    )

    return ResearchConstructedClaim(
        claim_id="claim-001",
        text="Structured messages support agent collaboration.",
        rationale="The evidence directly describes message use.",
        confidence_score=0.9,
        evidence_ids=["evidence-001"],
        citations=[citation],
    )


class SuccessfulClaimExecutor(ResearchClaimExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchClaimExecutionResult:
        return ResearchClaimExecutionResult(
            requested_evidence_group_count=1,
            claims=[constructed_claim()],
            tool_call_count=1,
            input_token_count=20,
            output_token_count=10,
        )


class PartialClaimExecutor(ResearchClaimExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchClaimExecutionResult:
        return ResearchClaimExecutionResult(
            requested_evidence_group_count=2,
            claims=[constructed_claim()],
            failures=[
                ResearchClaimConstructionFailure(
                    evidence_group_id="group-002",
                    code="INSUFFICIENT_EVIDENCE",
                    message="Evidence was insufficient.",
                )
            ],
        )


class FailingClaimExecutor(ResearchClaimExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchClaimExecutionResult:
        raise ResearchClaimExecutorError(
            "Claim provider unavailable.",
            retryable=True,
        )


def report() -> ResearchSynthesizedReport:
    return ResearchSynthesizedReport(
        report_id="report-001",
        title="Multi-Agent Research",
        executive_summary=(
            "Structured specialist collaboration improves "
            "research traceability."
        ),
        sections=[
            ResearchSynthesizedSection(
                section_id="section-001",
                heading="Findings",
                content="Agents collaborate through messages.",
                claim_ids=["claim-001"],
                order=1,
            ),
            ResearchSynthesizedSection(
                section_id="section-002",
                heading="Implications",
                content="Role separation enables review.",
                claim_ids=["claim-001"],
                order=2,
            ),
        ],
        limitations=["The current system is deterministic."],
        follow_up_questions=[
            "How should parallel execution be evaluated?"
        ],
    )


class SuccessfulSynthesisExecutor(ResearchSynthesisExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        return ResearchSynthesisExecutionResult(
            requested_section_count=2,
            report=report(),
            tool_call_count=1,
            input_token_count=30,
            output_token_count=40,
        )


class PartialSynthesisExecutor(ResearchSynthesisExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        partial_report = ResearchSynthesizedReport(
            report_id="report-001",
            title="Multi-Agent Research",
            executive_summary="Partial report.",
            sections=[
                ResearchSynthesizedSection(
                    section_id="section-001",
                    heading="Findings",
                    content="Partial findings.",
                    claim_ids=["claim-001"],
                    order=1,
                )
            ],
        )

        return ResearchSynthesisExecutionResult(
            requested_section_count=2,
            report=partial_report,
            failures=[
                ResearchSynthesisFailure(
                    section_key="implications",
                    code="SECTION_FAILED",
                    message="Section could not be synthesized.",
                )
            ],
        )


class FailingSynthesisExecutor(ResearchSynthesisExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSynthesisExecutionResult:
        raise ResearchSynthesisExecutorError(
            "Synthesis provider unavailable.",
            retryable=True,
        )


def claim_agent(
    executor: ResearchClaimExecutor,
) -> ClaimAnalystAgent:
    return ClaimAnalystAgent(
        profile=specialist_profile(
            ResearchAgentRole.CLAIM_ANALYST,
            ResearchAgentCapability.BUILD_CLAIMS,
        ),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            8,
            0,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-claim-001",
        output_reference_id_factory=(
            lambda: "claim-set-001"
        ),
    )


def synthesis_agent(
    executor: ResearchSynthesisExecutor,
) -> SynthesisSpecialistAgent:
    return SynthesisSpecialistAgent(
        profile=specialist_profile(
            ResearchAgentRole.SYNTHESIS_SPECIALIST,
            ResearchAgentCapability.SYNTHESIZE_REPORT,
        ),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            8,
            1,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-synthesis-001",
        output_reference_id_factory=(
            lambda: "report-output-001"
        ),
    )


def test_claim_analyst_returns_success() -> None:
    value = claim_agent(
        SuccessfulClaimExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CLAIM_ANALYST,
            capability=ResearchAgentCapability.BUILD_CLAIMS,
        )
    )

    assert value.status is ResearchAgentResultStatus.SUCCEEDED
    assert value.metrics.claim_count == 1
    assert value.metrics.evidence_count == 1
    assert len(value.payload["claims"]) == 1


def test_claim_analyst_returns_partial() -> None:
    value = claim_agent(
        PartialClaimExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CLAIM_ANALYST,
            capability=ResearchAgentCapability.BUILD_CLAIMS,
        )
    )

    assert value.status is ResearchAgentResultStatus.PARTIAL
    assert value.failure is not None
    assert value.failure.code == (
        "PARTIAL_CLAIM_CONSTRUCTION"
    )


def test_claim_analyst_converts_executor_error() -> None:
    value = claim_agent(
        FailingClaimExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.CLAIM_ANALYST,
            capability=ResearchAgentCapability.BUILD_CLAIMS,
        )
    )

    assert value.status is ResearchAgentResultStatus.FAILED
    assert value.failure is not None
    assert value.failure.retryable is True


def test_synthesis_specialist_returns_success() -> None:
    value = synthesis_agent(
        SuccessfulSynthesisExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
            capability=(
                ResearchAgentCapability.SYNTHESIZE_REPORT
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.SUCCEEDED
    assert value.payload["report"]["report_id"] == "report-001"
    assert value.metrics.claim_count == 2


def test_synthesis_specialist_returns_partial() -> None:
    value = synthesis_agent(
        PartialSynthesisExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
            capability=(
                ResearchAgentCapability.SYNTHESIZE_REPORT
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.PARTIAL
    assert value.failure is not None
    assert value.failure.code == (
        "PARTIAL_REPORT_SYNTHESIS"
    )


def test_synthesis_specialist_converts_executor_error() -> None:
    value = synthesis_agent(
        FailingSynthesisExecutor()
    ).execute(
        assignment(
            role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
            capability=(
                ResearchAgentCapability.SYNTHESIZE_REPORT
            ),
        )
    )

    assert value.status is ResearchAgentResultStatus.FAILED
    assert value.failure is not None
    assert value.failure.retryable is True


def test_claim_analyst_rejects_wrong_role() -> None:
    profile = specialist_profile(
        ResearchAgentRole.EVIDENCE_ANALYST,
        ResearchAgentCapability.BUILD_CLAIMS,
    )

    with pytest.raises(
        ClaimAnalystAgentError,
        match="claim analyst must have claim_analyst role",
    ):
        ClaimAnalystAgent(
            profile=profile,
            executor=SuccessfulClaimExecutor(),
        )


def test_synthesis_specialist_rejects_wrong_role() -> None:
    profile = specialist_profile(
        ResearchAgentRole.CLAIM_ANALYST,
        ResearchAgentCapability.SYNTHESIZE_REPORT,
    )

    with pytest.raises(
        SynthesisSpecialistAgentError,
        match=(
            "synthesis specialist must have "
            "synthesis_specialist role"
        ),
    ):
        SynthesisSpecialistAgent(
            profile=profile,
            executor=SuccessfulSynthesisExecutor(),
        )


def test_claim_and_synthesis_require_inputs() -> None:
    claim_assignment = assignment(
        role=ResearchAgentRole.CLAIM_ANALYST,
        capability=ResearchAgentCapability.BUILD_CLAIMS,
    ).model_copy(update={"inputs": []})

    with pytest.raises(
        ClaimAnalystAgentError,
        match="claim assignment must include evidence inputs",
    ):
        claim_agent(
            SuccessfulClaimExecutor()
        ).execute(claim_assignment)

    synthesis_assignment = assignment(
        role=ResearchAgentRole.SYNTHESIS_SPECIALIST,
        capability=ResearchAgentCapability.SYNTHESIZE_REPORT,
    ).model_copy(update={"inputs": []})

    with pytest.raises(
        SynthesisSpecialistAgentError,
        match="synthesis assignment must include claim inputs",
    ):
        synthesis_agent(
            SuccessfulSynthesisExecutor()
        ).execute(synthesis_assignment)
