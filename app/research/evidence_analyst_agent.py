"""Deterministic specialist agent for evidence extraction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.evidence_analyst_agent_error import (
    EvidenceAnalystAgentError,
)
from app.research.research_evidence_executor import (
    ResearchEvidenceExecutionResult,
    ResearchEvidenceExecutor,
    ResearchEvidenceExecutorError,
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


class EvidenceAnalystAgent:
    """Extract structured evidence from assigned documents."""

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
        executor: ResearchEvidenceExecutor,
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
            or (lambda: f"evidence-set-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.EVIDENCE_ANALYST
        ):
            raise EvidenceAnalystAgentError(
                "evidence analyst must have "
                "evidence_analyst role"
            )

        if not self._profile.has_capability(
            ResearchAgentCapability.EXTRACT_EVIDENCE
        ):
            raise EvidenceAnalystAgentError(
                "evidence analyst requires "
                "extract_evidence capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return the evidence analyst identity."""

        return self._identity

    @property
    def profile(
        self,
    ) -> ResearchAgentCapabilityProfile:
        """Return the evidence analyst profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Validate and execute one evidence assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(
                assignment
            )
        except ResearchEvidenceExecutorError as exc:
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
                code="UNEXPECTED_EVIDENCE_ERROR",
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
            raise EvidenceAnalystAgentError(
                "assignment assignee must match "
                "evidence analyst"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.EVIDENCE_ANALYST
        ):
            raise EvidenceAnalystAgentError(
                "assignment must require "
                "evidence_analyst role"
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            raise EvidenceAnalystAgentError(
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
                for capability in missing_capabilities
            )
            raise EvidenceAnalystAgentError(
                "evidence analyst lacks required "
                f"capabilities: {missing}"
            )

        if not assignment.requires_capability(
            ResearchAgentCapability.EXTRACT_EVIDENCE
        ):
            raise EvidenceAnalystAgentError(
                "evidence assignment must require "
                "extract_evidence capability"
            )

        if not assignment.inputs:
            raise EvidenceAnalystAgentError(
                "evidence assignment must include "
                "document inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchEvidenceExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build success, partial, or failed result."""

        if not execution.evidence:
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
                category=(
                    ResearchAgentFailureCategory.SOURCE
                ),
                code="NO_EVIDENCE_EXTRACTED",
                message=(
                    "The evidence analyst did not extract "
                    "any usable evidence."
                ),
                retryable=retryable,
                details={
                    "requested_document_count": (
                        execution.requested_document_count
                    ),
                    "failed_document_count": (
                        execution.failed_document_count
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
                code="PARTIAL_EVIDENCE_EXTRACTION",
                message=(
                    "Evidence could not be extracted from "
                    "every requested document."
                ),
                retryable=False,
                failed_stage="evidence_extraction",
                details={
                    "failed_document_count": (
                        execution.failed_document_count
                    ),
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
            )

        output = ResearchAgentOutputReference(
            name="research-evidence",
            output_type=assignment.expected_output_type,
            reference_id=output_reference_id,
            primary=True,
            metadata={
                "agent_role": self._identity.role.value,
                "evidence_count": str(
                    execution.evidence_count
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
                "Evidence analyst processed "
                f"{execution.requested_document_count} "
                "documents and extracted "
                f"{execution.evidence_count} evidence items."
            ),
            outputs=[output],
            payload={
                "requested_document_count": (
                    execution.requested_document_count
                ),
                "successful_document_count": (
                    execution.successful_document_count
                ),
                "failed_document_count": (
                    execution.failed_document_count
                ),
                "evidence_count": execution.evidence_count,
                "evidence": [
                    item.model_dump(mode="json")
                    for item in execution.evidence
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
        execution: ResearchEvidenceExecutionResult,
    ) -> ResearchAgentExecutionMetrics:
        """Convert executor metrics to result metrics."""

        return ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
            source_count=execution.requested_document_count,
            evidence_count=execution.evidence_count,
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
                "Evidence extraction may succeed "
                "on a later assignment attempt."
                if retryable
                else None
            ),
            failed_stage="evidence_extraction",
            details=details,
        )

        return ResearchAgentTaskResult(
            result_id=result_id,
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.FAILED,
            summary=(
                "Evidence analyst failed to produce "
                "usable evidence."
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
            raise EvidenceAnalystAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
