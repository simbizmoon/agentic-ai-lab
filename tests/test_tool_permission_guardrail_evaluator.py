"""Tests for deterministic tool permission guardrails."""

import pytest
from pydantic import ValidationError

from app.guardrails.guardrail_result import (
    GuardrailDecision,
)
from app.guardrails.tool_permission import (
    AgentToolPermissionProfile,
    ToolAccessMode,
    ToolCallRequest,
    ToolPermissionRule,
    ToolRiskLevel,
)
from app.guardrails.tool_permission_guardrail_evaluator import (
    ToolPermissionGuardrailEvaluator,
)
from app.guardrails.tool_permission_guardrail_evaluator_error import (
    ToolPermissionGuardrailEvaluatorError,
)
from app.guardrails.tool_permission_guardrail_snapshot import (
    ToolPermissionGuardrailSnapshot,
)
from app.schemas.research_agent import ResearchAgentRole


def permission_rule(
    *,
    tool_name: str = "source_search",
    access_mode: ToolAccessMode = ToolAccessMode.READ_ONLY,
    allow_external_network: bool = True,
    allow_sensitive_operations: bool = False,
    maximum_calls: int | None = 3,
    allowed_roles: list[ResearchAgentRole] | None = None,
) -> ToolPermissionRule:
    """Return one tool permission rule."""

    return ToolPermissionRule(
        tool_name=tool_name,
        allowed_operations=[
            "search",
            "read",
        ],
        access_mode=access_mode,
        allow_external_network=allow_external_network,
        allow_sensitive_operations=(
            allow_sensitive_operations
        ),
        maximum_calls=maximum_calls,
        allowed_roles=(
            allowed_roles
            if allowed_roles is not None
            else [
                ResearchAgentRole.SEARCH_SPECIALIST,
            ]
        ),
    )


def profile(
    *,
    rules: list[ToolPermissionRule] | None = None,
    default_deny: bool = True,
) -> AgentToolPermissionProfile:
    """Return one search-specialist permission profile."""

    return AgentToolPermissionProfile(
        profile_id="tool-profile-001",
        agent_id="agent-search-001",
        agent_role=ResearchAgentRole.SEARCH_SPECIALIST,
        rules=rules if rules is not None else [
            permission_rule()
        ],
        default_deny=default_deny,
    )


def request(
    **overrides: object,
) -> ToolCallRequest:
    """Return one valid tool-call request."""

    values: dict[str, object] = {
        "call_id": "tool-call-001",
        "request_id": "research-001",
        "workspace_id": "workspace-001",
        "agent_id": "agent-search-001",
        "agent_role": (
            ResearchAgentRole.SEARCH_SPECIALIST
        ),
        "tool_name": "source_search",
        "operation": "search",
        "write_operation": False,
        "external_network": True,
        "sensitive_operation": False,
        "sensitive_operation_approved": False,
        "risk_level": ToolRiskLevel.LOW,
    }
    values.update(overrides)

    return ToolCallRequest.model_validate(values)


def snapshot(
    *,
    request_value: ToolCallRequest | None = None,
    permission_profile: (
        AgentToolPermissionProfile | None
    ) = None,
    expected_request_id: str = "research-001",
    expected_workspace_id: str = "workspace-001",
    prior_tool_call_count: int = 0,
    warn_on_high_risk: bool = True,
) -> ToolPermissionGuardrailSnapshot:
    """Return one valid tool permission snapshot."""

    return ToolPermissionGuardrailSnapshot(
        request=request_value or request(),
        permission_profile=permission_profile or profile(),
        expected_request_id=expected_request_id,
        expected_workspace_id=expected_workspace_id,
        prior_tool_call_count=prior_tool_call_count,
        warn_on_high_risk=warn_on_high_risk,
    )


def evaluator() -> ToolPermissionGuardrailEvaluator:
    """Return one deterministic evaluator."""

    return ToolPermissionGuardrailEvaluator(
        evaluation_id_factory=(
            lambda: "tool-guardrail-evaluation-001"
        ),
        violation_id_factory=(
            lambda index: f"violation-{index:03d}"
        ),
    )


def test_allowed_tool_call_passes() -> None:
    value = evaluator().evaluate(snapshot())

    assert value.decision is GuardrailDecision.ALLOWED
    assert value.allowed is True
    assert value.violations == []


def test_unknown_tool_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                tool_name="unknown_tool"
            )
        )
    )

    assert value.decision is GuardrailDecision.BLOCKED
    assert any(
        violation.code == "TOOL_NOT_ALLOWED"
        for violation in value.violations
    )


