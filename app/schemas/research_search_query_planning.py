"""Schemas for deterministic research search query planning."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)
from app.schemas.research_task import ResearchTaskGraph


class ResearchSearchQueryPlanningResult(BaseModel):
    """Result of planning search queries for research tasks."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request: ResearchRequest
    task_graph: ResearchTaskGraph
    query_set: ResearchSearchQuerySet

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate request identity across planning layers."""

        request_ids = {
            self.request.request_id,
            self.task_graph.request_id,
            self.query_set.request_id,
            self.query_set.task_graph.request_id,
        }

        if request_ids != {self.request.request_id}:
            raise ValueError(
                "all search planning request IDs must match"
            )

        if self.query_set.task_graph != self.task_graph:
            raise ValueError(
                "query set task graph must match "
                "the planning task graph"
            )

        return self
