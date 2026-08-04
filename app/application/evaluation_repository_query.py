"""Query schemas for evaluation result repositories."""

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

from app.application.evaluation_record import (
    ApplicationEvaluationRecord,
    ApplicationEvaluationStatus,
    ApplicationEvaluationType,
)


class ApplicationEvaluationSortField(StrEnum):
    """Field used to sort evaluation records."""

    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    OVERALL_SCORE = "overall_score"
    RECORD_VERSION = "record_version"


class ApplicationEvaluationSortDirection(StrEnum):
    """Direction used to sort evaluation records."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class ApplicationEvaluationQuery(BaseModel):
    """Filtering and pagination query for evaluations."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_ids: list[str] = Field(default_factory=list)
    evaluation_types: list[
        ApplicationEvaluationType
    ] = Field(default_factory=list)
    statuses: list[
        ApplicationEvaluationStatus
    ] = Field(default_factory=list)

    request_id: str | None = None
    workspace_id: str | None = None
    execution_id: str | None = None
    dataset_id: str | None = None
    case_id: str | None = None
    baseline_evaluation_id: str | None = None

    minimum_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    maximum_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    blocking_only: bool | None = None

    started_from: datetime | None = None
    started_to: datetime | None = None

    sort_field: ApplicationEvaluationSortField = (
        ApplicationEvaluationSortField.FINISHED_AT
    )
    sort_direction: ApplicationEvaluationSortDirection = (
        ApplicationEvaluationSortDirection.DESCENDING
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate evaluation repository filters."""

        self._validate_unique_text(
            self.evaluation_ids,
            field_name="evaluation_ids",
        )

        if len(set(self.evaluation_types)) != len(
            self.evaluation_types
        ):
            raise ValueError(
                "evaluation_types must not contain duplicates"
            )

        if len(set(self.statuses)) != len(self.statuses):
            raise ValueError(
                "statuses must not contain duplicates"
            )

        optional_text = {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "execution_id": self.execution_id,
            "dataset_id": self.dataset_id,
            "case_id": self.case_id,
            "baseline_evaluation_id": (
                self.baseline_evaluation_id
            ),
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if (
            self.minimum_score is not None
            and self.maximum_score is not None
            and self.minimum_score > self.maximum_score
        ):
            raise ValueError(
                "minimum_score must not exceed maximum_score"
            )

        for field_name, value in {
            "started_from": self.started_from,
            "started_to": self.started_to,
        }.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if (
            self.started_from is not None
            and self.started_to is not None
            and self.started_from > self.started_to
        ):
            raise ValueError(
                "started_from must not exceed started_to"
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
        """Return zero-based pagination offset."""

        return (self.page - 1) * self.page_size


class ApplicationEvaluationPage(BaseModel):
    """One paginated collection of evaluation records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[ApplicationEvaluationRecord] = Field(
        default_factory=list
    )
    total_items: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        """Validate page consistency."""

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
        """Return the number of available pages."""

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
        """Return whether a following page exists."""

        return self.page < self.total_pages
