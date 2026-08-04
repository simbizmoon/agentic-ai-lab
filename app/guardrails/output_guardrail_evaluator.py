"""Deterministic guardrails for research-agent outputs."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar
from uuid import uuid4

from app.guardrails.guardrail_policy import (
    GuardrailAction,
    GuardrailScope,
    GuardrailSeverity,
)
from app.guardrails.guardrail_result import (
    GuardrailDecision,
    GuardrailEvaluationResult,
    GuardrailViolation,
)
from app.guardrails.output_guardrail_evaluator_error import (
    OutputGuardrailEvaluatorError,
)
from app.guardrails.output_guardrail_snapshot import (
    OutputGuardrailSnapshot,
)
from app.schemas.research_agent_result import (
    ResearchAgentResultStatus,
)


class OutputGuardrailEvaluator:
    """Validate a research-agent result before propagation."""

    _POLICY_IDS: ClassVar[list[str]] = [
        "output-assignment-context",
        "output-agent-identity",
        "output-request-context",
        "output-workspace-context",
        "output-required-artifacts",
        "output-primary-artifact",
        "output-primary-uniqueness",
        "output-expected-type",
        "output-reference-uniqueness",
    ]

    def __init__(
        self,
        *,
        evaluation_id_factory: Callable[[], str] | None = None,
        violation_id_factory: (
            Callable[[int], str] | None
        ) = None,
    ) -> None:
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (lambda: f"output-guardrail-{uuid4()}")
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"output-guardrail-violation-"
                    f"{index}-{uuid4()}"
                )
            )
        )

    def evaluate(
        self,
        snapshot: OutputGuardrailSnapshot,
    ) -> GuardrailEvaluationResult:
        """Evaluate output guardrails for one agent result."""

        result = snapshot.result
        expected_assignment = snapshot.expected_assignment
        assignment = result.assignment
        violations: list[GuardrailViolation] = []

        if (
            assignment.assignment_id.strip().casefold()
            != expected_assignment.assignment_id
            .strip()
            .casefold()
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-assignment-context",
                    rule_id="result-assignment-must-match",
                    code="RESULT_ASSIGNMENT_MISMATCH",
                    message=(
                        "Result assignment does not match "
                        "the expected assignment."
                    ),
                    field_path="result.assignment.assignment_id",
                    remediation=(
                        "Return a result for the expected "
                        "assignment."
                    ),
                )
            )

        if (
            result.agent.agent_id.strip().casefold()
            != expected_assignment.assignee.agent_id
            .strip()
            .casefold()
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-agent-identity",
                    rule_id="result-agent-must-match",
                    code="RESULT_AGENT_MISMATCH",
                    message=(
                        "Result agent does not match "
                        "the assignment assignee."
                    ),
                    field_path="result.agent.agent_id",
                    remediation=(
                        "Return the result from the assigned "
                        "agent."
                    ),
                )
            )

        if assignment.request_id != snapshot.expected_request_id:
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-request-context",
                    rule_id="result-request-must-match",
                    code="RESULT_REQUEST_CONTEXT_MISMATCH",
                    message=(
                        "Result request context does not match "
                        "the expected request."
                    ),
                    field_path="result.assignment.request_id",
                    remediation=(
                        "Use a result from the current "
                        "research request."
                    ),
                )
            )

        if (
            assignment.workspace_id
            != snapshot.expected_workspace_id
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-workspace-context",
                    rule_id="result-workspace-must-match",
                    code="RESULT_WORKSPACE_CONTEXT_MISMATCH",
                    message=(
                        "Result workspace context does not match "
                        "the expected workspace."
                    ),
                    field_path="result.assignment.workspace_id",
                    remediation=(
                        "Use a result from the current "
                        "research workspace."
                    ),
                )
            )

        output_reference_ids = [
            output.reference_id.strip().casefold()
            for output in result.outputs
        ]

        if (
            len(set(output_reference_ids))
            != len(output_reference_ids)
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-reference-uniqueness",
                    rule_id="output-reference-ids-unique",
                    code="DUPLICATE_OUTPUT_REFERENCE_ID",
                    message=(
                        "Result contains duplicate output "
                        "reference IDs."
                    ),
                    field_path="result.outputs",
                    remediation=(
                        "Use a unique reference ID for each "
                        "output artifact."
                    ),
                )
            )

        if result.status is ResearchAgentResultStatus.SUCCEEDED:
            self._evaluate_success_result(
                snapshot=snapshot,
                violations=violations,
            )

        blocking_violations = [
            violation
            for violation in violations
            if violation.blocking
        ]

        if blocking_violations:
            decision = GuardrailDecision.BLOCKED
        elif violations:
            decision = GuardrailDecision.WARNED
        else:
            decision = GuardrailDecision.ALLOWED

        return GuardrailEvaluationResult(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            subject_id=result.result_id,
            scope=GuardrailScope.OUTPUT,
            decision=decision,
            violations=violations,
            evaluated_policy_ids=self._POLICY_IDS,
            summary=self._summary(
                decision=decision,
                violation_count=len(violations),
            ),
            metadata={
                "assignment_id": assignment.assignment_id,
                "agent_id": result.agent.agent_id,
                "result_status": result.status.value,
            },
        )

    def _evaluate_success_result(
        self,
        *,
        snapshot: OutputGuardrailSnapshot,
        violations: list[GuardrailViolation],
    ) -> None:
        """Evaluate requirements specific to successful results."""

        result = snapshot.result
        expected_assignment = snapshot.expected_assignment

        if not result.outputs:
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-required-artifacts",
                    rule_id="successful-result-requires-output",
                    code="SUCCESS_RESULT_MISSING_OUTPUTS",
                    message=(
                        "Successful result does not contain "
                        "an output artifact."
                    ),
                    field_path="result.outputs",
                    remediation=(
                        "Attach at least one output artifact."
                    ),
                )
            )
            return

        primary_outputs = [
            output
            for output in result.outputs
            if output.primary
        ]

        if (
            snapshot.require_primary_output
            and not primary_outputs
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-primary-artifact",
                    rule_id="successful-result-requires-primary",
                    code="PRIMARY_OUTPUT_MISSING",
                    message=(
                        "Successful result does not contain "
                        "a primary output."
                    ),
                    field_path="result.outputs",
                    remediation=(
                        "Mark the principal output artifact "
                        "as primary."
                    ),
                )
            )

        if (
            snapshot.require_exactly_one_primary_output
            and len(primary_outputs) > 1
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="output-primary-uniqueness",
                    rule_id="primary-output-must-be-unique",
                    code="MULTIPLE_PRIMARY_OUTPUTS",
                    message=(
                        "Successful result contains more than "
                        "one primary output."
                    ),
                    field_path="result.outputs",
                    remediation=(
                        "Select exactly one primary output."
                    ),
                )
            )

        if (
            snapshot.enforce_expected_output_type
            and primary_outputs
        ):
            expected_type = (
                expected_assignment.expected_output_type
                .strip()
                .casefold()
            )

            for primary_output in primary_outputs:
                if (
                    primary_output.output_type
                    .strip()
                    .casefold()
                    == expected_type
                ):
                    continue

                violations.append(
                    self._blocking_violation(
                        index=len(violations) + 1,
                        policy_id="output-expected-type",
                        rule_id=(
                            "primary-output-type-must-match"
                        ),
                        code="PRIMARY_OUTPUT_TYPE_MISMATCH",
                        message=(
                            "Primary output type does not match "
                            "the assignment expected output type."
                        ),
                        field_path=(
                            "result.outputs.output_type"
                        ),
                        remediation=(
                            "Return the output type specified "
                            "by the assignment."
                        ),
                        details={
                            "expected_output_type": (
                                expected_assignment
                                .expected_output_type
                            ),
                            "actual_output_type": (
                                primary_output.output_type
                            ),
                        },
                    )
                )

    def _blocking_violation(
        self,
        *,
        index: int,
        policy_id: str,
        rule_id: str,
        code: str,
        message: str,
        field_path: str,
        remediation: str,
        details: dict | None = None,
    ) -> GuardrailViolation:
        """Build one blocking output violation."""

        return GuardrailViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            policy_id=policy_id,
            rule_id=rule_id,
            code=code,
            scope=GuardrailScope.OUTPUT,
            severity=GuardrailSeverity.ERROR,
            action=GuardrailAction.BLOCK,
            message=message,
            blocking=True,
            retryable=False,
            field_path=field_path,
            remediation=remediation,
            details=details or {},
        )

    @staticmethod
    def _summary(
        *,
        decision: GuardrailDecision,
        violation_count: int,
    ) -> str:
        """Return deterministic output guardrail summary."""

        return (
            "Output guardrail evaluation completed with "
            f"decision {decision.value} and "
            f"{violation_count} violations."
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
            raise OutputGuardrailEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value

    @staticmethod
    def _new_indexed_identifier(
        factory: Callable[[int], str],
        *,
        index: int,
        field_name: str,
    ) -> str:
        """Generate one nonblank indexed identifier."""

        value = factory(index)

        if not value.strip():
            raise OutputGuardrailEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
