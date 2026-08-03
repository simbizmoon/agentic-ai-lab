"""Schemas returned by structured planner clients."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationResult,
)


class PlannerClientResult(BaseModel):
    """Parsed planner output and deterministic validation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    output: PlanDraftOutput
    validation: PlannerOutputValidationResult
    response_id: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlannerClientResult:
        """Validate optional response metadata."""

        optional_text = {
            "response_id": self.response_id,
            "model": self.model,
        }

        for name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        return self
