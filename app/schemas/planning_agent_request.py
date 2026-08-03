"""Request schemas for the integrated planning agent pipeline."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.plan_request import PlanCreationRequest
from app.schemas.plan_run import PlanRunRequest


class PlanningAgentRequest(BaseModel):
    """Input for planning, executing, and evaluating one goal."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    planning: PlanCreationRequest
    execution: PlanRunRequest = Field(
        default_factory=PlanRunRequest
    )
