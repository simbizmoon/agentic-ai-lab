"""Bounded user request contract for scholarly evidence acquisition."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.scholarly_provider import ScholarlySearchRequest
from app.schemas.scholarly_work import ScholarlyWorkType


class ScholarlyEvidenceRequest(BaseModel):
    """Describe one explicit, low-cost scholarly evidence command."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    query: str
    maximum_results: int = Field(default=5, ge=1, le=25)
    maximum_provider_requests: Literal[1] = 1
    start_date: date | None = None
    end_date: date | None = None
    work_types: tuple[ScholarlyWorkType, ...] = ()
    require_abstract: bool = False

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must not be after end_date")
        if len(set(self.work_types)) != len(self.work_types):
            raise ValueError("work_types must not contain duplicates")
        return self

    @property
    def planned_maximum_provider_requests(self) -> int:
        """Return the explicit worst-case external provider request count."""

        return self.maximum_provider_requests

    def to_provider_request(self, *, request_id: str) -> ScholarlySearchRequest:
        """Bind a generated execution request ID to the provider-neutral request."""

        if not isinstance(request_id, str):
            raise TypeError("request_id must be a string")
        normalized_request_id = request_id.strip()
        if not normalized_request_id:
            raise ValueError("request_id must not be blank")
        return ScholarlySearchRequest(
            request_id=normalized_request_id,
            query=self.query,
            maximum_results=self.maximum_results,
            maximum_provider_requests=self.maximum_provider_requests,
            start_date=self.start_date,
            end_date=self.end_date,
            work_types=self.work_types,
            require_abstract=self.require_abstract,
        )
