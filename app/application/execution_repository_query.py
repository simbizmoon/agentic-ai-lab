"""Query schemas for application execution repositories."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.application.execution_record import (
    ApplicationExecutionStatus,
    ApplicationExecutionSubjectType,
)


class ApplicationExecutionSortField(StrEnum):
    """Field used to order execution repository results."""

    CREATED_AT = "created_at"
    QUEUED_AT = "queued_at"
    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    ATTEMPT_NUMBER = "attempt_number"
    RECORD_VERSION = "record_version"


class ApplicationExecutionSortDirection(StrEnum):
    """Direction used to order execution results."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class ApplicationExecutionQuery(BaseModel):
    """Filtering and pagination query for execution records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_ids: list[str] = Field(default_factory=list)
    root_execution_id: str | None = None
    parent_execution_id: str | None = None
    request_id: str | None = None
    workspace_id: str | None = None
    subject_type: ApplicationExecutionSubjectType | None = None
    subject_id: str | None = None
    statuses: list[ApplicationExecutionStatus] = Field(
        default_factory=list
    )
    minimum_attempt_number: int | None = Field(
        default=None,
        ge=1,
    )
    maximum_attempt_number: int | None = Field(
        default=None,
        ge=1,
    )
    created_from: datetime | None = None
    created_to: datetime | None = None
    terminal_only: bool | None = None
    sort_field: ApplicationExecutionSortField = (
        ApplicationExecutionSortField.CREATED_AT
    )
    sort_direction: ApplicationExecutionSortDirection = (
        ApplicationExecutionSortDirection.DESCENDING
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate execution query filters."""

        self._validate_unique_text(
            self.execution_ids,
            field_name="execution_ids",
        )

        if len(set(self.statuses)) != len(self.statuses):
            raise ValueError(
                "statuses must not contain duplicates"
            )

        optional_text = {
            "root_execution_id": self.root_execution_id,
            "parent_execution_id": self.parent_execution_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "subject_id": self.subject_id,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if (
            self.minimum_attempt_number is not None
            and self.maximum_attempt_number is not None
            and self.minimum_attempt_number
            > self.maximum_attempt_number
        ):
            raise ValueError(
                "minimum_attempt_number must not exceed "
                "maximum_attempt_number"
            )

        for field_name, value in {
            "created_from": self.created_from,
            "created_to": self.created_to,
        }.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError(
                "created_from must not exceed created_to"
            )

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

    @property
    def offset(self) -> int:
        """Return zero-based result offset."""

        return (self.page - 1) * self.page_size


class ApplicationExecutionPage(BaseModel):
    """One paginated collection of execution records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[
        ApplicationExecutionRecord
    ] = Field(default_factory=list)
    total_items: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        """Validate page count consistency."""

        if len(self.items) > self.page_size:
            raise ValueError(
                "page items must not exceed page_size"
            )

        if len(self.items) > self.total_items:
            raise ValueError(
                "page items must not exceed total_items"
            )

        return self

    @property
    def total_pages(self) -> int:
        """Return total number of pages."""

        if self.total_items == 0:
            return 0

        return (
            self.total_items + self.page_size - 1
        ) // self.page_size

    @property
    def has_previous_page(self) -> bool:
        """Return whether an earlier page exists."""

        return self.page > 1 and self.total_pages > 0

    @property
    def has_next_page(self) -> bool:
        """Return whether a later page exists."""

        return self.page < self.total_pages


from app.application.execution_record import (
    ApplicationExecutionRecord,
)

ApplicationExecutionPage.model_rebuild()
