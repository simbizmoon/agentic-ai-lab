"""Retention policies and results for archived agent traces."""

from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class AgentTraceRetentionPolicy(BaseModel):
    """Configuration for removing old trace archive files."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    maximum_age_days: int | None = Field(
        default=None,
        ge=1,
    )
    maximum_file_count: int | None = Field(
        default=None,
        ge=1,
    )
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_policy(
        self,
    ) -> AgentTraceRetentionPolicy:
        """Require at least one retention constraint."""

        if (
            self.maximum_age_days is None
            and self.maximum_file_count is None
        ):
            raise ValueError(
                "retention policy must define at least "
                "one constraint"
            )

        return self


class AgentTraceRetentionResult(BaseModel):
    """Result of applying one trace retention policy."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        arbitrary_types_allowed=True,
    )

    output_directory: Path
    scanned_file_count: int = Field(ge=0)
    eligible_file_count: int = Field(ge=0)
    deleted_file_count: int = Field(ge=0)
    retained_file_count: int = Field(ge=0)
    dry_run: bool
    eligible_paths: list[Path] = Field(
        default_factory=list
    )
    deleted_paths: list[Path] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> AgentTraceRetentionResult:
        """Validate retention-result consistency."""

        if not self.output_directory.is_absolute():
            raise ValueError(
                "output_directory must be absolute"
            )

        if self.eligible_file_count != len(
            self.eligible_paths
        ):
            raise ValueError(
                "eligible_file_count is inconsistent"
            )

        if self.deleted_file_count != len(
            self.deleted_paths
        ):
            raise ValueError(
                "deleted_file_count is inconsistent"
            )

        if self.dry_run and self.deleted_paths:
            raise ValueError(
                "dry-run result must not contain deleted paths"
            )

        if (
            self.deleted_file_count
            > self.eligible_file_count
        ):
            raise ValueError(
                "deleted count must not exceed eligible count"
            )

        if (
            self.retained_file_count
            + self.deleted_file_count
            != self.scanned_file_count
        ):
            raise ValueError(
                "retained and deleted counts are inconsistent"
            )

        if len(self.eligible_paths) != len(
            set(self.eligible_paths)
        ):
            raise ValueError(
                "eligible paths must be unique"
            )

        if len(self.deleted_paths) != len(
            set(self.deleted_paths)
        ):
            raise ValueError(
                "deleted paths must be unique"
            )

        for path in (
            self.eligible_paths + self.deleted_paths
        ):
            if not path.is_absolute():
                raise ValueError(
                    "retention paths must be absolute"
                )

        return self
