"""Deterministic guardrails for agent tool permissions."""

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
from app.guardrails.tool_permission import (
    ToolAccessMode,
    ToolRiskLevel,
)
from app.guardrails.tool_permission_guardrail_evaluator_error import (
    ToolPermissionGuardrailEvaluatorError,
)
from app.guardrails.tool_permission_guardrail_snapshot import (
    ToolPermissionGuardrailSnapshot,
)


class ToolPermissionGuardrailEvaluator:
    """Evaluate one tool-call request before execution."""

    _POLICY_IDS: ClassVar[list[str]] = [
        "tool-agent-context",
        "tool-request-context",
        "tool-workspace-context",
        "tool-allowlist",
        "tool-operation-permission",
        "tool-write-permission",
        "tool-network-permission",
        "tool-sensitive-operation",
        "tool-role-permission",
        "tool-call-limit",
        "tool-risk-warning",
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
            or (lambda: f"tool-guardrail-{uuid4()}")
        )
        self._violation_id_factory = (
            violation_id_factory
            or (
                lambda index: (
                    f"tool-guardrail-violation-"
                    f"{index}-{uuid4()}"
                )
            )
        )

    def evaluate(
        self,
        snapshot: ToolPermissionGuardrailSnapshot,
    ) -> GuardrailEvaluationResult:
        """Evaluate one tool-call request."""

        request = snapshot.request
        profile = snapshot.permission_profile
        violations: list[GuardrailViolation] = []

        if (
            request.agent_id.strip().casefold()
            != profile.agent_id.strip().casefold()
            or request.agent_role is not profile.agent_role
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-agent-context",
                    rule_id="tool-agent-must-match-profile",
                    code="TOOL_AGENT_CONTEXT_MISMATCH",
                    message=(
                        "Tool request agent does not match "
                        "the permission profile."
                    ),
                    field_path="request.agent_id",
                    remediation=(
                        "Use the tool permission profile "
                        "assigned to the requesting agent."
                    ),
                )
            )

        if request.request_id != snapshot.expected_request_id:
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-request-context",
                    rule_id="tool-request-id-must-match",
                    code="TOOL_REQUEST_CONTEXT_MISMATCH",
                    message=(
                        "Tool call request_id does not match "
                        "the execution context."
                    ),
                    field_path="request.request_id",
                    remediation=(
                        "Use the current research request ID."
                    ),
                )
            )

        if (
            request.workspace_id
            != snapshot.expected_workspace_id
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-workspace-context",
                    rule_id="tool-workspace-id-must-match",
                    code="TOOL_WORKSPACE_CONTEXT_MISMATCH",
                    message=(
                        "Tool call workspace_id does not match "
                        "the execution context."
                    ),
                    field_path="request.workspace_id",
                    remediation=(
                        "Use the current research workspace ID."
                    ),
                )
            )

        rule = profile.rule_for_tool(request.tool_name)

        if rule is None:
            if profile.default_deny:
                violations.append(
                    self._blocking_violation(
                        index=len(violations) + 1,
                        policy_id="tool-allowlist",
                        rule_id="requested-tool-must-be-allowed",
                        code="TOOL_NOT_ALLOWED",
                        message=(
                            "Requested tool is not present "
                            "in the permission profile."
                        ),
                        field_path="request.tool_name",
                        remediation=(
                            "Use an allowed tool or update "
                            "the permission profile."
                        ),
                        details={
                            "tool_name": request.tool_name,
                        },
                    )
                )

            return self._result(
                snapshot=snapshot,
                violations=violations,
            )

        allowed_operations = {
            operation.strip().casefold()
            for operation in rule.allowed_operations
        }

        if (
            request.operation.strip().casefold()
            not in allowed_operations
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-operation-permission",
                    rule_id="tool-operation-must-be-allowed",
                    code="TOOL_OPERATION_NOT_ALLOWED",
                    message=(
                        "Requested operation is not allowed "
                        "for this tool."
                    ),
                    field_path="request.operation",
                    remediation=(
                        "Use one of the permitted operations."
                    ),
                    details={
                        "operation": request.operation,
                    },
                )
            )

        if (
            request.write_operation
            and rule.access_mode is ToolAccessMode.READ_ONLY
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-write-permission",
                    rule_id="write-operation-requires-write-access",
                    code="TOOL_WRITE_NOT_ALLOWED",
                    message=(
                        "Write operation requested with "
                        "read-only tool permission."
                    ),
                    field_path="request.write_operation",
                    remediation=(
                        "Use a read operation or request "
                        "read-write permission."
                    ),
                )
            )

        if (
            request.external_network
            and not rule.allow_external_network
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-network-permission",
                    rule_id="external-network-must-be-allowed",
                    code="EXTERNAL_NETWORK_NOT_ALLOWED",
                    message=(
                        "Tool call requests external network "
                        "access without permission."
                    ),
                    field_path="request.external_network",
                    remediation=(
                        "Disable external access or use "
                        "an approved permission rule."
                    ),
                )
            )

        if request.sensitive_operation:
            sensitive_allowed = (
                rule.allow_sensitive_operations
                and request.sensitive_operation_approved
            )

            if not sensitive_allowed:
                violations.append(
                    self._blocking_violation(
                        index=len(violations) + 1,
                        policy_id="tool-sensitive-operation",
                        rule_id=(
                            "sensitive-operation-requires-approval"
                        ),
                        code="SENSITIVE_TOOL_OPERATION_NOT_APPROVED",
                        message=(
                            "Sensitive tool operation lacks "
                            "permission or explicit approval."
                        ),
                        field_path=(
                            "request.sensitive_operation"
                        ),
                        remediation=(
                            "Obtain explicit approval and "
                            "sensitive-operation permission."
                        ),
                    )
                )

        if (
            rule.allowed_roles
            and request.agent_role not in rule.allowed_roles
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-role-permission",
                    rule_id="agent-role-must-be-allowed",
                    code="TOOL_ROLE_NOT_ALLOWED",
                    message=(
                        "Agent role is not allowed "
                        "to use this tool."
                    ),
                    field_path="request.agent_role",
                    remediation=(
                        "Use an agent role permitted "
                        "by the tool rule."
                    ),
                )
            )

        if (
            rule.maximum_calls is not None
            and snapshot.prior_tool_call_count
            >= rule.maximum_calls
        ):
            violations.append(
                self._blocking_violation(
                    index=len(violations) + 1,
                    policy_id="tool-call-limit",
                    rule_id="tool-call-count-within-limit",
                    code="TOOL_CALL_LIMIT_EXCEEDED",
                    message=(
                        "Tool call limit has been reached."
                    ),
                    field_path="prior_tool_call_count",
                    remediation=(
                        "Stop additional calls or increase "
                        "the configured call limit."
                    ),
                    details={
                        "maximum_calls": rule.maximum_calls,
                        "prior_tool_call_count": (
                            snapshot.prior_tool_call_count
                        ),
                    },
                )
            )

        if (
            snapshot.warn_on_high_risk
            and request.risk_level
            in {
                ToolRiskLevel.HIGH,
                ToolRiskLevel.CRITICAL,
            }
            and not any(
                violation.blocking
                for violation in violations
            )
        ):
            violations.append(
                self._warning_violation(
                    index=len(violations) + 1,
                    policy_id="tool-risk-warning",
                    rule_id="high-risk-operation-warning",
                    code="HIGH_RISK_TOOL_OPERATION",
                    message=(
                        "A high-risk tool operation "
                        "was permitted."
                    ),
                    field_path="request.risk_level",
                    remediation=(
                        "Review audit logs after execution."
                    ),
                )
            )

        return self._result(
            snapshot=snapshot,
            violations=violations,
        )

    def _result(
        self,
        *,
        snapshot: ToolPermissionGuardrailSnapshot,
        violations: list[GuardrailViolation],
    ) -> GuardrailEvaluationResult:
        """Build the complete guardrail decision."""

        blocking = any(
            violation.blocking
            for violation in violations
        )

        if blocking:
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
            subject_id=snapshot.request.call_id,
            scope=GuardrailScope.TOOL,
            decision=decision,
            violations=violations,
            evaluated_policy_ids=self._POLICY_IDS,
            summary=(
                "Tool permission guardrail completed with "
                f"decision {decision.value} and "
                f"{len(violations)} violations."
            ),
            metadata={
                "agent_id": snapshot.request.agent_id,
                "tool_name": snapshot.request.tool_name,
                "operation": snapshot.request.operation,
            },
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
        """Build one blocking tool violation."""

        return GuardrailViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            policy_id=policy_id,
            rule_id=rule_id,
            code=code,
            scope=GuardrailScope.TOOL,
            severity=GuardrailSeverity.ERROR,
            action=GuardrailAction.BLOCK,
            message=message,
            blocking=True,
            retryable=False,
            field_path=field_path,
            remediation=remediation,
            details=details or {},
        )

    def _warning_violation(
        self,
        *,
        index: int,
        policy_id: str,
        rule_id: str,
        code: str,
        message: str,
        field_path: str,
        remediation: str,
    ) -> GuardrailViolation:
        """Build one nonblocking tool warning."""

        return GuardrailViolation(
            violation_id=self._new_indexed_identifier(
                self._violation_id_factory,
                index=index,
                field_name="violation_id",
            ),
            policy_id=policy_id,
            rule_id=rule_id,
            code=code,
            scope=GuardrailScope.TOOL,
            severity=GuardrailSeverity.WARNING,
            action=GuardrailAction.WARN,
            message=message,
            blocking=False,
            retryable=False,
            field_path=field_path,
            remediation=remediation,
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
            raise ToolPermissionGuardrailEvaluatorError(
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
            raise ToolPermissionGuardrailEvaluatorError(
                f"{field_name} factory returned blank value"
            )

        return value