def test_default_allow_profile_permits_unknown_tool() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                tool_name="unknown_tool"
            ),
            permission_profile=profile(
                default_deny=False
            ),
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_disallowed_operation_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                operation="delete"
            )
        )
    )

    assert any(
        violation.code == "TOOL_OPERATION_NOT_ALLOWED"
        for violation in value.violations
    )


def test_write_with_read_only_permission_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                operation="read",
                write_operation=True,
            )
        )
    )

    assert any(
        violation.code == "TOOL_WRITE_NOT_ALLOWED"
        for violation in value.violations
    )


def test_write_with_read_write_permission_is_allowed() -> None:
    rule = ToolPermissionRule(
        tool_name="source_search",
        allowed_operations=["update"],
        access_mode=ToolAccessMode.READ_WRITE,
        allow_external_network=False,
        maximum_calls=3,
        allowed_roles=[
            ResearchAgentRole.SEARCH_SPECIALIST,
        ],
    )

    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                operation="update",
                write_operation=True,
                external_network=False,
            ),
            permission_profile=profile(rules=[rule]),
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_external_network_without_permission_is_blocked() -> None:
    rule = permission_rule(
        allow_external_network=False
    )

    value = evaluator().evaluate(
        snapshot(
            permission_profile=profile(rules=[rule])
        )
    )

    assert any(
        violation.code == "EXTERNAL_NETWORK_NOT_ALLOWED"
        for violation in value.violations
    )


def test_sensitive_operation_without_approval_is_blocked() -> None:
    rule = permission_rule(
        allow_sensitive_operations=True
    )

    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                sensitive_operation=True,
                sensitive_operation_approved=False,
            ),
            permission_profile=profile(rules=[rule]),
        )
    )

    assert any(
        violation.code
        == "SENSITIVE_TOOL_OPERATION_NOT_APPROVED"
        for violation in value.violations
    )


def test_approved_sensitive_operation_is_allowed() -> None:
    rule = permission_rule(
        allow_sensitive_operations=True
    )

    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                sensitive_operation=True,
                sensitive_operation_approved=True,
            ),
            permission_profile=profile(rules=[rule]),
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_disallowed_role_is_blocked() -> None:
    rule = permission_rule(
        allowed_roles=[
            ResearchAgentRole.SOURCE_READER,
        ]
    )

    value = evaluator().evaluate(
        snapshot(
            permission_profile=profile(rules=[rule])
        )
    )

    assert any(
        violation.code == "TOOL_ROLE_NOT_ALLOWED"
        for violation in value.violations
    )


def test_call_limit_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(prior_tool_call_count=3)
    )

    assert any(
        violation.code == "TOOL_CALL_LIMIT_EXCEEDED"
        for violation in value.violations
    )


def test_high_risk_allowed_call_warns() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                risk_level=ToolRiskLevel.HIGH
            )
        )
    )

    assert value.decision is GuardrailDecision.WARNED
    assert value.allowed is True
    assert value.blocking_violations == []
    assert any(
        violation.code == "HIGH_RISK_TOOL_OPERATION"
        for violation in value.violations
    )


def test_high_risk_warning_can_be_disabled() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                risk_level=ToolRiskLevel.HIGH
            ),
            warn_on_high_risk=False,
        )
    )

    assert value.decision is GuardrailDecision.ALLOWED


def test_agent_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            request_value=request(
                agent_id="agent-other"
            )
        )
    )

    assert any(
        violation.code
        == "TOOL_AGENT_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_request_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            expected_request_id="research-other"
        )
    )

    assert any(
        violation.code
        == "TOOL_REQUEST_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_workspace_context_mismatch_is_blocked() -> None:
    value = evaluator().evaluate(
        snapshot(
            expected_workspace_id="workspace-other"
        )
    )

    assert any(
        violation.code
        == "TOOL_WORKSPACE_CONTEXT_MISMATCH"
        for violation in value.violations
    )


def test_profile_rejects_duplicate_tool_names() -> None:
    duplicate = permission_rule()

    with pytest.raises(
        ValidationError,
        match="rules must have unique tool names",
    ):
        profile(
            rules=[
                duplicate,
                duplicate,
            ]
        )


def test_request_rejects_invalid_sensitive_approval() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "sensitive approval requires "
            "sensitive_operation"
        ),
    ):
        request(
            sensitive_operation=False,
            sensitive_operation_approved=True,
        )


def test_evaluator_rejects_blank_evaluation_id() -> None:
    value = ToolPermissionGuardrailEvaluator(
        evaluation_id_factory=lambda: " ",
    )

    with pytest.raises(
        ToolPermissionGuardrailEvaluatorError,
        match=(
            "evaluation_id factory returned blank value"
        ),
    ):
        value.evaluate(snapshot())
