"""Query schemas for guardrail result repositories."""

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

from app.application.guardrail_record import (
    ApplicationGuardrailDecision,
    ApplicationGuardrailRecord,
    ApplicationGuardrailScope,
)


class ApplicationGuardrailSortField(StrEnum):
    """Field used to sort guardrail records."""

    EVALUATED_AT = "evaluated_at"
    TOTAL_VIOLATIONS = "total_violations"
    BLOCKING_VIOLATIONS = "blocking_violations"
    RECORD_VERSION = "record_version"


class ApplicationGuardrailSortDirection(StrEnum):
    """Direction used to sort guardrail records."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class ApplicationGuardrailQuery(BaseModel):
    """Filtering and pagination query for guardrail results."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    guardrail_evaluation_ids: list[str] = Field(
        default_factory=list
    )
    scopes: list[ApplicationGuardrailScope] = Field(
        default_factory=list
    )
    decisions: list[ApplicationGuardrailDecision] = Field(
        default_factory=list
    )

    request_id: str | None = None
    workspace_id: str | None = None
    execution_id: str | None = None
    assignment_id: str | None = None
    agent_id: str | None = None
    target_id: str | None = None
    target_type: str | None = None

    blocking_only: bool | None = None
    evaluated_from: datetime | None = None
    evaluated_to: datetime | None = None

    sort_field: ApplicationGuardrailSortField = (
        ApplicationGuardrailSortField.EVALUATED_AT
    )
    sort_direction: ApplicationGuardrailSortDirection = (
        ApplicationGuardrailSortDirection.DESCENDING
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate guardrail query filters."""

        self._validate_unique_text(
            self.guardrail_evaluation_ids,
            field_name="guardrail_evaluation_ids",
        )

        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError(
                "scopes must not contain duplicates"
            )

        if len(set(self.decisions)) != len(self.decisions):
            raise ValueError(
                "decisions must not contain duplicates"
            )

        optional_text = {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "execution_id": self.execution_id,
            "assignment_id": self.assignment_id,
            "agent_id": self.agent_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        for field_name, value in {
            "evaluated_from": self.evaluated_from,
            "evaluated_to": self.evaluated_to,
        }.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if (
            self.evaluated_from is not None
            and self.evaluated_to is not None
            and self.evaluated_from > self.evaluated_to
        ):
            raise ValueError(
                "evaluated_from must not exceed evaluated_to"
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


class ApplicationGuardrailPage(BaseModel):
    """One paginated collection of guardrail records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    items: list[ApplicationGuardrailRecord] = Field(
        default_factory=list
    )
    total_items: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_page(self) -> Self:
        """Validate guardrail page consistency."""

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
        """Return total page count."""

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
