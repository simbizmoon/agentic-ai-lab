"""Tests for the deterministic evidence analyst agent."""

from datetime import UTC, datetime

import pytest

from app.research.evidence_analyst_agent import (
    EvidenceAnalystAgent,
)
from app.research.evidence_analyst_agent_error import (
    EvidenceAnalystAgentError,
)
from app.research.research_evidence_executor import (
    ResearchEvidenceDocumentFailure,
    ResearchEvidenceExecutionResult,
    ResearchEvidenceExecutor,
    ResearchEvidenceExecutorError,
    ResearchExtractedEvidence,
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
    name: str,
) -> ResearchAgentIdentity:
    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager() -> ResearchAgentIdentity:
    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def analyst() -> ResearchAgentIdentity:
    return identity(
        agent_id="agent-evidence-001",
        role=ResearchAgentRole.EVIDENCE_ANALYST,
        name="Evidence Analyst",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.EVIDENCE_ANALYST,
        ],
    )


def analyst_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    return ResearchAgentCapabilityProfile(
        profile_id="profile-evidence-001",
        agent=agent or analyst(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.EXTRACT_EVIDENCE,
            ]
        ),
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    values: dict[str, object] = {
        "assignment_id": "assignment-evidence-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "research_task_id": "task-001",
        "assigner_profile": manager_profile(),
        "assignee": analyst(),
        "required_role": (
            ResearchAgentRole.EVIDENCE_ANALYST
        ),
        "required_capabilities": [
            ResearchAgentCapability.EXTRACT_EVIDENCE,
        ],
        "title": "Extract evidence",
        "objective": (
            "Extract traceable evidence from documents."
        ),
        "instructions": [
            "Preserve document and source references."
        ],
        "inputs": [
            ResearchAgentAssignmentInput(
                name="document-001",
                reference_type="research_source_document",
                reference_id="document-001",
            ),
            ResearchAgentAssignmentInput(
                name="document-002",
                reference_type="research_source_document",
                reference_id="document-002",
            ),
        ],
        "expected_output_type": "research_evidence_set",
        "acceptance_criteria": [
            "Every evidence item references a document."
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


def evidence(
    *,
    evidence_id: str,
    document_id: str,
    source_id: str,
) -> ResearchExtractedEvidence:
    return ResearchExtractedEvidence(
        evidence_id=evidence_id,
        document_id=document_id,
        source_id=source_id,
        text="Agents exchange structured messages.",
        interpretation=(
            "Structured messages support collaboration."
        ),
        relevance_score=0.9,
        confidence_score=0.85,
        location_reference="paragraph-2",
    )


class SuccessfulExecutor(ResearchEvidenceExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        return ResearchEvidenceExecutionResult(
            requested_document_count=2,
            evidence=[
                evidence(
                    evidence_id="evidence-001",
                    document_id="document-001",
                    source_id="source-001",
                ),
                evidence(
                    evidence_id="evidence-002",
                    document_id="document-002",
                    source_id="source-002",
                ),
            ],
            tool_call_count=2,
            duration_ms=180,
            input_token_count=30,
            output_token_count=20,
            metadata={
                "provider": "test-evidence",
            },
        )


class PartialExecutor(ResearchEvidenceExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        return ResearchEvidenceExecutionResult(
            requested_document_count=2,
            evidence=[
                evidence(
                    evidence_id="evidence-001",
                    document_id="document-001",
                    source_id="source-001",
                )
            ],
            failures=[
                ResearchEvidenceDocumentFailure(
                    document_id="document-002",
                    source_id="source-002",
                    code="NO_RELEVANT_EVIDENCE",
                    message="No relevant evidence found.",
                )
            ],
        )


class EmptyExecutor(ResearchEvidenceExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        return ResearchEvidenceExecutionResult(
            requested_document_count=2,
            failures=[
                ResearchEvidenceDocumentFailure(
                    document_id="document-001",
                    source_id="source-001",
                    code="EXTRACTION_TIMEOUT",
                    message="Extraction timed out.",
                    retryable=True,
                ),
                ResearchEvidenceDocumentFailure(
                    document_id="document-002",
                    source_id="source-002",
                    code="EXTRACTION_TIMEOUT",
                    message="Extraction timed out.",
                    retryable=True,
                ),
            ],
        )


class FailingExecutor(ResearchEvidenceExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        raise ResearchEvidenceExecutorError(
            "Evidence provider unavailable.",
            code="EVIDENCE_PROVIDER_UNAVAILABLE",
            retryable=True,
        )


class RuntimeFailingExecutor(ResearchEvidenceExecutor):
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        raise RuntimeError("Unexpected evidence failure.")


def agent(
    executor: ResearchEvidenceExecutor,
    *,
    profile: ResearchAgentCapabilityProfile | None = None,
) -> EvidenceAnalystAgent:
    return EvidenceAnalystAgent(
        profile=profile or analyst_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            7,
            0,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-evidence-001",
        output_reference_id_factory=(
            lambda: "evidence-set-001"
        ),
    )


def test_evidence_analyst_returns_success() -> None:
    value = agent(SuccessfulExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.payload["evidence_count"] == 2
    assert value.metrics.evidence_count == 2
    assert value.metrics.total_token_count == 50
    assert value.primary_output() is not None
    assert (
        value.primary_output().reference_id
        == "evidence-set-001"
    )


def test_evidence_analyst_returns_partial_result() -> None:
    value = agent(PartialExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.PARTIAL
    )
    assert value.failure is not None
    assert value.failure.code == (
        "PARTIAL_EVIDENCE_EXTRACTION"
    )
    assert value.payload["failed_document_count"] == 1


def test_evidence_analyst_returns_failed_when_empty() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.code == "NO_EVIDENCE_EXTRACTED"
    assert value.failure.retryable is True
    assert value.can_retry is True


def test_evidence_analyst_disables_retry_at_limit() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment(
            attempt_number=2,
            maximum_attempts=2,
        )
    )

    assert value.failure is not None
    assert value.failure.retryable is False


def test_evidence_analyst_converts_executor_error() -> None:
    value = agent(FailingExecutor()).execute(
        assignment()
    )

    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.TOOL
    )
    assert value.failure.code == (
        "EVIDENCE_PROVIDER_UNAVAILABLE"
    )


def test_evidence_analyst_converts_runtime_error() -> None:
    value = agent(RuntimeFailingExecutor()).execute(
        assignment()
    )

    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.INTERNAL
    )
    assert value.failure.code == (
        "UNEXPECTED_EVIDENCE_ERROR"
    )


def test_evidence_analyst_requires_correct_role() -> None:
    wrong = identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )

    with pytest.raises(
        EvidenceAnalystAgentError,
        match=(
            "evidence analyst must have "
            "evidence_analyst role"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=analyst_profile(agent=wrong),
        )


def test_evidence_analyst_requires_capability() -> None:
    profile = analyst_profile(
        capabilities=[
            ResearchAgentCapability.READ_SOURCES,
        ]
    )

    with pytest.raises(
        EvidenceAnalystAgentError,
        match=(
            "evidence analyst requires "
            "extract_evidence capability"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        )


def test_evidence_analyst_rejects_wrong_assignee() -> None:
    other = identity(
        agent_id="agent-evidence-002",
        role=ResearchAgentRole.EVIDENCE_ANALYST,
        name="Other Evidence Analyst",
    )

    with pytest.raises(
        EvidenceAnalystAgentError,
        match=(
            "assignment assignee must match "
            "evidence analyst"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
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
def test_evidence_analyst_rejects_status(
    status: ResearchAgentAssignmentStatus,
) -> None:
    with pytest.raises(
        EvidenceAnalystAgentError,
        match="assignment status is not executable",
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(status=status)
        )


def test_evidence_assignment_requires_inputs() -> None:
    with pytest.raises(
        EvidenceAnalystAgentError,
        match=(
            "evidence assignment must include "
            "document inputs"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(inputs=[])
        )


def test_evidence_assignment_requires_capability() -> None:
    profile = analyst_profile(
        capabilities=[
            ResearchAgentCapability.EXTRACT_EVIDENCE,
            ResearchAgentCapability.READ_SOURCES,
        ]
    )

    with pytest.raises(
        EvidenceAnalystAgentError,
        match=(
            "evidence assignment must require "
            "extract_evidence capability"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        ).execute(
            assignment(
                required_capabilities=[
                    ResearchAgentCapability.READ_SOURCES,
                ]
            )
        )


def test_evidence_analyst_rejects_blank_result_id() -> None:
    analyst_agent = EvidenceAnalystAgent(
        profile=analyst_profile(),
        executor=SuccessfulExecutor(),
        result_id_factory=lambda: " ",
    )

    with pytest.raises(
        EvidenceAnalystAgentError,
        match="result_id factory returned blank value",
    ):
        analyst_agent.execute(assignment())


def test_evidence_analyst_exposes_identity() -> None:
    analyst_agent = agent(SuccessfulExecutor())

    assert analyst_agent.identity.agent_id == (
        "agent-evidence-001"
    )
    assert analyst_agent.profile.profile_id == (
        "profile-evidence-001"
    )
