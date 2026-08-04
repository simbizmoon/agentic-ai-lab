"""Schemas for deterministic guardrail policy definitions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


class GuardrailScope(StrEnum):
    """Execution scope where a guardrail applies."""

    INPUT = "input"
    OUTPUT = "output"
    TOOL = "tool"
    ASSIGNMENT = "assignment"
    AGENT = "agent"
    WORKFLOW = "workflow"
    EVALUATION = "evaluation"


class GuardrailSeverity(StrEnum):
    """Severity assigned to a guardrail violation."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class GuardrailAction(StrEnum):
    """Action taken when a guardrail is triggered."""

    ALLOW = "allow"
    LOG = "log"
    WARN = "warn"
    BLOCK = "block"
    REQUEST_REVISION = "request_revision"
    RETRY = "retry"
    CANCEL = "cancel"
    QUARANTINE = "quarantine"


class GuardrailConditionOperator(StrEnum):
    """Operator used by one deterministic guardrail condition."""

    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    MATCHES = "matches"


class GuardrailRuleCondition(BaseModel):
    """One deterministic condition in a guardrail rule."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    condition_id: str
    field_path: str
    operator: GuardrailConditionOperator
    expected_value: JsonValue | None = None
    description: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        """Validate condition identity and operator semantics."""

        required_text = {
            "condition_id": self.condition_id,
            "field_path": self.field_path,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        value_optional_operators = {
            GuardrailConditionOperator.EXISTS,
            GuardrailConditionOperator.NOT_EXISTS,
        }

        if (
            self.operator not in value_optional_operators
            and self.expected_value is None
        ):
            raise ValueError(
                "condition operator requires expected_value"
            )

        if (
            self.operator in value_optional_operators
            and self.expected_value is not None
        ):
            raise ValueError(
                "existence condition must not include "
                "expected_value"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class GuardrailRule(BaseModel):
    """One executable rule within a guardrail policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    rule_id: str
    name: str
    description: str
    conditions: list[GuardrailRuleCondition] = Field(
        min_length=1
    )
    match_all: bool = True
    enabled: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        """Validate rule text and condition uniqueness."""

        required_text = {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        condition_ids = [
            condition.condition_id.strip().casefold()
            for condition in self.conditions
        ]

        if len(set(condition_ids)) != len(condition_ids):
            raise ValueError(
                "rule conditions must have unique "
                "condition IDs"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class GuardrailPolicy(BaseModel):
    """One versioned guardrail policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    policy_id: str
    name: str
    description: str
    version: str
    scope: GuardrailScope
    target_type: str
    target_roles: list[str] = Field(default_factory=list)
    rules: list[GuardrailRule] = Field(min_length=1)
    severity: GuardrailSeverity
    action: GuardrailAction
    blocking: bool = False
    retryable: bool = False
    priority: int = Field(default=100, ge=0)
    remediation: str | None = None
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        """Validate policy semantics and rule uniqueness."""

        required_text = {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "target_type": self.target_type,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        rule_ids = [
            rule.rule_id.strip().casefold()
            for rule in self.rules
        ]

        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError(
                "policy rules must have unique rule IDs"
            )

        self._validate_unique_text(
            self.target_roles,
            field_name="target_roles",
        )
        self._validate_unique_text(
            self.tags,
            field_name="tags",
        )

        blocking_actions = {
            GuardrailAction.BLOCK,
            GuardrailAction.REQUEST_REVISION,
            GuardrailAction.RETRY,
            GuardrailAction.CANCEL,
            GuardrailAction.QUARANTINE,
        }

        if self.blocking and self.action not in blocking_actions:
            raise ValueError(
                "blocking policy requires a blocking action"
            )

        if (
            self.action is GuardrailAction.RETRY
            and not self.retryable
        ):
            raise ValueError(
                "retry action requires retryable policy"
            )

        if (
            self.retryable
            and self.action
            not in {
                GuardrailAction.RETRY,
                GuardrailAction.REQUEST_REVISION,
            }
        ):
            raise ValueError(
                "retryable policy requires retry or "
                "request_revision action"
            )

        if (
            self.remediation is not None
            and not self.remediation.strip()
        ):
            raise ValueError(
                "remediation must not be blank when provided"
            )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank strings."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def active_rules(self) -> list[GuardrailRule]:
        """Return enabled rules."""

        return [
            rule
            for rule in self.rules
            if rule.enabled
        ]


class GuardrailPolicySet(BaseModel):
    """Ordered collection of guardrail policies."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    policy_set_id: str
    name: str
    description: str
    version: str
    policies: list[GuardrailPolicy] = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_policy_set(self) -> Self:
        """Validate policy-set identity and policy uniqueness."""

        required_text = {
            "policy_set_id": self.policy_set_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        policy_ids = [
            policy.policy_id.strip().casefold()
            for policy in self.policies
        ]

        if len(set(policy_ids)) != len(policy_ids):
            raise ValueError(
                "policy set must have unique policy IDs"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @property
    def enabled_policies(self) -> list[GuardrailPolicy]:
        """Return enabled policies ordered by priority."""

        return sorted(
            (
                policy
                for policy in self.policies
                if policy.enabled
            ),
            key=lambda policy: (
                policy.priority,
                policy.policy_id.casefold(),
            ),
        )

    def policies_for_scope(
        self,
        scope: GuardrailScope,
    ) -> list[GuardrailPolicy]:
        """Return enabled policies for one scope."""

        return [
            policy
            for policy in self.enabled_policies
            if policy.scope is scope
        ]

    def policy_by_id(
        self,
        policy_id: str,
    ) -> GuardrailPolicy | None:
        """Return one policy using case-insensitive matching."""

        normalized = policy_id.strip().casefold()

        return next(
            (
                policy
                for policy in self.policies
                if policy.policy_id.strip().casefold()
                == normalized
            ),
            None,
        )
