"""Schemas for deterministic research task decomposition."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.research_request import ResearchRequest
from app.schemas.research_request_validation import (
    ResearchRequestValidationResult,
)
from app.schemas.research_task import ResearchTaskGraph


class ResearchTaskDecompositionResult(BaseModel):
    """Result of decomposing one research request."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request: ResearchRequest
    validation: ResearchRequestValidationResult
    task_graph: ResearchTaskGraph

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate request and graph consistency."""

        request_ids = {
            self.request.request_id,
            self.validation.request_id,
            self.task_graph.request_id,
        }

        if request_ids != {self.request.request_id}:
            raise ValueError(
                "all decomposition request IDs must match"
            )

        if not self.validation.valid:
            raise ValueError(
                "decomposition requires a valid "
                "research request"
            )

        return self
