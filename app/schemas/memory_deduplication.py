"""Schemas for deterministic memory deduplication."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.memory_record import MemoryRecord


class MemoryDeduplicationAction(StrEnum):
    """Action selected for a memory candidate."""

    CREATE = "create"
    KEEP_EXISTING = "keep_existing"
    UPDATE_EXISTING = "update_existing"


class MemoryDeduplicationReason(StrEnum):
    """Stable reason codes for duplicate decisions."""

    NO_DUPLICATE = "no_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"
    IMPORTANCE_INCREASED = "importance_increased"
    CONFIDENCE_INCREASED = "confidence_increased"
    TAGS_EXPANDED = "tags_expanded"
    METADATA_CHANGED = "metadata_changed"
    EXPIRATION_EXTENDED = "expiration_extended"


class MemoryDeduplicationResult(BaseModel):
    """Result of comparing a candidate with stored memories."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    action: MemoryDeduplicationAction
    reasons: list[MemoryDeduplicationReason] = Field(
        min_length=1
    )
    matched_memory: MemoryRecord | None = None
    normalized_content: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> MemoryDeduplicationResult:
        """Validate action, reasons, and matched-memory consistency."""

        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError(
                "deduplication reasons must be unique"
            )

        if not self.normalized_content.strip():
            raise ValueError(
                "normalized_content must not be blank"
            )

        if self.action is MemoryDeduplicationAction.CREATE:
            if self.matched_memory is not None:
                raise ValueError(
                    "create action must not include matched_memory"
                )

            if self.reasons != [
                MemoryDeduplicationReason.NO_DUPLICATE
            ]:
                raise ValueError(
                    "create action requires no_duplicate reason"
                )

        else:
            if self.matched_memory is None:
                raise ValueError(
                    "duplicate action requires matched_memory"
                )

            if (
                MemoryDeduplicationReason.NO_DUPLICATE
                in self.reasons
            ):
                raise ValueError(
                    "duplicate action must not use no_duplicate"
                )

        if (
            self.action
            is MemoryDeduplicationAction.KEEP_EXISTING
            and self.reasons
            != [MemoryDeduplicationReason.EXACT_DUPLICATE]
        ):
            raise ValueError(
                "keep_existing requires exact_duplicate reason"
            )

        return self
