"""Deterministic guardrails for research assignment inputs."""

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
from app.guardrails.input_guardrail_evaluator_error import (
    InputGuardrailEvaluatorError,
)
from app.guardrails.input_guardrail_snapshot import (
    InputGuardrailSnapshot,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentAssignmentStatus,
)


class InputGuardrailEvaluator:
    """Validate a research assignment before agent execution."""

    _EXECUTABLE_STATUSES: ClassVar[
        set[ResearchAgentAssignmentStatus]
    ] = {
        ResearchAgentAssignmentStatus.OFFERED,
        ResearchAgentAssignmentStatus.ACCEPTED,
        ResearchAgentAssignmentStatus.IN_PROGRESS,
    }

    _POLICY_IDS: ClassVar[list[str]] = [
        "input-assignee-identity",
        "input-required-role",
        "input-required-capabilities",
        "input-assignment-status",
        "input-required-artifacts",
        "input-reference-availability",
        "input-request-context",
        "input-workspace-context",
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
            or (lambda: f"input-guardrail-{uuid4()}")
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"input-guardrail-violation-"
                    f"{index}-{uuid4()}"
                )
            )
        )

    def evaluate(
        self,
        snapshot: InputGuardrailSnapshot,
    ) -> GuardrailEvaluationResult:
        """Evaluate input guardrails for one assignment."""

        assignment = snapshot.assignment
        profile = snapshot.assignee_profile
        violations: list[GuardrailViolation] = []

        if (
            assignment.assignee.agent_id.strip().casefold()
            != profile.agent.agent_id.strip().casefold()
        ):
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-assignee-identity",
                    rule_id="assignee-profile-must-match",
                    code="ASSIGNEE_PROFILE_MISMATCH",
                    message=(
                        "Assignment assignee does not match "
                        "the supplied capability profile."
                    ),
                    field_path="assignment.assignee.agent_id",
                    remediation=(
                        "Supply the capability profile for "
                        "the assigned agent."
                    ),
                )
            )

        if assignment.required_role is not profile.agent.role:
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-required-role",
                    rule_id="required-role-must-match",
                    code="REQUIRED_ROLE_MISMATCH",
                    message=(
                        "Assignee role does not match "
                        "the assignment required role."
                    ),
                    field_path="assignment.required_role",
                    remediation=(
                        "Assign the task to an agent with "
                        "the required role."
                    ),
                )
            )

        missing_capabilities = [
            capability
            for capability in assignment.required_capabilities
            if not profile.has_capability(capability)
        ]

        for capability in missing_capabilities:
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id=(
                        "input-required-capabilities"
                    ),
                    rule_id="required-capability-must-exist",
                    code="MISSING_REQUIRED_CAPABILITY",
                    message=(
                        "Assignee lacks required capability: "
                        f"{capability.value}"
                    ),
                    field_path=(
                        "assignment.required_capabilities"
                    ),
                    remediation=(
                        "Select an agent profile containing "
                        "the required capability."
                    ),
                    details={
                        "capability": capability.value,
                    },
                )
            )

        if assignment.status not in self._EXECUTABLE_STATUSES:
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-assignment-status",
                    rule_id="assignment-status-executable",
                    code="ASSIGNMENT_STATUS_NOT_EXECUTABLE",
                    message=(
                        "Assignment status does not permit "
                        "agent execution."
                    ),
                    field_path="assignment.status",
                    remediation=(
                        "Transition the assignment to offered, "
                        "accepted, or in_progress."
                    ),
                    details={
                        "status": assignment.status.value,
                    },
                )
            )

        if snapshot.require_inputs and not assignment.inputs:
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-required-artifacts",
                    rule_id="assignment-inputs-required",
                    code="MISSING_ASSIGNMENT_INPUTS",
                    message=(
                        "Assignment requires at least one "
                        "input artifact."
                    ),
                    field_path="assignment.inputs",
                    remediation=(
                        "Attach the required input artifact."
                    ),
                )
            )

        available_reference_ids = {
            reference_id.strip().casefold()
            for reference_id in (
                snapshot.available_reference_ids
            )
        }

        for input_artifact in assignment.inputs:
            if (
                input_artifact.reference_id
                .strip()
                .casefold()
                in available_reference_ids
            ):
                continue

            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id=(
                        "input-reference-availability"
                    ),
                    rule_id="input-reference-must-exist",
                    code="INPUT_REFERENCE_NOT_AVAILABLE",
                    message=(
                        "Assignment input reference is not "
                        "available: "
                        f"{input_artifact.reference_id}"
                    ),
                    field_path="assignment.inputs",
                    remediation=(
                        "Register or produce the referenced "
                        "input artifact before execution."
                    ),
                    details={
                        "reference_id": (
                            input_artifact.reference_id
                        ),
                        "reference_type": (
                            input_artifact.reference_type
                        ),
                    },
                )
            )

        if (
            assignment.request_id
            != snapshot.expected_request_id
        ):
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-request-context",
                    rule_id="request-id-must-match",
                    code="REQUEST_CONTEXT_MISMATCH",
                    message=(
                        "Assignment request_id does not match "
                        "the execution context."
                    ),
                    field_path="assignment.request_id",
                    remediation=(
                        "Use an assignment from the current "
                        "research request."
                    ),
                )
            )

        if (
            assignment.workspace_id
            != snapshot.expected_workspace_id
        ):
            violations.append(
                self._violation(
                    index=len(violations) + 1,
                    policy_id="input-workspace-context",
                    rule_id="workspace-id-must-match",
                    code="WORKSPACE_CONTEXT_MISMATCH",
                    message=(
                        "Assignment workspace_id does not match "
                        "the execution context."
                    ),
                    field_path="assignment.workspace_id",
                    remediation=(
                        "Use an assignment from the current "
                        "research workspace."
                    ),
                )
            )

        decision = (
            GuardrailDecision.BLOCKED
            if violations
            else GuardrailDecision.ALLOWED
        )

        return GuardrailEvaluationResult(
            evaluation_id=self._new_identifier(
                self._evaluation_id_factory,
                field_name="evaluation_id",
            ),
            subject_id=assignment.assignment_id,
            scope=GuardrailScope.INPUT,
            decision=decision,
            violations=violations,
            evaluated_policy_ids=self._POLICY_IDS,
            summary=(
                "Input guardrail evaluation blocked "
                f"execution with {len(violations)} violations."
                if violations
                else (
                    "Input guardrail evaluation allowed "
                    "assignment execution."
                )
            ),
            metadata={
                "agent_id": profile.agent.agent_id,
                "request_id": assignment.request_id,
                "workspace_id": assignment.workspace_id,
            },
        )

    def _violation(
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
        """Build one blocking input violation."""

        return GuardrailViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            policy_id=policy_id,
            rule_id=rule_id,
            code=code,
            scope=GuardrailScope.INPUT,
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
    def _new_identifier(
        factory: Callable[[], str],
        *,
        field_name: str,
    ) -> str:
        """Generate one nonblank identifier."""

        value = factory()

        if not value.strip():
            raise InputGuardrailEvaluatorError(
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
            raise InputGuardrailEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
