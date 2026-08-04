"""Deterministic specialist agent for source-reading assignments."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.research_source_reader_executor import (
    ResearchSourceReaderExecutionResult,
    ResearchSourceReaderExecutor,
    ResearchSourceReaderExecutorError,
)
from app.research.source_reader_specialist_agent_error import (
    SourceReaderSpecialistAgentError,
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


class SourceReaderSpecialistAgent:
    """Execute source-reading work assigned to one specialist."""

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
        executor: ResearchSourceReaderExecutor,
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
            or (lambda: f"result-{uuid4()}")
        )
        self._output_reference_id_factory = (
            output_reference_id_factory
            or (lambda: f"document-set-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.SOURCE_READER
        ):
            raise SourceReaderSpecialistAgentError(
                "source reader must have source_reader role"
            )

        if not self._profile.has_capability(
            ResearchAgentCapability.READ_SOURCES
        ):
            raise SourceReaderSpecialistAgentError(
                "source reader requires read_sources capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return the source reader identity."""

        return self._identity

    @property
    def profile(
        self,
    ) -> ResearchAgentCapabilityProfile:
        """Return the source reader capability profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Validate and execute one source-reading assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(
                assignment
            )
        except ResearchSourceReaderExecutorError as exc:
            return self._failure_result(
                assignment=assignment,
                category=ResearchAgentFailureCategory.SOURCE,
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
                code="UNEXPECTED_SOURCE_READER_ERROR",
                message=str(exc) or exc.__class__.__name__,
                retryable=False,
                details={
                    "exception_type": (
                        exc.__class__.__name__
                    ),
                },
            )

        return self._execution_result(
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
            raise SourceReaderSpecialistAgentError(
                "assignment assignee must match source reader"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.SOURCE_READER
        ):
            raise SourceReaderSpecialistAgentError(
                "assignment must require source_reader role"
            )

        if (
            assignment.status
            not in self._EXECUTABLE_STATUSES
        ):
            raise SourceReaderSpecialistAgentError(
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
            raise SourceReaderSpecialistAgentError(
                "source reader lacks required "
                f"capabilities: {missing}"
            )

        if not assignment.requires_capability(
            ResearchAgentCapability.READ_SOURCES
        ):
            raise SourceReaderSpecialistAgentError(
                "source-reading assignment must require "
                "read_sources capability"
            )

        if not assignment.inputs:
            raise SourceReaderSpecialistAgentError(
                "source-reading assignment must include "
                "source inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchSourceReaderExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build success, partial, or failed result."""

        if not execution.documents:
            retryable = (
                any(
                    failure.retryable
                    for failure in execution.failures
                )
                and assignment.attempt_number
                < assignment.maximum_attempts
            )

            return self._failure_result(
                assignment=assignment,
                category=ResearchAgentFailureCategory.SOURCE,
                code="NO_SOURCE_DOCUMENTS_READ",
                message=(
                    "The source reader did not produce "
                    "any readable documents."
                ),
                retryable=retryable,
                details={
                    "requested_source_count": (
                        execution.requested_source_count
                    ),
                    "failed_source_count": (
                        execution.failed_source_count
                    ),
                    "failures": [
                        failure.model_dump(mode="json")
                        for failure in execution.failures
                    ],
                },
                metrics=self._metrics(execution),
            )

        result_id = self._new_identifier(
            self._result_id_factory,
            field_name="result_id",
        )
        output_reference_id = self._new_identifier(
            self._output_reference_id_factory,
            field_name="output_reference_id",
        )

        partial = not execution.is_complete

        failure = None

        if partial:
            failure = ResearchAgentFailure(
                category=ResearchAgentFailureCategory.SOURCE,
                code="PARTIAL_SOURCE_READ",
                message=(
                    "Some requested sources could not be read."
                ),
                retryable=False,
                failed_stage="source_reading",
                details={
                    "failed_source_count": (
                        execution.failed_source_count
                    ),
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
            )

        output = ResearchAgentOutputReference(
            name="source-documents",
            output_type=assignment.expected_output_type,
            reference_id=output_reference_id,
            primary=True,
            metadata={
                "agent_role": self._identity.role.value,
                "document_count": str(
                    execution.successful_source_count
                ),
            },
        )

        return ResearchAgentTaskResult(
            result_id=result_id,
            assignment=assignment,
            agent=self._identity,
            status=(
                ResearchAgentResultStatus.PARTIAL
                if partial
                else ResearchAgentResultStatus.SUCCEEDED
            ),
            summary=(
                "Source reader processed "
                f"{execution.requested_source_count} sources, "
                f"produced {execution.successful_source_count} "
                "documents, and recorded "
                f"{execution.failed_source_count} failures."
            ),
            outputs=[output],
            payload={
                "requested_source_count": (
                    execution.requested_source_count
                ),
                "document_count": (
                    execution.successful_source_count
                ),
                "failed_source_count": (
                    execution.failed_source_count
                ),
                "documents": [
                    document.model_dump(mode="json")
                    for document in execution.documents
                ],
                "failures": [
                    item.model_dump(mode="json")
                    for item in execution.failures
                ],
            },
            metrics=self._metrics(execution),
            failure=failure,
            completed_at=self._now(),
            metadata={
                "executor": (
                    self._executor.__class__.__name__
                ),
                **execution.metadata,
            },
        )

    @staticmethod
    def _metrics(
        execution: ResearchSourceReaderExecutionResult,
    ) -> ResearchAgentExecutionMetrics:
        """Convert executor metrics to agent result metrics."""

        return ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
            source_count=execution.requested_source_count,
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
        metrics: ResearchAgentExecutionMetrics | None = None,
    ) -> ResearchAgentTaskResult:
        """Build one structured failed result."""

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
                "The source-reading operation may succeed "
                "on a later assignment attempt."
                if retryable
                else None
            ),
            failed_stage="source_reading",
            details=details,
        )

        return ResearchAgentTaskResult(
            result_id=result_id,
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.FAILED,
            summary=(
                "Source reader failed to produce "
                "a readable source document."
            ),
            outputs=[],
            payload={},
            metrics=(
                metrics
                or ResearchAgentExecutionMetrics()
            ),
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
            raise SourceReaderSpecialistAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
