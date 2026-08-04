"""Tests for deterministic guardrail policy schemas."""

import pytest
from pydantic import ValidationError

from app.guardrails.guardrail_policy import (
    GuardrailAction,
    GuardrailConditionOperator,
    GuardrailPolicy,
    GuardrailPolicySet,
    GuardrailRule,
    GuardrailRuleCondition,
    GuardrailScope,
    GuardrailSeverity,
)


def condition(
    *,
    condition_id: str = "condition-001",
    field_path: str = "assignment.inputs",
    operator: GuardrailConditionOperator = (
        GuardrailConditionOperator.EXISTS
    ),
    expected_value=None,
) -> GuardrailRuleCondition:
    """Return one guardrail condition."""

    return GuardrailRuleCondition(
        condition_id=condition_id,
        field_path=field_path,
        operator=operator,
        expected_value=expected_value,
        description="Validate one required field.",
    )


def rule(
    *,
    rule_id: str = "rule-001",
    enabled: bool = True,
) -> GuardrailRule:
    """Return one guardrail rule."""

    return GuardrailRule(
        rule_id=rule_id,
        name="Required input rule",
        description="Require assignment inputs.",
        conditions=[condition()],
        enabled=enabled,
    )


def policy(
    *,
    policy_id: str = "policy-001",
    scope: GuardrailScope = GuardrailScope.INPUT,
    priority: int = 100,
    enabled: bool = True,
) -> GuardrailPolicy:
    """Return one blocking guardrail policy."""

    return GuardrailPolicy(
        policy_id=policy_id,
        name="Required assignment inputs",
        description=(
            "Block assignments without required inputs."
        ),
        version="1.0.0",
        scope=scope,
        target_type="research_assignment",
        target_roles=["search_specialist"],
        rules=[rule()],
        severity=GuardrailSeverity.ERROR,
        action=GuardrailAction.BLOCK,
        blocking=True,
        retryable=False,
        priority=priority,
        remediation="Provide the required input artifacts.",
        enabled=enabled,
        tags=["input", "assignment"],
    )


def test_guardrail_policy_returns_active_rules() -> None:
    value = GuardrailPolicy(
        policy_id="policy-active-rules",
        name="Active rules",
        description="Return enabled rules only.",
        version="1.0.0",
        scope=GuardrailScope.INPUT,
        target_type="assignment",
        rules=[
            rule(rule_id="rule-enabled"),
            rule(
                rule_id="rule-disabled",
                enabled=False,
            ),
        ],
        severity=GuardrailSeverity.WARNING,
        action=GuardrailAction.WARN,
    )

    assert [
        item.rule_id
        for item in value.active_rules
    ] == ["rule-enabled"]


def test_condition_requires_expected_value() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "condition operator requires expected_value"
        ),
    ):
        condition(
            operator=GuardrailConditionOperator.EQUALS,
        )


def test_existence_condition_rejects_expected_value() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "existence condition must not include "
            "expected_value"
        ),
    ):
        condition(expected_value=True)


def test_rule_rejects_duplicate_condition_ids() -> None:
    duplicate = condition()

    with pytest.raises(
        ValidationError,
        match=(
            "rule conditions must have unique "
            "condition IDs"
        ),
    ):
        GuardrailRule(
            rule_id="rule-duplicate",
            name="Duplicate conditions",
            description="Condition IDs must be unique.",
            conditions=[
                duplicate,
                duplicate,
            ],
        )


def test_policy_rejects_duplicate_rule_ids() -> None:
    duplicate = rule()

    with pytest.raises(
        ValidationError,
        match=(
            "policy rules must have unique rule IDs"
        ),
    ):
        GuardrailPolicy(
            policy_id="policy-duplicate-rules",
            name="Duplicate rules",
            description="Rule IDs must be unique.",
            version="1.0.0",
            scope=GuardrailScope.INPUT,
            target_type="assignment",
            rules=[
                duplicate,
                duplicate,
            ],
            severity=GuardrailSeverity.ERROR,
            action=GuardrailAction.BLOCK,
            blocking=True,
        )


