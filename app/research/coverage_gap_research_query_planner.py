"""Deterministic query planning for semantic answer-coverage gaps."""

from __future__ import annotations

from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_request import ResearchRequest
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQueryPriority,
    ResearchSearchQuerySet,
    ResearchSearchQueryType,
)
from app.schemas.research_task import ResearchTaskGraph


class CoverageGapResearchQueryPlanner:
    """Create one bounded search query from answer-coverage gaps."""

    def plan(
        self,
        *,
        request: ResearchRequest,
        task_graph: ResearchTaskGraph,
        existing_query_set: ResearchSearchQuerySet,
        coverage_evaluation: ResearchAnswerCoverageEvaluation,
    ) -> ResearchSearchQuerySet:
        """Return one deterministic query targeted at missing answer aspects."""

        if request.request_id != task_graph.request_id:
            raise ValueError(
                "request_id must match task graph request_id"
            )

        if existing_query_set.request_id != request.request_id:
            raise ValueError(
                "existing query set request_id must match request_id"
            )

        if coverage_evaluation.request_id != request.request_id:
            raise ValueError(
                "coverage evaluation request_id must match request_id"
            )

        missing_aspects = [
            aspect.strip()
            for aspect in coverage_evaluation.missing_aspects
            if aspect.strip()
        ]
        if not missing_aspects:
            raise ValueError(
                "coverage evaluation must contain missing aspects"
            )

        source_query = existing_query_set.ordered_queries()[0]

        task_ids = {
            task.task_id.strip().casefold()
            for task in task_graph.tasks
        }
        if source_query.task_id.strip().casefold() not in task_ids:
            raise ValueError(
                "existing query must reference an existing task"
            )

        gap_text = " ".join(missing_aspects[:3])
        query_text = (
            f"{request.question.strip()} {gap_text}"
        )

        existing_texts = {
            query.normalized_query_text()
            for query in existing_query_set.queries
        }
        normalized = " ".join(
            query_text.casefold().split()
        )
        if normalized in existing_texts:
            query_text = (
                f"{query_text} missing details"
            )

        query = ResearchSearchQuery(
            query_id=(
                f"{request.request_id.strip()}-"
                "query-coverage-001"
            ),
            request_id=request.request_id,
            task_id=source_query.task_id,
            query_text=query_text,
            query_type=ResearchSearchQueryType.FOCUSED,
            priority=ResearchSearchQueryPriority.CRITICAL,
            preferred_source_types=list(
                source_query.preferred_source_types
            ),
            start_date=request.start_date,
            end_date=request.end_date,
            maximum_results=min(
                100,
                max(1, request.maximum_sources * 3),
            ),
            exact_phrase=False,
            metadata={
                "planner": "deterministic-coverage-gap",
                "reason": "answer_coverage_gap",
                "coverage_level": (
                    coverage_evaluation.coverage_level.value
                ),
                "replanning_round": "1",
                "missing_aspect_count": str(
                    len(missing_aspects)
                ),
            },
        )

        return ResearchSearchQuerySet(
            request_id=request.request_id,
            task_graph=task_graph,
            queries=[query],
        )
