"""Application reliability query schema."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)


class ApplicationReliabilityQuery(BaseModel):
    """Filter used to build a reliability snapshot."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str | None = None
    workspace_id: str | None = None

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Validate optional reliability filters."""

        for field_name, value in {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        return self
