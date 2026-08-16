"""Read-only inventory models for AIRA persistent caches."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CacheKind(StrEnum):
    """Persistent cache universes supported by inventory."""

    EMBEDDING = "embedding"
    PARSED = "parsed"


class CacheEntryInfo(BaseModel):
    """Safe metadata for one validated persistent cache entry."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    filename: str = Field(min_length=1)
    entry_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_filename(self) -> Self:
        if self.filename != f"{self.entry_key}.json":
            raise ValueError("cache entry filename must match entry key")
        return self


class CacheStatus(BaseModel):
    """Observational, non-transactional inventory of one cache directory."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    directory: Path
    directory_exists: bool
    entries: tuple[CacheEntryInfo, ...] = ()
    valid_entry_count: int = Field(ge=0)
    valid_entry_bytes: int = Field(ge=0)
    corrupt_entry_count: int = Field(ge=0)
    corrupt_entry_bytes: int = Field(ge=0)
    lock_file_count: int = Field(ge=0)
    lock_file_bytes: int = Field(ge=0)
    temporary_file_count: int = Field(ge=0)
    temporary_file_bytes: int = Field(ge=0)
    unknown_target_count: int = Field(ge=0)
    unknown_target_bytes: int = Field(ge=0)
    oldest_valid_entry_mtime_ns: int | None = Field(default=None, ge=0)
    newest_valid_entry_mtime_ns: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_aggregates(self) -> Self:
        if len(self.entries) != self.valid_entry_count:
            raise ValueError("valid entry count must match entries")
        if sum(entry.size_bytes for entry in self.entries) != self.valid_entry_bytes:
            raise ValueError("valid entry bytes must match entries")
        if any(entry.cache_kind != self.cache_kind for entry in self.entries):
            raise ValueError("entry cache kind must match status")
        mtimes = [entry.mtime_ns for entry in self.entries]
        expected_oldest = min(mtimes, default=None)
        expected_newest = max(mtimes, default=None)
        if self.oldest_valid_entry_mtime_ns != expected_oldest:
            raise ValueError("oldest valid entry timestamp must match entries")
        if self.newest_valid_entry_mtime_ns != expected_newest:
            raise ValueError("newest valid entry timestamp must match entries")
        if not self.directory_exists and any(
            (
                self.valid_entry_count,
                self.corrupt_entry_count,
                self.lock_file_count,
                self.temporary_file_count,
                self.unknown_target_count,
            )
        ):
            raise ValueError("missing cache directory must have an empty inventory")
        return self


class CachePruneCandidate(BaseModel):
    """One valid final entry selected by a deterministic prune plan."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    filename: str = Field(min_length=1)
    entry_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_filename(self) -> Self:
        if self.filename != f"{self.entry_key}.json":
            raise ValueError("prune candidate filename must match entry key")
        return self


class CachePrunePlan(BaseModel):
    """Immutable dry-run plan derived from one observational cache status.

    A plan is neither deletion authorization nor a guarantee of current filesystem
    state. Execution must lock and revalidate every candidate in a later step.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    directory: Path
    target_entry_bytes_total: int = Field(ge=0)
    observed_valid_entry_count: int = Field(ge=0)
    observed_valid_entry_bytes: int = Field(ge=0)
    selected_entry_count: int = Field(ge=0)
    selected_entry_bytes: int = Field(ge=0)
    expected_remaining_valid_entry_count: int = Field(ge=0)
    expected_remaining_valid_entry_bytes: int = Field(ge=0)
    candidates: tuple[CachePruneCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if len(self.candidates) != self.selected_entry_count:
            raise ValueError("selected entry count must match candidates")
        if sum(candidate.size_bytes for candidate in self.candidates) != (
            self.selected_entry_bytes
        ):
            raise ValueError("selected entry bytes must match candidates")
        if any(
            candidate.cache_kind != self.cache_kind for candidate in self.candidates
        ):
            raise ValueError("candidate cache kind must match plan")
        if list(self.candidates) != sorted(
            self.candidates,
            key=lambda candidate: (candidate.mtime_ns, candidate.entry_key),
        ):
            raise ValueError("prune candidates must use deterministic selection order")
        if self.expected_remaining_valid_entry_count != (
            self.observed_valid_entry_count - self.selected_entry_count
        ):
            raise ValueError("expected remaining entry count is inconsistent")
        if self.expected_remaining_valid_entry_bytes != (
            self.observed_valid_entry_bytes - self.selected_entry_bytes
        ):
            raise ValueError("expected remaining entry bytes are inconsistent")
        if self.observed_valid_entry_bytes <= self.target_entry_bytes_total:
            if self.candidates:
                raise ValueError("entries must not be selected at or below target")
            return self
        if not self.candidates:
            raise ValueError("entries must be selected above target")
        if self.expected_remaining_valid_entry_bytes > self.target_entry_bytes_total:
            raise ValueError("selected entries do not reach target")
        if (
            self.expected_remaining_valid_entry_bytes + self.candidates[-1].size_bytes
            <= self.target_entry_bytes_total
        ):
            raise ValueError("plan selects more entries than required")
        return self


class CachePruneOutcome(StrEnum):
    """Result of revalidating and executing one planned candidate."""

    DELETED = "deleted"
    ALREADY_ABSENT = "already_absent"
    STALE = "stale"
    INVALID = "invalid"


class CachePruneExecutionItem(BaseModel):
    """Observed outcome for one candidate during prune execution."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    filename: str = Field(min_length=1)
    entry_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    planned_size_bytes: int = Field(ge=0)
    outcome: CachePruneOutcome
    deleted_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        if self.filename != f"{self.entry_key}.json":
            raise ValueError("execution item filename must match entry key")
        expected_deleted = (
            self.planned_size_bytes if self.outcome is CachePruneOutcome.DELETED else 0
        )
        if self.deleted_bytes != expected_deleted:
            raise ValueError("deleted bytes must match execution outcome")
        return self


class CachePruneResult(BaseModel):
    """Complete non-transactional result of executing one prune plan."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cache_kind: CacheKind
    directory: Path
    planned_entry_count: int = Field(ge=0)
    planned_entry_bytes: int = Field(ge=0)
    deleted_entry_count: int = Field(ge=0)
    deleted_entry_bytes: int = Field(ge=0)
    skipped_entry_count: int = Field(ge=0)
    items: tuple[CachePruneExecutionItem, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if len(self.items) != self.planned_entry_count:
            raise ValueError("execution items must match planned entry count")
        if sum(item.planned_size_bytes for item in self.items) != (
            self.planned_entry_bytes
        ):
            raise ValueError("planned entry bytes must match execution items")
        if any(item.cache_kind != self.cache_kind for item in self.items):
            raise ValueError("execution item cache kind must match result")
        deleted = [
            item for item in self.items if item.outcome is CachePruneOutcome.DELETED
        ]
        if len(deleted) != self.deleted_entry_count:
            raise ValueError("deleted entry count must match execution items")
        if sum(item.deleted_bytes for item in deleted) != self.deleted_entry_bytes:
            raise ValueError("deleted entry bytes must match execution items")
        if self.skipped_entry_count != self.planned_entry_count - len(deleted):
            raise ValueError("skipped entry count must match execution items")
        return self
