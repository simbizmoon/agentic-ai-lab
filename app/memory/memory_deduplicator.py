"""Deterministic duplicate detection for agent memories."""

from __future__ import annotations

from datetime import datetime

from app.memory.memory_normalizer import (
    normalize_memory_content,
    normalize_memory_tags,
)
from app.memory.memory_store import MemoryStore
from app.schemas.memory_create import MemoryCreate
from app.schemas.memory_deduplication import (
    MemoryDeduplicationAction,
    MemoryDeduplicationReason,
    MemoryDeduplicationResult,
)
from app.schemas.memory_query import MemoryQuery
from app.schemas.memory_record import MemoryRecord


class MemoryDeduplicator:
    """Compare memory candidates with stored records."""

    def __init__(
        self,
        *,
        store: MemoryStore,
    ) -> None:
        self._store = store

    @property
    def store(self) -> MemoryStore:
        """Return the configured memory store."""

        return self._store

    def evaluate(
        self,
        *,
        request: MemoryCreate,
        now: datetime,
    ) -> MemoryDeduplicationResult:
        """Return the appropriate action for one candidate."""

        normalized_content = normalize_memory_content(
            request.content
        )

        candidates = self.store.list(
            query=MemoryQuery(
                kinds=[request.kind],
                scopes=[request.scope],
                sources=[request.source],
                subject_id=request.subject_id,
                project_id=request.project_id,
                session_id=request.session_id,
                include_expired=False,
            ),
            now=now,
        )

        matched = next(
            (
                memory
                for memory in candidates
                if normalize_memory_content(
                    memory.content
                )
                == normalized_content
            ),
            None,
        )

        if matched is None:
            return MemoryDeduplicationResult(
                action=MemoryDeduplicationAction.CREATE,
                reasons=[
                    MemoryDeduplicationReason.NO_DUPLICATE
                ],
                matched_memory=None,
                normalized_content=normalized_content,
            )

        reasons = self._update_reasons(
            request=request,
            existing=matched,
        )

        if not reasons:
            return MemoryDeduplicationResult(
                action=(
                    MemoryDeduplicationAction.KEEP_EXISTING
                ),
                reasons=[
                    MemoryDeduplicationReason.EXACT_DUPLICATE
                ],
                matched_memory=matched,
                normalized_content=normalized_content,
            )

        return MemoryDeduplicationResult(
            action=(
                MemoryDeduplicationAction.UPDATE_EXISTING
            ),
            reasons=reasons,
            matched_memory=matched,
            normalized_content=normalized_content,
        )

    @staticmethod
    def _update_reasons(
        *,
        request: MemoryCreate,
        existing: MemoryRecord,
    ) -> list[MemoryDeduplicationReason]:
        """Return reasons for improving an existing record."""

        reasons: list[MemoryDeduplicationReason] = []

        if request.importance > existing.importance:
            reasons.append(
                MemoryDeduplicationReason
                .IMPORTANCE_INCREASED
            )

        if request.confidence > existing.confidence:
            reasons.append(
                MemoryDeduplicationReason
                .CONFIDENCE_INCREASED
            )

        existing_tags = set(
            normalize_memory_tags(existing.tags)
        )
        request_tags = set(
            normalize_memory_tags(request.tags)
        )

        if not request_tags.issubset(existing_tags):
            reasons.append(
                MemoryDeduplicationReason.TAGS_EXPANDED
            )

        if (
            request.metadata
            and request.metadata != existing.metadata
        ):
            reasons.append(
                MemoryDeduplicationReason.METADATA_CHANGED
            )

        if (
            request.expires_at is not None
            and (
                existing.expires_at is None
                or request.expires_at
                > existing.expires_at
            )
        ):
            reasons.append(
                MemoryDeduplicationReason
                .EXPIRATION_EXTENDED
            )

        return reasons
