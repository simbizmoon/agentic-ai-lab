"""Deterministic policy for storing agent memories."""

from __future__ import annotations

from app.memory.sensitive_memory_detector import (
    detect_secret_content,
    detect_sensitive_content,
)
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_policy_config import (
    MemoryPolicyConfig,
)
from app.schemas.memory_policy_result import (
    MemoryPolicyDecision,
    MemoryPolicyReason,
    MemoryPolicyResult,
)
from app.schemas.memory_record import (
    MemoryKind,
    MemoryScope,
    MemorySource,
)


class MemoryPolicy:
    """Evaluate whether a memory candidate may be stored."""

    def __init__(
        self,
        *,
        config: MemoryPolicyConfig | None = None,
    ) -> None:
        self._config = config or MemoryPolicyConfig()

    @property
    def config(self) -> MemoryPolicyConfig:
        """Return the configured policy settings."""

        return self._config

    def evaluate(
        self,
        request: MemoryCreate,
    ) -> MemoryPolicyResult:
        """Evaluate one memory creation request."""

        rejection_reasons = self._rejection_reasons(
            request
        )

        if rejection_reasons:
            return MemoryPolicyResult(
                decision=MemoryPolicyDecision.REJECT,
                reasons=rejection_reasons,
                safe_message=(
                    "The memory candidate cannot be stored "
                    "under the current policy."
                ),
                requires_user_approval=False,
            )

        approval_reasons = self._approval_reasons(
            request
        )

        if approval_reasons:
            return MemoryPolicyResult(
                decision=(
                    MemoryPolicyDecision.REQUIRE_APPROVAL
                ),
                reasons=approval_reasons,
                safe_message=(
                    "The memory candidate requires explicit "
                    "user approval before storage."
                ),
                requires_user_approval=True,
            )

        return MemoryPolicyResult(
            decision=MemoryPolicyDecision.ALLOW,
            reasons=[MemoryPolicyReason.ALLOWED],
            safe_message=(
                "The memory candidate may be stored."
            ),
            requires_user_approval=False,
        )

    def _rejection_reasons(
        self,
        request: MemoryCreate,
    ) -> list[MemoryPolicyReason]:
        """Return all deterministic rejection reasons."""

        reasons: list[MemoryPolicyReason] = []

        if detect_secret_content(request.content):
            reasons.append(
                MemoryPolicyReason.SECRET_CONTENT
            )

        if (
            self.config.reject_sensitive_content
            and detect_sensitive_content(request.content)
        ):
            reasons.append(
                MemoryPolicyReason.SENSITIVE_CONTENT
            )

        if (
            request.importance
            < self.config.minimum_importance
        ):
            reasons.append(
                MemoryPolicyReason.LOW_IMPORTANCE
            )

        if (
            self.config.require_expiration_for_working_memory
            and request.kind is MemoryKind.WORKING
            and request.expires_at is None
        ):
            reasons.append(
                MemoryPolicyReason
                .WORKING_MEMORY_REQUIRES_EXPIRATION
            )

        if (
            self.config.require_expiration_for_session_scope
            and request.scope is MemoryScope.SESSION
            and request.expires_at is None
        ):
            reasons.append(
                MemoryPolicyReason
                .SESSION_MEMORY_REQUIRES_EXPIRATION
            )

        sources_requiring_reference = {
            MemorySource.TOOL_RESULT,
            MemorySource.AGENT_INFERENCE,
            MemorySource.IMPORTED_DOCUMENT,
        }

        if (
            request.source in sources_requiring_reference
            and request.source_reference is None
        ):
            reasons.append(
                MemoryPolicyReason
                .SOURCE_REFERENCE_REQUIRED
            )

        if (
            request.source is MemorySource.AGENT_INFERENCE
            and request.confidence
            < self.config.minimum_inference_confidence
        ):
            reasons.append(
                MemoryPolicyReason
                .LOW_CONFIDENCE_INFERENCE
            )

        return list(dict.fromkeys(reasons))

    def _approval_reasons(
        self,
        request: MemoryCreate,
    ) -> list[MemoryPolicyReason]:
        """Return reasons requiring explicit approval."""

        if (
            request.source is MemorySource.AGENT_INFERENCE
            and self.config.inferred_memory_requires_approval
        ):
            return [
                MemoryPolicyReason
                .INFERENCE_REQUIRES_APPROVAL
            ]

        return []
