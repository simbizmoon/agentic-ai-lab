"""Provider-neutral scholarly metadata request and response contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scholarly_work import ScholarlyWork, ScholarlyWorkType


class ScholarlySearchStatus(StrEnum):
    """Outcome of one bounded provider search."""

    SUCCEEDED = "succeeded"
    NO_RESULTS = "no_results"
    PARTIAL = "partial"
    FAILED = "failed"


class ScholarlySearchRequest(BaseModel):
    """One explicit and bounded scholarly metadata search request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_id: str
    query: str
    maximum_results: int = Field(default=10, ge=1, le=100)
    maximum_provider_requests: int = Field(default=1, ge=1, le=10)
    start_date: date | None = None
    end_date: date | None = None
    work_types: tuple[ScholarlyWorkType, ...] = ()
    require_abstract: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        if not self.query.strip():
            raise ValueError("query must not be blank")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must not be after end_date")
        if len(set(self.work_types)) != len(self.work_types):
            raise ValueError("work_types must not contain duplicates")
        for key, value in self.metadata.items():
            if not key.strip() or not value.strip():
                raise ValueError("metadata keys and values must not be blank")
        return self


class ScholarlyProviderError(BaseModel):
    """Structured provider-level failure."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    error_type: str
    message: str
    retryable: bool = False
    http_status: int | None = Field(default=None, ge=100, le=599)

    @model_validator(mode="after")
    def validate_error(self) -> Self:
        if not self.error_type.strip():
            raise ValueError("error_type must not be blank")
        if not self.message.strip():
            raise ValueError("message must not be blank")
        return self


class ScholarlyRecordFailure(BaseModel):
    """One provider record rejected without hiding a partial result."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider_position: int = Field(ge=1)
    provider_record_id: str | None = None
    error_type: str
    message: str

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        if self.provider_record_id is not None and not self.provider_record_id.strip():
            raise ValueError("provider_record_id must not be blank when provided")
        if not self.error_type.strip():
            raise ValueError("error_type must not be blank")
        if not self.message.strip():
            raise ValueError("message must not be blank")
        return self


class ScholarlyProviderUsage(BaseModel):
    """Observed bounded provider usage for one result."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request_count: int = Field(ge=0)
    records_received: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    records_rejected: int = Field(ge=0)
    duration_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        if self.records_accepted + self.records_rejected != self.records_received:
            raise ValueError(
                "accepted and rejected records must equal records_received"
            )
        return self


class ScholarlySearchResult(BaseModel):
    """Normalized result from one scholarly metadata provider."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: ScholarlySearchRequest
    provider: str
    status: ScholarlySearchStatus
    works: tuple[ScholarlyWork, ...] = ()
    record_failures: tuple[ScholarlyRecordFailure, ...] = ()
    error: ScholarlyProviderError | None = None
    usage: ScholarlyProviderUsage
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if not self.provider.strip():
            raise ValueError("provider must not be blank")
        if self.usage.request_count > self.request.maximum_provider_requests:
            raise ValueError("provider request count exceeds request budget")
        if len(self.works) > self.request.maximum_results:
            raise ValueError("work count exceeds maximum_results")
        if self.usage.records_accepted != len(self.works):
            raise ValueError("records_accepted must equal work count")
        if self.usage.records_rejected != len(self.record_failures):
            raise ValueError("records_rejected must equal record failure count")
        work_ids = [work.work_id.strip().casefold() for work in self.works]
        if len(set(work_ids)) != len(work_ids):
            raise ValueError("work IDs must be unique")
        failure_positions = [item.provider_position for item in self.record_failures]
        if len(set(failure_positions)) != len(failure_positions):
            raise ValueError("record failure positions must be unique")
        expected_provider = self.provider.strip().casefold()
        if any(
            work.provenance.provider.strip().casefold() != expected_provider
            for work in self.works
        ):
            raise ValueError("work provenance provider must match result provider")
        self._validate_status()
        for key, value in self.metadata.items():
            if not key.strip() or not value.strip():
                raise ValueError("metadata keys and values must not be blank")
        return self

    def _validate_status(self) -> None:
        if self.status is ScholarlySearchStatus.SUCCEEDED:
            if not self.works or self.record_failures or self.error is not None:
                raise ValueError("succeeded result requires only accepted works")
        elif self.status is ScholarlySearchStatus.NO_RESULTS:
            if self.works or self.record_failures or self.error is not None:
                raise ValueError("no-results result must be empty without error")
        elif self.status is ScholarlySearchStatus.PARTIAL:
            if not self.works or not self.record_failures or self.error is not None:
                raise ValueError(
                    "partial result requires accepted works and record failures"
                )
        elif self.status is ScholarlySearchStatus.FAILED and (
            self.works or self.record_failures or self.error is None
        ):
            raise ValueError("failed result requires only a provider error")
