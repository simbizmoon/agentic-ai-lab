"""Deterministic specialist agent for report synthesis."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.research_claim_synthesis_agent_error import (
    SynthesisSpecialistAgentError,
)
from app.research.research_synthesis_executor import (
    ResearchSynthesisExecutionResult,
    ResearchSynthesisExecutor,
    ResearchSynthesisExecutorError,
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


class SynthesisSpecialistAgent:
    """Synthesize claims into a structured research report."""

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
        executor: ResearchSynthesisExecutor,
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
            or (lambda: f"report-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.SYNTHESIS_SPECIALIST
        ):
            raise SynthesisSpecialistAgentError(
                "synthesis specialist must have "
                "synthesis_specialist role"
            )

        if not profile.has_capability(
            ResearchAgentCapability.SYNTHESIZE_REPORT
        ):
            raise SynthesisSpecialistAgentError(
                "synthesis specialist requires "
                "synthesize_report capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return synthesis specialist identity."""

        return self._identity

    @property
    def profile(self) -> ResearchAgentCapabilityProfile:
        """Return synthesis specialist profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Execute one report synthesis assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(assignment)
        except ResearchSynthesisExecutorError as exc:
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
                code="UNEXPECTED_SYNTHESIS_ERROR",
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
        """Validate synthesis assignment."""

        if (
            assignment.assignee.agent_id.strip().casefold()
            != self._identity.agent_id.strip().casefold()
        ):
            raise SynthesisSpecialistAgentError(
                "assignment assignee must match "
                "synthesis specialist"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.SYNTHESIS_SPECIALIST
        ):
            raise SynthesisSpecialistAgentError(
                "assignment must require "
                "synthesis_specialist role"
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            raise SynthesisSpecialistAgentError(
                "assignment status is not executable"
            )

        for capability in assignment.required_capabilities:
            if not self._profile.has_capability(capability):
                raise SynthesisSpecialistAgentError(
                    "synthesis specialist lacks required "
                    f"capability: {capability.value}"
                )

        if not assignment.requires_capability(
            ResearchAgentCapability.SYNTHESIZE_REPORT
        ):
            raise SynthesisSpecialistAgentError(
                "synthesis assignment must require "
                "synthesize_report capability"
            )

        if not assignment.inputs:
            raise SynthesisSpecialistAgentError(
                "synthesis assignment must include claim inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchSynthesisExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build report synthesis result."""

        metrics = ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
            claim_count=(
                sum(
                    len(section.claim_ids)
                    for section in execution.report.sections
                )
                if execution.report is not None
                else 0
            ),
        )

        if execution.report is None:
            retryable = (
                any(item.retryable for item in execution.failures)
                and assignment.attempt_number
                < assignment.maximum_attempts
            )

            return self._failure_result(
                assignment=assignment,
                code="NO_REPORT_SYNTHESIZED",
                message="No research report was produced.",
                retryable=retryable,
                details={
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
                category=ResearchAgentFailureCategory.VALIDATION,
                metrics=metrics,
            )

        partial = not execution.is_complete
        failure = None

        if partial:
            failure = ResearchAgentFailure(
                category=ResearchAgentFailureCategory.VALIDATION,
                code="PARTIAL_REPORT_SYNTHESIS",
                message=(
                    "Some requested report sections "
                    "were not synthesized."
                ),
                retryable=False,
                failed_stage="report_synthesis",
                details={
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
            )

        output = ResearchAgentOutputReference(
            name="research-report",
            output_type=assignment.expected_output_type,
            reference_id=self._new_identifier(
                self._output_reference_id_factory,
                field_name="output_reference_id",
            ),
            primary=True,
        )

        return ResearchAgentTaskResult(
            result_id=self._new_identifier(
                self._result_id_factory,
                field_name="result_id",
            ),
            assignment=assignment,
            agent=self._identity,
            status=(
                ResearchAgentResultStatus.PARTIAL
                if partial
                else ResearchAgentResultStatus.SUCCEEDED
            ),
            summary=(
                "Synthesized a research report with "
                f"{execution.completed_section_count} sections."
            ),
            outputs=[output],
            payload={
                "report": execution.report.model_dump(
                    mode="json"
                ),
                "failures": [
                    item.model_dump(mode="json")
                    for item in execution.failures
                ],
            },
            metrics=metrics,
            failure=failure,
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
        """Build failed synthesis result."""

        failure = ResearchAgentFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            retry_reason=(
                "Report synthesis may succeed "
                "on a later attempt."
                if retryable
                else None
            ),
            failed_stage="report_synthesis",
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
                "Synthesis specialist failed to produce "
                "a research report."
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
            raise SynthesisSpecialistAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
