"""Deterministic specialist agent for citation verification."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from app.research.research_citation_verifier_executor import (
    ResearchCitationVerifierExecutionResult,
    ResearchCitationVerifierExecutor,
    ResearchCitationVerifierExecutorError,
)
from app.research.research_review_agent_error import (
    CitationVerifierAgentError,
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


class CitationVerifierAgent:
    """Verify claim, evidence, source, and citation links."""

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
        executor: ResearchCitationVerifierExecutor,
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
            or (lambda: f"citation-review-set-{uuid4()}")
        )

        if (
            self._identity.role
            is not ResearchAgentRole.CITATION_VERIFIER
        ):
            raise CitationVerifierAgentError(
                "citation verifier must have "
                "citation_verifier role"
            )

        if not profile.has_capability(
            ResearchAgentCapability.VERIFY_CITATIONS
        ):
            raise CitationVerifierAgentError(
                "citation verifier requires "
                "verify_citations capability"
            )

    @property
    def identity(self) -> ResearchAgentIdentity:
        """Return citation verifier identity."""

        return self._identity

    @property
    def profile(self) -> ResearchAgentCapabilityProfile:
        """Return citation verifier profile."""

        return self._profile

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchAgentTaskResult:
        """Execute one citation verification assignment."""

        self._validate_assignment(assignment)

        try:
            execution = self._executor.execute(assignment)
        except ResearchCitationVerifierExecutorError as exc:
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
                code="UNEXPECTED_CITATION_VERIFIER_ERROR",
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
        """Validate citation verification assignment."""

        if (
            assignment.assignee.agent_id.strip().casefold()
            != self._identity.agent_id.strip().casefold()
        ):
            raise CitationVerifierAgentError(
                "assignment assignee must match "
                "citation verifier"
            )

        if (
            assignment.required_role
            is not ResearchAgentRole.CITATION_VERIFIER
        ):
            raise CitationVerifierAgentError(
                "assignment must require "
                "citation_verifier role"
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            raise CitationVerifierAgentError(
                "assignment status is not executable"
            )

        for capability in assignment.required_capabilities:
            if not self._profile.has_capability(capability):
                raise CitationVerifierAgentError(
                    "citation verifier lacks required capability: "
                    f"{capability.value}"
                )

        if not assignment.requires_capability(
            ResearchAgentCapability.VERIFY_CITATIONS
        ):
            raise CitationVerifierAgentError(
                "citation verification assignment must require "
                "verify_citations capability"
            )

        if not assignment.inputs:
            raise CitationVerifierAgentError(
                "citation verification assignment must include "
                "claim and citation inputs"
            )

    def _execution_result(
        self,
        *,
        assignment: ResearchAgentTaskAssignment,
        execution: ResearchCitationVerifierExecutionResult,
    ) -> ResearchAgentTaskResult:
        """Build citation verification task result."""

        metrics = ResearchAgentExecutionMetrics(
            duration_ms=execution.duration_ms,
            tool_call_count=execution.tool_call_count,
            input_token_count=execution.input_token_count,
            output_token_count=execution.output_token_count,
            claim_count=execution.requested_citation_count,
        )

        if not execution.verifications:
            retryable = (
                any(item.retryable for item in execution.failures)
                and assignment.attempt_number
                < assignment.maximum_attempts
            )

            return self._failure_result(
                assignment=assignment,
                code="NO_CITATIONS_VERIFIED",
                message="No citation verification was produced.",
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
                code="PARTIAL_CITATION_VERIFICATION",
                message="Some citations could not be verified.",
                retryable=False,
                failed_stage="citation_verification",
                details={
                    "failures": [
                        item.model_dump(mode="json")
                        for item in execution.failures
                    ],
                },
            )

        output = ResearchAgentOutputReference(
            name="citation-verifications",
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
                f"Verified {execution.verified_citation_count} "
                f"of {execution.requested_citation_count} citations."
            ),
            outputs=[output],
            payload={
                "verifications": [
                    item.model_dump(mode="json")
                    for item in execution.verifications
                ],
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
        """Build failed citation verification result."""

        failure = ResearchAgentFailure(
            category=category,
            code=code,
            message=message,
            retryable=retryable,
            retry_reason=(
                "Citation verification may succeed "
                "on a later attempt."
                if retryable
                else None
            ),
            failed_stage="citation_verification",
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
                "Citation verifier failed to verify citations."
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
            raise CitationVerifierAgentError(
                f"{field_name} factory returned blank value"
            )

        return value
