"""Transport-neutral response generated from application failures."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.application.failure import ApplicationFailure


class ApplicationFailureResponse(BaseModel):
    """Serializable response for a normalized application failure."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    status_code: int = Field(ge=400, le=599)
    body: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        """Require a standard error response body."""

        error = self.body.get("error")

        if not isinstance(error, dict):
            raise TypeError(
                "failure response body requires error object"
            )

        return self

    @classmethod
    def from_failure(
        cls,
        failure: ApplicationFailure,
        *,
        include_internal: bool = False,
    ) -> ApplicationFailureResponse:
        """Create a transport-neutral failure response."""

        error_body: dict[str, JsonValue] = {
            "category": failure.category.value,
            "code": failure.code,
            "message": failure.message,
            "retryable": failure.retryable,
            "details": [
                detail.model_dump(mode="json")
                for detail in failure.details
            ],
        }

        if failure.execution_id is not None:
            error_body["execution_id"] = failure.execution_id

        if include_internal:
            error_body["exception_type"] = (
                failure.exception_type
            )
            error_body["internal_message"] = (
                failure.internal_message
            )
            error_body["metadata"] = failure.metadata

        return cls(
            status_code=failure.status_code,
            body={"error": error_body},
        )
