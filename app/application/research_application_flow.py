"""End-to-end application flow for idempotent research execution."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.application.research_execution import (
    ApplicationResearchExecutionOutput,
    ApplicationResearchExecutionRequest,
    ApplicationResearchExecutionResult,
)


class ApplicationResearchFlowRequest(BaseModel):
    """Request for an idempotent research application flow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    idempotency_key: str
    research: ApplicationResearchExecutionRequest
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate flow request fields."""

        if not self.idempotency_key.strip():
            raise ValueError(
                "idempotency_key must not be blank"
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


class ApplicationResearchFlowStoredResult(BaseModel):
    """JSON-compatible result stored for idempotent reuse."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    output: ApplicationResearchExecutionOutput

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate stored result identity."""

        if not self.execution_id.strip():
            raise ValueError(
                "execution_id must not be blank"
            )

        return self


class ApplicationResearchFlowResult(BaseModel):
    """Successful result returned by the research flow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    idempotency_record_id: str
    reused: bool
    research_result: ApplicationResearchExecutionResult

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate flow result identity."""

        if not self.idempotency_record_id.strip():
            raise ValueError(
                "idempotency_record_id must not be blank"
            )

        return self
