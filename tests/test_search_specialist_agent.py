"""Tests for the deterministic search specialist agent."""

from datetime import UTC, datetime

import pytest

from app.research.research_search_executor import (
    ResearchSearchExecutionResult,
    ResearchSearchExecutor,
    ResearchSearchExecutorError,
    ResearchSearchHit,
)
from app.research.search_specialist_agent import (
    SearchSpecialistAgent,
)
from app.research.search_specialist_agent_error import (
    SearchSpecialistAgentError,
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
    """Return one manager identity."""

    return identity(
        agent_id="agent-manager-001",
        role=ResearchAgentRole.MANAGER,
        name="Research Manager",
    )


def specialist() -> ResearchAgentIdentity:
    """Return one search specialist identity."""

    return identity(
        agent_id="agent-search-001",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Search Specialist",
    )


def manager_profile() -> ResearchAgentCapabilityProfile:
    """Return one manager profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-manager-001",
        agent=manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )


def specialist_profile(
    *,
    agent: ResearchAgentIdentity | None = None,
    capabilities: list[
        ResearchAgentCapability
    ] | None = None,
) -> ResearchAgentCapabilityProfile:
    """Return one search specialist profile."""

    return ResearchAgentCapabilityProfile(
        profile_id="profile-search-001",
        agent=agent or specialist(),
        capabilities=(
            capabilities
            if capabilities is not None
            else [
                ResearchAgentCapability.SEARCH_SOURCES,
                ResearchAgentCapability.PLAN_QUERIES,
            ]
        ),
    )


def assignment(
    **overrides: object,
) -> ResearchAgentTaskAssignment:
    """Return one executable search assignment."""

    values: dict[str, object] = {
        "assignment_id": "assignment-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "research_task_id": "task-001",
        "assigner_profile": manager_profile(),
        "assignee": specialist(),
        "required_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "required_capabilities": [
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
        "title": "Find sources",
        "objective": "Find authoritative sources.",
        "instructions": [
            "Use the approved queries."
        ],
        "expected_output_type": (
            "research_source_candidate_set"
        ),
        "acceptance_criteria": [
            "Return normalized source candidates."
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


class SuccessfulExecutor(ResearchSearchExecutor):
    """Return deterministic search results."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        assert assignment.assignment_id == "assignment-001"

        return ResearchSearchExecutionResult(
            hits=[
                ResearchSearchHit(
                    source_id="source-001",
                    title="Agent Memory",
                    location="https://example.test/source-001",
                    snippet="A source about agent memory.",
                    score=0.9,
                    query_id="query-001",
                ),
                ResearchSearchHit(
                    source_id="source-002",
                    title="Multi-Agent Research",
                    location="https://example.test/source-002",
                    score=0.8,
                    query_id="query-002",
                ),
            ],
            query_count=2,
            tool_call_count=2,
            duration_ms=150,
            input_token_count=10,
            output_token_count=20,
            metadata={
                "provider": "test-search",
            },
        )


class EmptyExecutor(ResearchSearchExecutor):
    """Return a valid empty search result."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        return ResearchSearchExecutionResult(
            hits=[],
            query_count=1,
            tool_call_count=1,
            duration_ms=25,
        )


class RetryableFailingExecutor(ResearchSearchExecutor):
    """Raise a retryable structured search error."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        raise ResearchSearchExecutorError(
            "Search provider is temporarily unavailable.",
            code="SEARCH_PROVIDER_UNAVAILABLE",
            retryable=True,
            details={
                "provider": "test-search",
            },
        )


class UnexpectedFailingExecutor(ResearchSearchExecutor):
    """Raise an unexpected runtime exception."""

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        raise RuntimeError("Unexpected failure.")


def agent(
    executor: ResearchSearchExecutor,
    *,
    profile: ResearchAgentCapabilityProfile | None = None,
) -> SearchSpecialistAgent:
    """Return one deterministic search specialist."""

    return SearchSpecialistAgent(
        profile=profile or specialist_profile(),
        executor=executor,
        now=lambda: datetime(
            2026,
            8,
            4,
            6,
            0,
            tzinfo=UTC,
        ),
        result_id_factory=lambda: "result-001",
        output_reference_id_factory=(
            lambda: "source-set-001"
        ),
    )


