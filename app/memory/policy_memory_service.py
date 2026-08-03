"""Memory creation service with deterministic policy enforcement."""

from __future__ import annotations

from app.memory.memory_policy import MemoryPolicy
from app.memory.memory_service import MemoryService
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_policy_result import (
    MemoryPolicyDecision,
    MemoryPolicyResult,
)
from app.schemas.memory_record import MemoryRecord


class MemoryPolicyRejectedError(RuntimeError):
    """Raised when memory storage is rejected by policy."""

    def __init__(
        self,
        *,
        result: MemoryPolicyResult,
    ) -> None:
        super().__init__(result.safe_message)
        self.result = result


class MemoryApprovalRequiredError(RuntimeError):
    """Raised when memory storage requires user approval."""

    def __init__(
        self,
        *,
        result: MemoryPolicyResult,
    ) -> None:
        super().__init__(result.safe_message)
        self.result = result


class PolicyMemoryService:
    """Apply storage policy before creating memories."""

    def __init__(
        self,
        *,
        memory_service: MemoryService,
        policy: MemoryPolicy,
    ) -> None:
        self._memory_service = memory_service
        self._policy = policy

    @property
    def memory_service(self) -> MemoryService:
        """Return the underlying memory service."""

        return self._memory_service

    @property
    def policy(self) -> MemoryPolicy:
        """Return the configured storage policy."""

        return self._policy

    def evaluate(
        self,
        request: MemoryCreate,
    ) -> MemoryPolicyResult:
        """Return the policy decision without storing."""

        return self.policy.evaluate(request)

    def ensure_allowed(
        self,
        request: MemoryCreate,
        *,
        user_approved: bool = False,
    ) -> MemoryPolicyResult:
        """Validate policy requirements without storing."""

        result = self.evaluate(request)

        if result.decision is MemoryPolicyDecision.REJECT:
            raise MemoryPolicyRejectedError(
                result=result
            )

        if (
            result.decision
            is MemoryPolicyDecision.REQUIRE_APPROVAL
            and not user_approved
        ):
            raise MemoryApprovalRequiredError(
                result=result
            )

        return result

    def create(
        self,
        request: MemoryCreate,
        *,
        user_approved: bool = False,
    ) -> MemoryRecord:
        """Store a memory if policy requirements are satisfied."""

        self.ensure_allowed(
            request,
            user_approved=user_approved,
        )

        return self.memory_service.create(request)
