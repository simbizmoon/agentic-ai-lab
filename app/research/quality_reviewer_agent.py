"""Deterministic specialist agent for report-quality review."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.quality_reviewer_agent_error import (
    QualityReviewerAgentError,
)
from app.research.research_quality_review_executor import (
    ResearchQualityReviewExecutionResult,
    ResearchQualityReviewExecutor,
    ResearchQualityReviewExecutorError,
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


class QualityReviewerAgent:
    """Independently evaluate a synthesized research report."""

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
        executor: ResearchQualityReviewExecutor,
        now: Callable[[], datetime] | None = None,
        result_id_factory: Callable[[], str] | None = None,
        output_reference_id_factory: (
            Callable[[], str] | None
        ) = None,
    ) -> None:
        self._profile = profile
        self._identity = profile.agent
        self._executor = executor
        self._now = now or (lambda: datetime.now(UTC))
        self._result_id_factory = (
            result_id_factory
            or (lambda: f"result-{uuid4()}")
        )
        self._output_reference_id_factory = (
            output_reference_id_factory
            or (lambda: f"quality-review-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.QUALITY_REVIEWER
        ):
            raise QualityReviewerAgentError(
                "quality reviewer must have "
                "quality_reviewer role"
            )

        if not profile.has_capability(
            ResearchAgentCapability.EVALUATE_REPORT
        ):
            raise QualityReviewerAgentError(
                "quality reviewer requires "
                "evaluate_report capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return quality reviewer identity."""

        return self._identity

    @property
    def profile(self) -> ResearchAgentCapabilityProfile:
        """Return quality reviewer profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Execute one independent quality review."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(assignment)
        except ResearchQualityReviewExecutorError as exc:
            return self._failure_result(
                assignment=assignment,
                code=exc.code,
                message=str(exc),
                retryable=(
                    exc.retryable
                    and assignment.attempt_number
                    < assignment.maximum_attempts
                ),
                details=exc.details,
                category=ResearchAgentFailureCategory.TOOL,
            )
        except RuntimeError as exc:
            return self._failure_result(
                assignment=assignment,
                code="UNEXPECTED_QUALITY_REVIEW_ERROR",
                message=str(exc) or exc.__class__.__name__,
                retryable=False,
                details={
                    "exception_type": exc.__class__.__name__,
                },
                category=ResearchAgentFailureCategory.INTERNAL,
            )

        return self._execution_result(
            assignment=assignment,
            execution=execution,
        )

    def _validate_assignment(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> None:
        """Validate quality review assignment."""

        if (
            assignment.assignee.agent_id.strip().casefold()
            != self._identity.agent_id.strip().casefold()
        ):
            raise QualityReviewerAgentError(
                "assignment assignee must match "
                "quality reviewer"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.QUALITY_REVIEWER
        ):
            raise QualityReviewerAgentError(
                "assignment must require "
                "quality_reviewer role"
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            raise QualityReviewerAgentError(
                "assignment status is not executable"
            )

        for capability in assignment.required_capabilities:
            if not self._profile.has_capability(capability):
                raise QualityReviewerAgentError(
                    "quality reviewer lacks required "
                    f"capability: {capability.value}"
                )

        if not assignment.requires_capability(
            ResearchAgentCapability.EVALUATE_REPORT
        ):
            raise QualityReviewerAgentError(
                "quality review assignment must require "
                "evaluate_report capability"
            )

        if not assignment.inputs:
            raise QualityReviewerAgentError(
                "quality review assignment must include "
                "report inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchQualityReviewExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build a successful quality review result."""

        metrics = ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
        )

        if execution.review is None:
            return self._failure_result(
                assignment=assignment,
                code="NO_QUALITY_REVIEW_PRODUCED",
                message="No quality review was produced.",
                retryable=False,
                details={},
                category=ResearchAgentFailureCategory.VALIDATION,
                metrics=metrics,
            )

        review = execution.review

        output = ResearchAgentOutputReference(
            name="research-quality-review",
            output_type=assignment.expected_output_type,
            reference_id=self._new_identifier(
                self._output_reference_id_factory,
                field_name="output_reference_id",
            ),
            primary=True,
            metadata={
                "decision": review.decision.value,
                "overall_score": (
                    f"{review.scores.overall_score:.6f}"
                ),
            },
        )

        return ResearchAgentTaskResult(
            result_id=self._new_identifier(
                self._result_id_factory,
                field_name="result_id",
            ),
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.SUCCEEDED,
            summary=(
                "Quality reviewer completed the report "
                f"evaluation with decision "
                f"{review.decision.value}."
            ),
            outputs=[output],
            payload={
                "review": review.model_dump(mode="json"),
                "decision": review.decision.value,
                "approved": review.approved,
                "requires_revision": (
                    review.requires_revision
                ),
                "overall_score": (
                    review.scores.overall_score
                ),
                "revision_count": len(
                    review.revision_requests
                ),
            },
            metrics=metrics,
            completed_at=self._now(),
            metadata={
                "executor": self._executor.__class__.__name__,
                **execution.metadata,
            },
        )

    def _failure_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        code: str,
        message: str,
        retryable: bool,
        details: dict,
        category: ResearchAgentFailureCategory,
        metrics: ResearchAgentExecutionMetrics | None = None,
    ) -> ResearchAgentTaskResult:
        """Build a failed quality review result."""

        failure = ResearchAgentFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            retry_reason=(
                "Quality review may succeed on a later attempt."
                if retryable
                else None
            ),
            failed_stage="quality_review",
            details=details,
        )

        return ResearchAgentTaskResult(
            result_id=self._new_identifier(
                self._result_id_factory,
                field_name="result_id",
            ),
            assignment=assignment,
            agent=self._identity,
            status=ResearchAgentResultStatus.FAILED,
            summary=(
                "Quality reviewer failed to evaluate "
                "the research report."
            ),
            outputs=[],
            metrics=metrics or ResearchAgentExecutionMetrics(),
            failure=failure,
            completed_at=self._now(),
        )

    @staticmethod
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate one nonblank identifier."""

        value = factory()

        if not value.strip():
            raise QualityReviewerAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