def test_search_specialist_returns_success_result() -> None:
    value = agent(SuccessfulExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.succeeded is True
    assert value.metrics.source_count == 2
    assert value.metrics.tool_call_count == 2
    assert value.metrics.total_token_count == 30
    assert value.payload["query_count"] == 2
    assert value.payload["hit_count"] == 2
    assert len(value.payload["hits"]) == 2
    assert value.primary_output() is not None
    assert (
        value.primary_output().reference_id
        == "source-set-001"
    )


def test_search_specialist_accepts_empty_result() -> None:
    value = agent(EmptyExecutor()).execute(
        assignment()
    )

    assert value.status is (
        ResearchAgentResultStatus.SUCCEEDED
    )
    assert value.metrics.source_count == 0
    assert value.payload["hit_count"] == 0
    assert "returned 0 sources" in value.summary


def test_search_specialist_converts_retryable_error() -> None:
    value = agent(
        RetryableFailingExecutor()
    ).execute(assignment())

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.TOOL
    )
    assert value.failure.code == (
        "SEARCH_PROVIDER_UNAVAILABLE"
    )
    assert value.failure.retryable is True
    assert value.can_retry is True


def test_search_specialist_disables_retry_at_limit() -> None:
    value = agent(
        RetryableFailingExecutor()
    ).execute(
        assignment(
            attempt_number=2,
            maximum_attempts=2,
        )
    )

    assert value.failure is not None
    assert value.failure.retryable is False
    assert value.can_retry is False


def test_search_specialist_converts_unexpected_error() -> None:
    value = agent(
        UnexpectedFailingExecutor()
    ).execute(assignment())

    assert value.status is (
        ResearchAgentResultStatus.FAILED
    )
    assert value.failure is not None
    assert value.failure.category is (
        ResearchAgentFailureCategory.INTERNAL
    )
    assert value.failure.code == (
        "UNEXPECTED_SEARCH_ERROR"
    )
    assert value.failure.retryable is False


def test_search_specialist_rejects_wrong_role_profile() -> None:
    reader = identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )
    profile = ResearchAgentCapabilityProfile(
        profile_id="profile-reader-001",
        agent=reader,
        capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "search specialist must have "
            "search_specialist role"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        )


def test_search_specialist_requires_search_capability() -> None:
    profile = specialist_profile(
        capabilities=[
            ResearchAgentCapability.PLAN_QUERIES,
        ]
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "search specialist requires "
            "search_sources capability"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        )


def test_search_specialist_rejects_wrong_assignee() -> None:
    other = identity(
        agent_id="agent-search-002",
        role=ResearchAgentRole.SEARCH_SPECIALIST,
        name="Other Search Specialist",
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "assignment assignee must match "
            "search specialist"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(assignee=other)
        )


def test_search_specialist_rejects_wrong_required_role() -> None:
    reader = identity(
        agent_id="agent-reader-001",
        role=ResearchAgentRole.SOURCE_READER,
        name="Source Reader",
    )

    reader_profile = ResearchAgentCapabilityProfile(
        profile_id="profile-manager-reader",
        agent=manager(),
        capabilities=[
            ResearchAgentCapability.MANAGE_RESEARCH,
        ],
        can_delegate=True,
        delegatable_roles=[
            ResearchAgentRole.SOURCE_READER,
        ],
    )

    wrong_assignment = assignment(
        assigner_profile=reader_profile,
        assignee=reader,
        required_role=ResearchAgentRole.SOURCE_READER,
        required_capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ],
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "assignment assignee must match "
            "search specialist"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            wrong_assignment
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
def test_search_specialist_rejects_non_executable_status(
    status: ResearchAgentAssignmentStatus,
) -> None:
    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "assignment status is not executable"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(status=status)
        )


def test_search_specialist_rejects_missing_required_capability() -> None:
    profile = specialist_profile(
        capabilities=[
            ResearchAgentCapability.SEARCH_SOURCES,
        ]
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "search specialist lacks required capabilities: "
            "plan_queries"
        ),
    ):
        agent(
            SuccessfulExecutor(),
            profile=profile,
        ).execute(
            assignment(
                required_capabilities=[
                    ResearchAgentCapability.SEARCH_SOURCES,
                    ResearchAgentCapability.PLAN_QUERIES,
                ]
            )
        )


def test_search_assignment_must_require_search_capability() -> None:
    with pytest.raises(
        SearchSpecialistAgentError,
        match=(
            "search assignment must require "
            "search_sources capability"
        ),
    ):
        agent(SuccessfulExecutor()).execute(
            assignment(
                required_capabilities=[
                    ResearchAgentCapability.PLAN_QUERIES,
                ]
            )
        )


def test_search_specialist_rejects_blank_result_id() -> None:
    specialist_agent = SearchSpecialistAgent(
        profile=specialist_profile(),
        executor=SuccessfulExecutor(),
        result_id_factory=lambda: " ",
    )

    with pytest.raises(
        SearchSpecialistAgentError,
        match="result_id factory returned blank value",
    ):
        specialist_agent.execute(assignment())


def test_search_specialist_exposes_identity_and_profile() -> None:
    specialist_agent = agent(
        SuccessfulExecutor()
    )

    assert specialist_agent.identity.agent_id == (
        "agent-search-001"
    )
    assert specialist_agent.profile.profile_id == (
        "profile-search-001"
    )
