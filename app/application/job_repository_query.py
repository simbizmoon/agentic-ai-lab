"""Query schemas for background job repositories."""

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

from app.application.job_record import (
    ApplicationJobPriority,
    ApplicationJobRecord,
    ApplicationJobStatus,
    ApplicationJobType,
)


class ApplicationJobSortField(StrEnum):
    """Field used to sort background jobs."""

    CREATED_AT = "created_at"
    AVAILABLE_AT = "available_at"
    PRIORITY = "priority"
    ATTEMPT_NUMBER = "attempt_number"
    RECORD_VERSION = "record_version"


class ApplicationJobSortDirection(StrEnum):
    """Direction used to sort background jobs."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class ApplicationJobQuery(BaseModel):
    """Filtering and pagination query for background jobs."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    job_ids: list[str] = Field(default_factory=list)
    root_job_id: str | None = None
    parent_job_id: str | None = None
    previous_attempt_job_id: str | None = None

    request_id: str | None = None
    workspace_id: str | None = None
    execution_id: str | None = None

    job_types: list[ApplicationJobType] = Field(
        default_factory=list
    )
    queue_names: list[str] = Field(default_factory=list)
    priorities: list[ApplicationJobPriority] = Field(
        default_factory=list
    )
    statuses: list[ApplicationJobStatus] = Field(
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

    available_from: datetime | None = None
    available_to: datetime | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    terminal_only: bool | None = None
    leased_only: bool | None = None

    sort_field: ApplicationJobSortField = (
        ApplicationJobSortField.CREATED_AT
    )
    sort_direction: ApplicationJobSortDirection = (
        ApplicationJobSortDirection.DESCENDING
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate background-job repository filters."""

        self._validate_unique_text(
            self.job_ids,
            field_name="job_ids",
        )
        self._validate_unique_text(
            self.queue_names,
            field_name="queue_names",
        )

        if len(set(self.job_types)) != len(self.job_types):
            raise ValueError(
                "job_types must not contain duplicates"
            )

        if len(set(self.priorities)) != len(self.priorities):
            raise ValueError(
                "priorities must not contain duplicates"
            )

        if len(set(self.statuses)) != len(self.statuses):
            raise ValueError(
                "statuses must not contain duplicates"
            )

        optional_text = {
            "root_job_id": self.root_job_id,
            "parent_job_id": self.parent_job_id,
            "previous_attempt_job_id": (
                self.previous_attempt_job_id
            ),
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "execution_id": self.execution_id,
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

        self._validate_datetime_range(
            start=self.available_from,
            end=self.available_to,
            start_name="available_from",
            end_name="available_to",
        )
        self._validate_datetime_range(
            start=self.created_from,
            end=self.created_to,
            start_name="created_from",
            end_name="created_to",
        )

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank text values."""

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
    def _validate_datetime_range(
        *,
        start: datetime | None,
        end: datetime | None,
        start_name: str,
        end_name: str,
    ) -> None:
        """Validate one optional timezone-aware date range."""

        if start is not None and start.tzinfo is None:
            raise ValueError(
                f"{start_name} must be timezone-aware"
            )

        if end is not None and end.tzinfo is None:
            raise ValueError(
                f"{end_name} must be timezone-aware"
            )

        if start is not None and end is not None and start > end:
            raise ValueError(
                f"{start_name} must not exceed {end_name}"
            )

    @property
    def offset(self) -> int:
        """Return zero-based pagination offset."""

        return (self.page - 1) * self.page_size


class ApplicationJobPage(BaseModel):
    """One paginated collection of background jobs."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[ApplicationJobRecord] = Field(
        default_factory=list
    )
    total_items: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        """Validate job page consistency."""

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
        """Return total available pages."""

        if self.total_items == 0:
            return 0

        return (
            self.total_items + self.page_size - 1
        ) // self.page_size

    @property
    def has_previous_page(self) -> bool:
        """Return whether a previous page exists."""

        return self.page > 1 and self.total_pages > 0

    @property
    def has_next_page(self) -> bool:
        """Return whether another page exists."""

        return self.page < self.total_pages
