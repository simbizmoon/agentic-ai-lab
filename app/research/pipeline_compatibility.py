"""Compatibility adapters for the single research pipeline."""

from __future__ import annotations

from app.research.research_search_query_planner import (
    ResearchSearchQueryPlanner,
)
from app.research.research_task_decomposer import (
    ResearchTaskDecomposer,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuerySet,
)
from app.schemas.research_task import ResearchTaskGraph


class PipelineTaskDecomposerAdapter:
    """Expose only the task graph expected by the pipeline."""

    def __init__(
        self,
        decomposer: ResearchTaskDecomposer | None = None,
    ) -> None:
        self._decomposer = (
            decomposer or ResearchTaskDecomposer()
        )

    @property
    def decomposer(self) -> ResearchTaskDecomposer:
        """Return the wrapped task decomposer."""

        return self._decomposer

    def decompose(
        self,
        request: ResearchRequest,
    ) -> ResearchTaskGraph:
        """Decompose a request and return its task graph."""

        result = self._decomposer.decompose(request)
        return result.task_graph


class PipelineQueryPlannerAdapter:
    """Expose only the query set expected by the pipeline."""

    def __init__(
        self,
        planner: ResearchSearchQueryPlanner | None = None,
    ) -> None:
        self._planner = (
            planner or ResearchSearchQueryPlanner()
        )

    @property
    def planner(self) -> ResearchSearchQueryPlanner:
        """Return the wrapped query planner."""

        return self._planner

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
    ) -> ResearchSearchQuerySet:
        """Plan search queries and return their query set."""

        result = self._planner.plan(
            request=request,
            task_graph=task_graph,
        )
        return result.query_set
