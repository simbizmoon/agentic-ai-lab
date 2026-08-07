"""Deterministic supplemental query planning for evidence gaps."""

from __future__ import annotations

from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQueryPriority,
    ResearchSearchQuerySet,
    ResearchSearchQueryType,
)
from app.schemas.research_task import ResearchTaskGraph


class SupplementalResearchQueryPlanner:
    """Create one bounded query after an evidence-source shortfall."""

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
        initial_query_set: ResearchSearchQuerySet,
    ) -> ResearchSearchQuerySet:
        """Return one deterministic supplemental query."""

        if request.request_id != task_graph.request_id:
            raise ValueError(
                "request_id must match task graph request_id"
            )

        if initial_query_set.request_id != request.request_id:
            raise ValueError(
                "initial query set request_id must match request_id"
            )

        source_query = initial_query_set.ordered_queries()[0]

        task_by_id = {
            task.task_id.strip().casefold(): task
            for task in task_graph.tasks
        }
        task = task_by_id.get(
            source_query.task_id.strip().casefold()
        )

        if task is None:
            raise ValueError(
                "initial query must reference an existing task"
            )

        query_text = (
            f"{task.question.strip()} official guide"
        )

        existing_query_texts = {
            query.normalized_query_text()
            for query in initial_query_set.queries
        }

        if (
            " ".join(query_text.casefold().split())
            in existing_query_texts
        ):
            query_text = (
                f"{task.question.strip()} "
                "official guide concepts"
            )

        preferred_source_types = list(
            source_query.preferred_source_types
        )

        if (
            ResearchSourceType.OFFICIAL_DOCUMENTATION
            not in preferred_source_types
        ):
            preferred_source_types.append(
                ResearchSourceType.OFFICIAL_DOCUMENTATION
            )

        query = ResearchSearchQuery(
            query_id=(
                f"{request.request_id.strip()}-"
                "query-supplemental-001"
            ),
            request_id=request.request_id,
            task_id=source_query.task_id,
            query_text=query_text,
            query_type=ResearchSearchQueryType.OFFICIAL,
            priority=ResearchSearchQueryPriority.HIGH,
            preferred_source_types=preferred_source_types,
            start_date=request.start_date,
            end_date=request.end_date,
            maximum_results=min(
                100,
                max(1, request.maximum_sources * 3),
            ),
            exact_phrase=False,
            metadata={
                "planner": "deterministic-supplemental",
                "reason": "low_source_diversity",
                "replanning_round": "1",
            },
        )

        return ResearchSearchQuerySet(
            request_id=request.request_id,
            task_graph=task_graph,
            queries=[query],
        )
