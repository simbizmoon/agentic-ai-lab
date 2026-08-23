"""Schemas for bounded scholarly metadata workflow artifacts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scholarly_provider import ScholarlySearchResult


class ScholarlyDuplicateGroup(BaseModel):
    """Exact-identifier duplicate group without choosing a winner."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    group_id: str
    member_work_ids: tuple[str, ...] = Field(min_length=2)
    shared_identity_keys: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_group(self) -> Self:
        if not self.group_id.strip():
            raise ValueError("group_id must not be blank")
        members = [value.strip().casefold() for value in self.member_work_ids]
        if any(not value for value in members):
            raise ValueError("member_work_ids must not contain blank values")
        if len(set(members)) != len(members):
            raise ValueError("member_work_ids must not contain duplicates")
        keys = [value.strip() for value in self.shared_identity_keys]
        if any(not value for value in keys):
            raise ValueError("shared_identity_keys must not contain blank values")
        if len(set(keys)) != len(keys):
            raise ValueError("shared_identity_keys must not contain duplicates")
        if tuple(sorted(keys)) != self.shared_identity_keys:
            raise ValueError("shared_identity_keys must be sorted")
        return self


class ScholarlySearchWorkflowArtifact(BaseModel):
    """Provider result plus deterministic duplicate observations."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    artifact_id: str
    result: ScholarlySearchResult
    duplicate_groups: tuple[ScholarlyDuplicateGroup, ...] = ()
    distinct_identity_group_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        if not self.artifact_id.strip():
            raise ValueError("artifact_id must not be blank")
        work_ids = {work.work_id.strip().casefold() for work in self.result.works}
        grouped_ids: list[str] = []
        for group in self.duplicate_groups:
            for work_id in group.member_work_ids:
                normalized = work_id.strip().casefold()
                if normalized not in work_ids:
                    raise ValueError("duplicate group references unknown work_id")
                grouped_ids.append(normalized)
        if len(set(grouped_ids)) != len(grouped_ids):
            raise ValueError("a work must not appear in multiple duplicate groups")
        expected_count = len(self.result.works) - sum(
            len(group.member_work_ids) - 1 for group in self.duplicate_groups
        )
        if self.distinct_identity_group_count != expected_count:
            raise ValueError("distinct identity group count is inconsistent")
        return self
