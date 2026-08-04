"""Deterministic specialist agent for claim construction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.research_claim_executor import (
    ResearchClaimExecutionResult,
    ResearchClaimExecutor,
    ResearchClaimExecutorError,
)
from app.research.research_claim_synthesis_agent_error import (
    ClaimAnalystAgentError,
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


class ClaimAnalystAgent:
    """Construct evidence-backed research claims."""

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
        executor: ResearchClaimExecutor,
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
            or (lambda: f"claim-set-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.CLAIM_ANALYST
        ):
            raise ClaimAnalystAgentError(
                "claim analyst must have claim_analyst role"
            )

        if not profile.has_capability(
            ResearchAgentCapability.BUILD_CLAIMS
        ):
            raise ClaimAnalystAgentError(
                "claim analyst requires build_claims capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return claim analyst identity."""

        return self._identity

    @property
    def profile(self) -> ResearchAgentCapabilityProfile:
        """Return claim analyst profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Execute one claim-construction assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(assignment)
        except ResearchClaimExecutorError as exc:
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
                code="UNEXPECTED_CLAIM_ERROR",
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
        """Validate claim assignment."""

        if (
            assignment.assignee.agent_id.strip().casefold()
            != self._identity.agent_id.strip().casefold()
        ):
            raise ClaimAnalystAgentError(
                "assignment assignee must match claim analyst"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.CLAIM_ANALYST
        ):
            raise ClaimAnalystAgentError(
                "assignment must require claim_analyst role"
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            raise ClaimAnalystAgentError(
                "assignment status is not executable"
            )

        for capability in assignment.required_capabilities:
            if not self._profile.has_capability(capability):
                raise ClaimAnalystAgentError(
                    "claim analyst lacks required capability: "
                    f"{capability.value}"
                )

        if not assignment.requires_capability(
            ResearchAgentCapability.BUILD_CLAIMS
        ):
            raise ClaimAnalystAgentError(
                "claim assignment must require "
                "build_claims capability"
            )

        if not assignment.inputs:
            raise ClaimAnalystAgentError(
                "claim assignment must include evidence inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchClaimExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build claim construction result."""

        metrics = ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
            evidence_count=sum(
                len(claim.evidence_ids)
                for claim in execution.claims
            ),
            claim_count=execution.claim_count,
        )

        if not execution.claims:
            retryable = (
                any(item.retryable for item in execution.failures)
                and assignment.attempt_number
                < assignment.maximum_attempts
            )

            return self._failure_result(
                assignment=assignment,
                code="NO_CLAIMS_CONSTRUCTED",
                message="No evidence-backed claim was produced.",
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
                code="PARTIAL_CLAIM_CONSTRUCTION",
                message=(
                    "Some evidence groups did not produce claims."
                ),
                retryable=False,
                failed_stage="claim_construction",
                details={
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
            )

        output = ResearchAgentOutputReference(
            name="research-claims",
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
                f"Constructed {execution.claim_count} claims "
                "from the assigned evidence groups."
            ),
            outputs=[output],
            payload={
                "claims": [
                    claim.model_dump(mode="json")
                    for claim in execution.claims
                ],
                "failures": [
                    failure_item.model_dump(mode="json")
                    for failure_item in execution.failures
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
        """Build failed claim-construction result."""

        failure = ResearchAgentFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            retry_reason=(
                "Claim construction may succeed "
                "on a later attempt."
                if retryable
                else None
            ),
            failed_stage="claim_construction",
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
            summary="Claim analyst failed to construct claims.",
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
            raise ClaimAnalystAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
