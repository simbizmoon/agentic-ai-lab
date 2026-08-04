"""Deterministic specialist agent for source-search assignments."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.research_search_executor import (
    ResearchSearchExecutionResult,
    ResearchSearchExecutor,
    ResearchSearchExecutorError,
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
    ResearchAgentExecutionMetrics,
    ResearchAgentFailure,
    ResearchAgentFailureCategory,
    ResearchAgentOutputReference,
    ResearchAgentResultStatus,
    ResearchAgentTaskResult,
)


class SearchSpecialistAgent:
    """Execute source-search work assigned to one specialist."""

    _EXECUTABLE_STATUSES: ClassVar[
        set[ResearchAgentAssignmentStatus]
    ] = {
        ResearchAgentAssignmentStatus.OFFERED,
        ResearchAgentAssignmentStatus.ACCEPTED,
        ResearchAgentAssignmentStatus.IN_PROGRESS,
    }

    def __init__(
        self,
        *,
        profile: ResearchAgentCapabilityProfile,
        executor: ResearchSearchExecutor,
        now: Callable[[], datetime] | None = None,
        result_id_factory: Callable[[], str] | None = None,
        output_reference_id_factory: (
            Callable[[], str] | None
        ) = None,
    ) -> None:
        self._profile = profile
        self._identity = profile.agent
        self._executor = executor
        self._now = now or (
            lambda: datetime.now(UTC)
        )
        self._result_id_factory = (
            result_id_factory
            or (
                lambda: f"result-{uuid4()}"
            )
        )
        self._output_reference_id_factory = (
            output_reference_id_factory
            or (
                lambda: f"source-set-{uuid4()}"
            )
        )

        if (
            self._identity.role
            is not ResearchAgentRole.SEARCH_SPECIALIST
        ):
            raise SearchSpecialistAgentError(
                "search specialist must have "
                "search_specialist role"
            )

        if not self._profile.has_capability(
            ResearchAgentCapability.SEARCH_SOURCES
        ):
            raise SearchSpecialistAgentError(
                "search specialist requires "
                "search_sources capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return the specialist identity."""

        return self._identity

    @property
    def profile(
        self,
    ) -> ResearchAgentCapabilityProfile:
        """Return the specialist capability profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Validate and execute one source-search assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(
                assignment
            )
        except ResearchSearchExecutorError as exc:
            return self._failure_result(
                assignment=assignment,
                category=ResearchAgentFailureCategory.TOOL,
                code=exc.code,
                message=str(exc),
                retryable=(
                    exc.retryable
                    and assignment.attempt_number
                    < assignment.maximum_attempts
                ),
                details=exc.details,
            )
        except RuntimeError as exc:
            return self._failure_result(
                assignment=assignment,
                category=(
                    ResearchAgentFailureCategory.INTERNAL
                ),
                code="UNEXPECTED_SEARCH_ERROR",
                message=str(exc) or exc.__class__.__name__,
                retryable=False,
                details={
                    "exception_type": (
                        exc.__class__.__name__
                    ),
                },
            )

        return self._success_result(
            assignment=assignment,
            execution=execution,
        )

    def _validate_assignment(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> None:
        """Validate assignment ownership and requirements."""

        if (
            assignment.assignee.agent_id
            .strip()
            .casefold()
            != self._identity.agent_id
            .strip()
            .casefold()
        ):
            raise SearchSpecialistAgentError(
                "assignment assignee must match "
                "search specialist"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.SEARCH_SPECIALIST
        ):
            raise SearchSpecialistAgentError(
                "assignment must require "
                "search_specialist role"
            )

        if (
            assignment.status
            not in self._EXECUTABLE_STATUSES
        ):
            raise SearchSpecialistAgentError(
                "assignment status is not executable"
            )

        missing_capabilities = [
            capability
            for capability
            in assignment.required_capabilities
            if not self._profile.has_capability(
                capability
            )
        ]

        if missing_capabilities:
            missing = ", ".join(
                capability.value
                for capability
                in missing_capabilities
            )
            raise SearchSpecialistAgentError(
                "search specialist lacks required "
                f"capabilities: {missing}"
            )

        if not assignment.requires_capability(
            ResearchAgentCapability.SEARCH_SOURCES
        ):
            raise SearchSpecialistAgentError(
                "search assignment must require "
                "search_sources capability"
            )

    def _success_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchSearchExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build one successful structured task result."""

        result_id = self._new_identifier(
            self._result_id_factory,
            field_name="result_id",
        )
        output_reference_id = self._new_identifier(
            self._output_reference_id_factory,
            field_name="output_reference_id",
        )

        output = ResearchAgentOutputReference(
            name="source-search-results",
            output_type=assignment.expected_output_type,
            reference_id=output_reference_id,
            primary=True,
            metadata={
                "agent_role": self._identity.role.value,
                "result_count": str(len(execution.hits)),
            },
        )

        return ResearchAgentTaskResult(
            result_id=result_id,
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.SUCCEEDED,
            summary=(
                "Search specialist completed "
                f"{execution.query_count} queries and "
                f"returned {len(execution.hits)} sources."
            ),
            outputs=[output],
            payload={
                "query_count": execution.query_count,
                "hit_count": len(execution.hits),
                "hits": [
                    hit.model_dump(mode="json")
                    for hit in execution.hits
                ],
            },
            metrics=ResearchAgentExecutionMetrics(
                duration_ms=execution.duration_ms,
                tool_call_count=(
                    execution.tool_call_count
                ),
                input_token_count=(
                    execution.input_token_count
                ),
                output_token_count=(
                    execution.output_token_count
                ),
                source_count=len(execution.hits),
            ),
            completed_at=self._now(),
            metadata={
                "executor": (
                    self._executor.__class__.__name__
                ),
                **execution.metadata,
            },
        )

    def _failure_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        category: ResearchAgentFailureCategory,
        code: str,
        message: str,
        retryable: bool,
        details: dict,
    ) -> ResearchAgentTaskResult:
        """Build one structured failed task result."""

        result_id = self._new_identifier(
            self._result_id_factory,
            field_name="result_id",
        )

        failure = ResearchAgentFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            retry_reason=(
                "The search operation may succeed "
                "on a later assignment attempt."
                if retryable
                else None
            ),
            failed_stage="source_search",
            details=details,
        )

        return ResearchAgentTaskResult(
            result_id=result_id,
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.FAILED,
            summary=(
                "Search specialist failed to complete "
                "the assigned source search."
            ),
            outputs=[],
            payload={},
            metrics=ResearchAgentExecutionMetrics(),
            failure=failure,
            completed_at=self._now(),
            metadata={
                "executor": (
                    self._executor.__class__.__name__
                ),
            },
        )

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate and validate one identifier."""

        value = factory()

        if not value.strip():
            raise SearchSpecialistAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
