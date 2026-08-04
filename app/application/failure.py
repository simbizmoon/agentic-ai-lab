"""Standard application failure schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


class ApplicationFailureCategory(StrEnum):
    """High-level category of an application failure."""

    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PERMISSION = "permission"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class ApplicationFailureDetail(BaseModel):
    """One structured failure detail."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    location: str
    code: str
    message: str
    context: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_detail(self) -> Self:
        """Validate detail text fields."""

        for field_name, value in {
            "location": self.location,
            "code": self.code,
            "message": self.message,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ApplicationFailure(BaseModel):
    """Normalized application failure exposed to upper layers."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    category: ApplicationFailureCategory
    code: str
    message: str
    retryable: bool
    status_code: int = Field(ge=400, le=599)

    details: list[ApplicationFailureDetail] = Field(
        default_factory=list
    )

    internal_message: str | None = None
    exception_type: str
    execution_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate normalized failure invariants."""

        required_text = {
            "code": self.code,
            "message": self.message,
            "exception_type": self.exception_type,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        for field_name, value in {
            "internal_message": self.internal_message,
            "execution_id": self.execution_id,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        normalized_locations = [
            detail.location.strip().casefold()
            for detail in self.details
        ]

        if len(set(normalized_locations)) != len(
            normalized_locations
        ):
            raise ValueError(
                "failure details must have unique locations"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self
