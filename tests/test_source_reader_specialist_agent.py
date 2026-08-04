"""Tests for the deterministic source reader specialist."""

from datetime import UTC, datetime

import pytest

from app.research.research_source_reader_executor import (
    ResearchReadDocument,
    ResearchSourceReaderExecutionResult,
    ResearchSourceReaderExecutor,
    ResearchSourceReaderExecutorError,
    ResearchSourceReadFailure,
)
from app.research.source_reader_specialist_agent import (
    SourceReaderSpecialistAgent,
)
from app.research.source_reader_specialist_agent_error import (
    SourceReaderSpecialistAgentError,
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
    """Return one agent identity."""

    return ResearchAgentIdentity(
        agent_id=agent_id,
        name=name,
        role=role,
        description=f"{name} agent.",
    )


def manager() -> ResearchAgentIdentity:
    """Return the manager identity."""

    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def reader() -> ResearchAgentIdentity:
    """Return the source reader identity."""

    return identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return a manager delegation profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SOURCE_READER,
        ],
    )


def reader_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return a source reader profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-reader-001",
        agent=agent or reader(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.READ_SOURCES,
            ]
        ),
    )


def source_input(
    *,
    source_id: str = "source-001",
) -> ResearchAgentAssignmentInput:
    """Return one source assignment input."""

    return ResearchAgentAssignmentInput(
        name=f"source-{source_id}",
        reference_type="research_source_candidate",
        reference_id=source_id,
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one executable source reader assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-reader-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "research_task_id": "task-001",
        "assigner_profile": manager_profile(),
        "assignee": reader(),
        "required_role": ResearchAgentRole.SOURCE_READER,
        "required_capabilities": [
            ResearchAgentCapability.READ_SOURCES,
        ],
        "title": "Read selected sources",
        "objective": "Read and normalize source documents.",
        "instructions": [
            "Read every supplied source."
        ],
        "inputs": [
            source_input(source_id="source-001"),
            source_input(source_id="source-002"),
        ],
        "expected_output_type": (
            "research_source_document_set"
        ),
        "acceptance_criteria": [
            "Return normalized documents."
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


class SuccessfulExecutor(ResearchSourceReaderExecutor):
    """Return two successfully read documents."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        assert len(assignment.inputs) == 2

        return ResearchSourceReaderExecutionResult(
            requested_source_count=2,
            documents=[
                ResearchReadDocument(
                    document_id="document-001",
                    source_id="source-001",
                    title="Agent Memory",
                    content="Agent memory stores useful context.",
                    location="https://example.test/source-001",
                    word_count=6,
                ),
                ResearchReadDocument(
                    document_id="document-002",
                    source_id="source-002",
                    title="Multi-Agent Systems",
                    content="Agents collaborate through messages.",
                    location="https://example.test/source-002",
                    word_count=5,
                ),
            ],
            tool_call_count=2,
            duration_ms=200,
            input_token_count=20,
            output_token_count=40,
            metadata={
                "provider": "test-reader",
            },
        )


class PartialExecutor(ResearchSourceReaderExecutor):
    """Return one document and one source failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        return ResearchSourceReaderExecutionResult(
            requested_source_count=2,
            documents=[
                ResearchReadDocument(
                    document_id="document-001",
                    source_id="source-001",
                    title="Agent Memory",
                    content="Agent memory content.",
                    word_count=3,
                )
            ],
            failures=[
                ResearchSourceReadFailure(
                    source_id="source-002",
                    code="SOURCE_UNAVAILABLE",
                    message="The source was unavailable.",
                    retryable=False,
                )
            ],
            tool_call_count=2,
            duration_ms=150,
        )


class EmptyExecutor(ResearchSourceReaderExecutor):
    """Return no documents and two failures."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        return ResearchSourceReaderExecutionResult(
            requested_source_count=2,
            failures=[
                ResearchSourceReadFailure(
                    source_id="source-001",
                    code="SOURCE_TIMEOUT",
                    message="Source read timed out.",
                    retryable=True,
                ),
                ResearchSourceReadFailure(
                    source_id="source-002",
                    code="SOURCE_TIMEOUT",
                    message="Source read timed out.",
                    retryable=True,
                ),
            ],
            tool_call_count=2,
            duration_ms=300,
        )


class FailingExecutor(ResearchSourceReaderExecutor):
    """Raise one structured reader failure."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        raise ResearchSourceReaderExecutorError(
            "Reader provider is temporarily unavailable.",
            code="READER_PROVIDER_UNAVAILABLE",
            retryable=True,
            details={
                "provider": "test-reader",
            },
        )


class UnexpectedExecutor(ResearchSourceReaderExecutor):
    """Raise one expected runtime exception."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        raise RuntimeError("Unexpected reader failure.")


def agent(
    executor: ResearchSourceReaderExecutor,
    *,
    profile: ResearchAgentCapabilityProfile | None = None,
) -> SourceReaderSpecialistAgent:
    """Return one deterministic source reader agent."""

    return SourceReaderSpecialistAgent(
        profile=profile or reader_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            6,
            30,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-reader-001",
        output_reference_id_factory=(
            lambda: "document-set-001"
        ),
    )


def test_source_reader_returns_success_result() -> None:
    value = agent(SuccessfulExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.succeeded is True
    assert value.failure is None
    assert value.payload["document_count"] == 2
    assert value.payload["failed_source_count"] == 0
    assert len(value.payload["documents"]) == 2
    assert value.metrics.source_count == 2
    assert value.metrics.total_token_count == 60
    assert value.primary_output() is not None
    assert (
        value.primary_output().reference_id
        == "document-set-001"
    )


def test_source_reader_returns_partial_result() -> None:
    value = agent(PartialExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.PARTIAL
    )
    assert value.failure is not None
    assert value.failure.code == "PARTIAL_SOURCE_READ"
    assert value.payload["document_count"] == 1
    assert value.payload["failed_source_count"] == 1


def test_source_reader_returns_failed_result_when_empty() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.code == (
        "NO_SOURCE_DOCUMENTS_READ"
    )
    assert value.failure.retryable is True
    assert value.can_retry is True


def test_source_reader_disables_retry_at_limit() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment(
            attempt_number=2,
            maximum_attempts=2,
        )
    )

    assert value.failure is not None
    assert value.failure.retryable is False
    assert value.can_retry is False


def test_source_reader_converts_executor_error() -> None:
    value = agent(FailingExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.SOURCE
    )
    assert value.failure.code == (
        "READER_PROVIDER_UNAVAILABLE"
    )
    assert value.failure.retryable is True


def test_source_reader_converts_runtime_error() -> None:
    value = agent(UnexpectedExecutor()).execute(
        assignment()
    )

    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.INTERNAL
    )
    assert value.failure.code == (
        "UNEXPECTED_SOURCE_READER_ERROR"
    )
    assert value.failure.retryable is False


def test_source_reader_requires_correct_role() -> None:
    wrong_agent = identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )
    profile = reader_profile(agent=wrong_agent)

    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match=(
            "source reader must have source_reader role"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        )


def test_source_reader_requires_capability() -> None:
    profile = reader_profile(
        capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ]
    )

    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match=(
            "source reader requires read_sources capability"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        )


def test_source_reader_rejects_wrong_assignee() -> None:
    other_reader = identity(
        agent_id="agent-reader-002",
        role=ResearchAgentRole.SOURCE_READER,
        name="Other Reader",
    )

    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match=(
            "assignment assignee must match source reader"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(assignee=other_reader)
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
def test_source_reader_rejects_non_executable_status(
    status: ResearchAgentAssignmentStatus,
) -> None:
    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match="assignment status is not executable",
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(status=status)
        )


def test_source_reader_rejects_missing_inputs() -> None:
    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match=(
            "source-reading assignment must include "
            "source inputs"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(inputs=[])
        )


def test_source_reader_assignment_requires_read_capability() -> None:
    profile = reader_profile(
        capabilities=[
            ResearchAgentCapability.READ_SOURCES,
            ResearchAgentCapability.SEARCH_SOURCES,
        ]
    )

    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match=(
            "source-reading assignment must require "
            "read_sources capability"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        ).execute(
            assignment(
                required_capabilities=[
                    ResearchAgentCapability.SEARCH_SOURCES,
                ]
            )
        )


def test_source_reader_rejects_blank_result_id() -> None:
    specialist_agent = SourceReaderSpecialistAgent(
        profile=reader_profile(),
        executor=SuccessfulExecutor(),
        result_id_factory=lambda: " ",
    )

    with pytest.raises(
        SourceReaderSpecialistAgentError,
        match="result_id factory returned blank value",
    ):
        specialist_agent.execute(assignment())


def test_source_reader_exposes_identity_and_profile() -> None:
    specialist_agent = agent(SuccessfulExecutor())

    assert specialist_agent.identity.agent_id == (
        "agent-reader-001"
    )
    assert specialist_agent.profile.profile_id == (
        "profile-reader-001"
    )