def test_blocking_policy_requires_blocking_action() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "blocking policy requires a blocking action"
        ),
    ):
        GuardrailPolicy(
            policy_id="policy-invalid-action",
            name="Invalid blocking action",
            description="Blocking policy cannot only log.",
            version="1.0.0",
            scope=GuardrailScope.INPUT,
            target_type="assignment",
            rules=[rule()],
            severity=GuardrailSeverity.ERROR,
            action=GuardrailAction.LOG,
            blocking=True,
        )


def test_retry_action_requires_retryable_policy() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retry action requires retryable policy"
        ),
    ):
        GuardrailPolicy(
            policy_id="policy-invalid-retry",
            name="Invalid retry policy",
            description="Retry action must be retryable.",
            version="1.0.0",
            scope=GuardrailScope.TOOL,
            target_type="tool_call",
            rules=[rule()],
            severity=GuardrailSeverity.ERROR,
            action=GuardrailAction.RETRY,
            blocking=True,
            retryable=False,
        )


def test_retryable_policy_requires_supported_action() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "retryable policy requires retry or "
            "request_revision action"
        ),
    ):
        GuardrailPolicy(
            policy_id="policy-invalid-retryable",
            name="Invalid retryable policy",
            description="Warn action cannot retry.",
            version="1.0.0",
            scope=GuardrailScope.OUTPUT,
            target_type="agent_result",
            rules=[rule()],
            severity=GuardrailSeverity.WARNING,
            action=GuardrailAction.WARN,
            retryable=True,
        )


def test_policy_rejects_duplicate_target_roles() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "target_roles must not contain duplicates"
        ),
    ):
        GuardrailPolicy(
            policy_id="policy-duplicate-roles",
            name="Duplicate roles",
            description="Role names must be unique.",
            version="1.0.0",
            scope=GuardrailScope.AGENT,
            target_type="agent",
            target_roles=[
                "Search_Specialist",
                "search_specialist",
            ],
            rules=[rule()],
            severity=GuardrailSeverity.WARNING,
            action=GuardrailAction.WARN,
        )


def test_policy_set_orders_enabled_policies() -> None:
    policy_set = GuardrailPolicySet(
        policy_set_id="policy-set-001",
        name="AIRA guardrails",
        description="Baseline guardrail policies.",
        version="1.0.0",
        policies=[
            policy(
                policy_id="policy-later",
                priority=200,
            ),
            policy(
                policy_id="policy-first",
                priority=10,
            ),
            policy(
                policy_id="policy-disabled",
                priority=0,
                enabled=False,
            ),
        ],
    )

    assert [
        item.policy_id
        for item in policy_set.enabled_policies
    ] == [
        "policy-first",
        "policy-later",
    ]


def test_policy_set_filters_by_scope() -> None:
    policy_set = GuardrailPolicySet(
        policy_set_id="policy-set-001",
        name="AIRA guardrails",
        description="Baseline guardrail policies.",
        version="1.0.0",
        policies=[
            policy(
                policy_id="policy-input",
                scope=GuardrailScope.INPUT,
            ),
            policy(
                policy_id="policy-output",
                scope=GuardrailScope.OUTPUT,
            ),
        ],
    )

    assert [
        item.policy_id
        for item in policy_set.policies_for_scope(
            GuardrailScope.OUTPUT
        )
    ] == ["policy-output"]


def test_policy_set_finds_policy_case_insensitively() -> None:
    policy_set = GuardrailPolicySet(
        policy_set_id="policy-set-001",
        name="AIRA guardrails",
        description="Baseline guardrail policies.",
        version="1.0.0",
        policies=[
            policy(policy_id="Policy-001"),
        ],
    )

    value = policy_set.policy_by_id("policy-001")

    assert value is not None
    assert value.policy_id == "Policy-001"
    assert policy_set.policy_by_id("missing") is None


def test_policy_set_rejects_duplicate_policy_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "policy set must have unique policy IDs"
        ),
    ):
        GuardrailPolicySet(
            policy_set_id="policy-set-duplicate",
            name="Duplicate policies",
            description="Policy IDs must be unique.",
            version="1.0.0",
            policies=[
                policy(policy_id="POLICY-001"),
                policy(policy_id="policy-001"),
            ],
        )
