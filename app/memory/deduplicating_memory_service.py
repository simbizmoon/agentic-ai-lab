"""Memory creation service with duplicate handling."""

from __future__ import annotations

from app.memory.memory_deduplicator import (
    MemoryDeduplicator,
)
from app.memory.memory_service import MemoryService
from app.memory.policy_memory_service import (
    PolicyMemoryService,
)
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_deduplication import (
    MemoryDeduplicationAction,
    MemoryDeduplicationResult,
)
from app.schemas.memory_record import MemoryRecord
from app.schemas.memory_update import MemoryUpdate


class DeduplicatingMemoryService:
    """Apply policy and deterministic duplicate handling."""

    def __init__(
        self,
        *,
        policy_service: PolicyMemoryService,
        deduplicator: MemoryDeduplicator,
    ) -> None:
        self._policy_service = policy_service
        self._deduplicator = deduplicator

    @property
    def policy_service(self) -> PolicyMemoryService:
        """Return the configured policy service."""

        return self._policy_service

    @property
    def memory_service(self) -> MemoryService:
        """Return the underlying memory service."""

        return self.policy_service.memory_service

    @property
    def deduplicator(self) -> MemoryDeduplicator:
        """Return the configured deduplicator."""

        return self._deduplicator

    def evaluate_duplicate(
        self,
        request: MemoryCreate,
    ) -> MemoryDeduplicationResult:
        """Evaluate duplication without changing stored data."""

        now = self.memory_service.clock_now()

        return self.deduplicator.evaluate(
            request=request,
            now=now,
        )

    def create(
        self,
        request: MemoryCreate,
        *,
        user_approved: bool = False,
    ) -> MemoryRecord:
        """Create, keep, or update a memory candidate."""

        self.policy_service.ensure_allowed(
            request,
            user_approved=user_approved,
        )

        result = self.evaluate_duplicate(request)

        if (
            result.action
            is MemoryDeduplicationAction.CREATE
        ):
            return self.memory_service.create(request)

        existing = result.matched_memory

        if existing is None:
            raise RuntimeError(
                "duplicate result is missing matched memory"
            )

        if (
            result.action
            is MemoryDeduplicationAction.KEEP_EXISTING
        ):
            return existing

        merged_tags = sorted(
            set(existing.tags) | set(request.tags)
        )
        merged_metadata = {
            **existing.metadata,
            **request.metadata,
        }

        return self.memory_service.update(
            memory_id=existing.memory_id,
            update=MemoryUpdate(
                tags=merged_tags,
                importance=max(
                    existing.importance,
                    request.importance,
                ),
                confidence=max(
                    existing.confidence,
                    request.confidence,
                ),
                expires_at=(
                    request.expires_at
                    if request.expires_at is not None
                    else existing.expires_at
                ),
                metadata=merged_metadata,
            ),
        )
