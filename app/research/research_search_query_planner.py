"""Deterministic search query planning for research tasks."""

from __future__ import annotations

from app.research.research_search_query_planning_error import (
    ResearchSearchQueryPlanningError,
)
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
from app.schemas.research_search_query_planning import (
    ResearchSearchQueryPlanningResult,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


class ResearchSearchQueryPlanner:
    """Create deterministic queries for searchable tasks."""

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
    ) -> ResearchSearchQueryPlanningResult:
        """Create a validated query set."""

        if request.request_id != task_graph.request_id:
            raise ResearchSearchQueryPlanningError(
                "request_id must match task graph request_id"
            )

        searchable_tasks = [
            task
            for task in task_graph.tasks
            if task.requires_search
        ]

        if not searchable_tasks:
            raise ResearchSearchQueryPlanningError(
                "task graph must contain at least one "
                "searchable task"
            )

        maximum_results = max(
            1,
            request.maximum_sources
            // len(searchable_tasks),
        )

        queries: list[ResearchSearchQuery] = []
        query_position = 1

        for task in searchable_tasks:
            task_queries = self._queries_for_task(
                request=request,
                task=task,
                start_position=query_position,
                maximum_results=maximum_results,
            )
            queries.extend(task_queries)
            query_position += len(task_queries)

        return ResearchSearchQueryPlanningResult(
            request=request,
            task_graph=task_graph,
            query_set=ResearchSearchQuerySet(
                request_id=request.request_id,
                task_graph=task_graph,
                queries=queries,
            ),
        )

    def _queries_for_task(
        self,
        *,
        request: ResearchRequest,
        task: ResearchTask,
        start_position: int,
        maximum_results: int,
    ) -> list[ResearchSearchQuery]:
        """Build deterministic queries for one task."""

        query_specs: list[
            tuple[
                ResearchSearchQueryType,
                ResearchSearchQueryPriority,
                str,
                bool,
            ]
        ] = [
            (
                ResearchSearchQueryType.FOCUSED,
                ResearchSearchQueryPriority.HIGH,
                self._focused_query_text(task),
                False,
            )
        ]

        preferred_types = set(
            request.preferred_source_types
        )

        if (
            ResearchSourceType.OFFICIAL_DOCUMENTATION
            in preferred_types
            or ResearchSourceType.GOVERNMENT
            in preferred_types
        ):
            query_specs.append(
                (
                    ResearchSearchQueryType.OFFICIAL,
                    ResearchSearchQueryPriority.HIGH,
                    self._official_query_text(task),
                    False,
                )
            )

        if (
            ResearchSourceType.PRIMARY_RESEARCH
            in preferred_types
            or ResearchSourceType.ACADEMIC
            in preferred_types
        ):
            query_specs.append(
                (
                    ResearchSearchQueryType.PRIMARY_SOURCE,
                    ResearchSearchQueryPriority.HIGH,
                    self._primary_source_query_text(task),
                    False,
                )
            )

        return [
            ResearchSearchQuery(
                query_id=self._query_id(
                    request_id=request.request_id,
                    position=start_position + offset,
                ),
                request_id=request.request_id,
                task_id=task.task_id,
                query_text=query_text,
                query_type=query_type,
                priority=priority,
                preferred_source_types=list(
                    request.preferred_source_types
                ),
                start_date=request.start_date,
                end_date=request.end_date,
                maximum_results=maximum_results,
                exact_phrase=exact_phrase,
                metadata={
                    "planner": "deterministic",
                    "task_type": task.metadata.get(
                        "task_type",
                        "unspecified",
                    ),
                },
            )
            for offset, (
                query_type,
                priority,
                query_text,
                exact_phrase,
            ) in enumerate(query_specs)
        ]

    @staticmethod
    def _focused_query_text(
        task: ResearchTask,
    ) -> str:
        """Create the main focused query."""

        topic = task.metadata.get("topic")

        if topic:
            return (
                f"{topic.strip()} "
                f"{task.question.strip()}"
            )

        return task.question.strip()

    @staticmethod
    def _official_query_text(
        task: ResearchTask,
    ) -> str:
        """Create a query favoring official sources."""

        topic = task.metadata.get(
            "topic",
            task.title,
        )

        return (
            f"{topic.strip()} official documentation"
        )

    @staticmethod
    def _primary_source_query_text(
        task: ResearchTask,
    ) -> str:
        """Create a query favoring primary research."""

        topic = task.metadata.get(
            "topic",
            task.title,
        )

        return (
            f"{topic.strip()} primary research paper"
        )

    @staticmethod
    def _query_id(
        *,
        request_id: str,
        position: int,
    ) -> str:
        """Return one deterministic query identifier."""

        return (
            f"{request_id.strip()}-query-"
            f"{position:03d}"
        )
