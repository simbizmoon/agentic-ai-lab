"""AIRA-native research-planning benchmark dataset and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
    ResearchSearchQueryType,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


class ResearchTaskGraphDraft(BaseModel):
    """Model-generated tasks before graph-level validation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tasks: list[ResearchTask] = Field(min_length=1)


class ResearchQuerySetDraft(BaseModel):
    """Model-generated queries before query-set validation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    queries: list[ResearchSearchQuery] = Field(min_length=1)


@dataclass(frozen=True)
class ResearchPlanningCase:
    """One fixed AIRA-native research-planning case."""

    case_id: str
    request: ResearchRequest


@dataclass(frozen=True)
class ResearchPlanningScore:
    """Deterministic structural and semantic benchmark score."""

    schema_passed: bool
    graph_or_query_set_passed: bool
    checks_passed: int
    checks_total: int
    passed: bool
    failures: tuple[str, ...]


def research_planning_cases() -> tuple[ResearchPlanningCase, ...]:
    """Return fixed research-planning requests."""
    return (
        ResearchPlanningCase(
            case_id="memory-001",
            request=ResearchRequest(
                request_id="local-plan-memory-001",
                question=(
                    "How do working memory and episodic memory "
                    "architectures differ in AI agents?"
                ),
                objective=(
                    "Compare the two memory patterns and identify "
                    "their engineering trade-offs."
                ),
                include_topics=[
                    "working memory",
                    "episodic memory",
                ],
                preferred_source_types=[
                    ResearchSourceType.PRIMARY_RESEARCH,
                    ResearchSourceType.OFFICIAL_DOCUMENTATION,
                ],
                maximum_sources=12,
            ),
        ),
        ResearchPlanningCase(
            case_id="seat-001",
            request=ResearchRequest(
                request_id="local-plan-seat-001",
                question=(
                    "착석 상태 기반 행동관리 시스템의 기술적 선행기술을 "
                    "어떻게 조사해야 하는가?"
                ),
                objective=(
                    "착석 감지와 행동관리 자동화의 선행기술을 분리하여 "
                    "신뢰할 수 있는 근거를 수집한다."
                ),
                include_topics=[
                    "착석 감지",
                    "행동관리 자동화",
                ],
                preferred_source_types=[
                    ResearchSourceType.PRIMARY_RESEARCH,
                    ResearchSourceType.OFFICIAL_DOCUMENTATION,
                ],
                maximum_sources=12,
            ),
        ),
        ResearchPlanningCase(
            case_id="rag-agent-001",
            request=ResearchRequest(
                request_id="local-plan-rag-agent-001",
                question=(
                    "How should RAG retrieval and agentic web research "
                    "be compared for an AI research system?"
                ),
                objective=(
                    "Compare retrieval quality, source grounding, "
                    "latency, and operational trade-offs."
                ),
                include_topics=[
                    "RAG retrieval",
                    "agentic web research",
                ],
                preferred_source_types=[
                    ResearchSourceType.PRIMARY_RESEARCH,
                    ResearchSourceType.OFFICIAL_DOCUMENTATION,
                ],
                maximum_sources=12,
            ),
        ),
    )


def task_planning_prompt(case: ResearchPlanningCase) -> str:
    """Build a bounded task-decomposition prompt."""
    request = case.request
    topics = "\n".join(
        f"- {topic}" for topic in request.include_topics
    )
    return (
        "너는 AIRA research task planner다.\n"
        "아래 research request를 실행 가능한 task graph로 분해하라.\n\n"
        f"request_id: {request.request_id}\n"
        f"question: {request.question}\n"
        f"objective: {request.objective}\n"
        f"include_topics:\n{topics}\n\n"
        "규칙:\n"
        "- include_topics 각각에 대해 검색이 필요한 topic task를 정확히 하나 만든다.\n"
        "- topic task metadata에는 task_type='topic_research'와 "
        "topic=<해당 include topic>을 넣는다.\n"
        "- topic task는 requires_search=true이고 서로 의존하지 않는다.\n"
        "- topic이 둘 이상이면 마지막에 synthesis task를 정확히 하나 만든다.\n"
        "- synthesis task는 requires_search=false이고 모든 topic task에 의존한다.\n"
        "- synthesis task metadata task_type은 'synthesis'다.\n"
        "- 모든 task request_id는 위 request_id와 동일해야 한다.\n"
        "- 모든 task의 completion_criteria는 비어 있지 않아야 한다.\n"
        "- status는 planned를 사용한다.\n"
        "- JSON Schema에 맞는 결과만 반환한다."
    )


def query_planning_prompt(
    case: ResearchPlanningCase,
    graph: ResearchTaskGraph,
) -> str:
    """Build a bounded search-query planning prompt."""
    request = case.request
    task_lines = []
    for task in graph.tasks:
        task_lines.append(
            f"- task_id={task.task_id}; "
            f"requires_search={task.requires_search}; "
            f"topic={task.metadata.get('topic', '')}; "
            f"question={task.question}"
        )

    source_types = ", ".join(
        source_type.value
        for source_type in request.preferred_source_types
    )
    return (
        "너는 AIRA research search-query planner다.\n"
        "아래 validated task graph에 검색 query를 할당하라.\n\n"
        f"request_id: {request.request_id}\n"
        f"preferred_source_types: {source_types}\n"
        f"maximum_sources: {request.maximum_sources}\n"
        "tasks:\n"
        + "\n".join(task_lines)
        + "\n\n규칙:\n"
        "- requires_search=true인 각 task에 query를 만든다.\n"
        "- requires_search=false인 synthesis task에는 query를 만들지 않는다.\n"
        "- 각 검색 task에 focused query를 정확히 하나 포함한다.\n"
        "- preferred source에 primary_research가 있으므로 "
        "primary_source query를 정확히 하나 포함한다.\n"
        "- preferred source에 official_documentation이 있으므로 "
        "official query를 정확히 하나 포함한다.\n"
        "- 각 query의 request_id와 task_id를 정확히 연결한다.\n"
        "- 같은 task 안에서 query_text를 중복하지 않는다.\n"
        "- priority는 high(30)를 사용한다.\n"
        "- preferred_source_types는 request의 두 source type을 포함한다.\n"
        "- maximum_results는 6으로 한다.\n"
        "- metadata planner='local-llm'을 넣는다.\n"
        "- JSON Schema에 맞는 결과만 반환한다."
    )


def task_draft_schema() -> dict[str, Any]:
    """Return JSON Schema for model-generated research tasks."""
    return ResearchTaskGraphDraft.model_json_schema()


def query_draft_schema() -> dict[str, Any]:
    """Return JSON Schema for model-generated search queries."""
    return ResearchQuerySetDraft.model_json_schema()


def validate_task_draft(
    *,
    case: ResearchPlanningCase,
    response: str,
) -> tuple[ResearchTaskGraph | None, ResearchPlanningScore]:
    """Validate one model-generated task graph."""
    failures: list[str] = []
    try:
        draft = ResearchTaskGraphDraft.model_validate_json(response)
    except ValidationError as error:
        return None, ResearchPlanningScore(
            schema_passed=False,
            graph_or_query_set_passed=False,
            checks_passed=0,
            checks_total=6,
            passed=False,
            failures=(f"schema_validation_failed:{error.errors()[0]['type']}",),
        )

    try:
        graph = ResearchTaskGraph(
            request_id=case.request.request_id,
            tasks=draft.tasks,
        )
    except ValidationError as error:
        return None, ResearchPlanningScore(
            schema_passed=True,
            graph_or_query_set_passed=False,
            checks_passed=1,
            checks_total=6,
            passed=False,
            failures=(f"graph_validation_failed:{error.errors()[0]['type']}",),
        )

    topic_tasks = [
        task
        for task in graph.tasks
        if task.metadata.get("task_type") == "topic_research"
    ]
    synthesis_tasks = [
        task
        for task in graph.tasks
        if task.metadata.get("task_type") == "synthesis"
    ]

    checks: list[tuple[str, bool]] = [
        (
            "topic_count",
            len(topic_tasks) == len(case.request.include_topics),
        ),
        (
            "topic_coverage",
            [task.metadata.get("topic") for task in topic_tasks]
            == list(case.request.include_topics),
        ),
        (
            "topic_searchable",
            all(task.requires_search for task in topic_tasks),
        ),
        (
            "single_synthesis",
            len(synthesis_tasks) == 1,
        ),
        (
            "synthesis_not_searchable",
            len(synthesis_tasks) == 1
            and not synthesis_tasks[0].requires_search,
        ),
        (
            "synthesis_dependencies",
            len(synthesis_tasks) == 1
            and set(synthesis_tasks[0].depends_on)
            == {task.task_id for task in topic_tasks},
        ),
    ]

    for name, ok in checks:
        if not ok:
            failures.append(name)

    passed_count = sum(ok for _, ok in checks)
    return graph, ResearchPlanningScore(
        schema_passed=True,
        graph_or_query_set_passed=True,
        checks_passed=passed_count,
        checks_total=len(checks),
        passed=passed_count == len(checks),
        failures=tuple(failures),
    )


def validate_query_draft(
    *,
    case: ResearchPlanningCase,
    graph: ResearchTaskGraph,
    response: str,
) -> ResearchPlanningScore:
    """Validate model-generated search queries against AIRA schemas."""
    try:
        draft = ResearchQuerySetDraft.model_validate_json(response)
    except ValidationError as error:
        return ResearchPlanningScore(
            schema_passed=False,
            graph_or_query_set_passed=False,
            checks_passed=0,
            checks_total=6,
            passed=False,
            failures=(f"schema_validation_failed:{error.errors()[0]['type']}",),
        )

    try:
        query_set = ResearchSearchQuerySet(
            request_id=case.request.request_id,
            task_graph=graph,
            queries=draft.queries,
        )
    except ValidationError as error:
        return ResearchPlanningScore(
            schema_passed=True,
            graph_or_query_set_passed=False,
            checks_passed=1,
            checks_total=6,
            passed=False,
            failures=(f"query_set_validation_failed:{error.errors()[0]['type']}",),
        )

    failures: list[str] = []
    searchable_tasks = [
        task for task in graph.tasks if task.requires_search
    ]
    synthesis_ids = {
        task.task_id for task in graph.tasks if not task.requires_search
    }

    per_task_types = {
        task.task_id: {
            query.query_type
            for query in query_set.queries_for_task(task.task_id)
        }
        for task in searchable_tasks
    }

    checks: list[tuple[str, bool]] = [
        (
            "all_search_tasks_covered",
            all(query_set.queries_for_task(task.task_id) for task in searchable_tasks),
        ),
        (
            "focused_per_task",
            all(
                ResearchSearchQueryType.FOCUSED in per_task_types[task.task_id]
                for task in searchable_tasks
            ),
        ),
        (
            "official_per_task",
            all(
                ResearchSearchQueryType.OFFICIAL in per_task_types[task.task_id]
                for task in searchable_tasks
            ),
        ),
        (
            "primary_per_task",
            all(
                ResearchSearchQueryType.PRIMARY_SOURCE
                in per_task_types[task.task_id]
                for task in searchable_tasks
            ),
        ),
        (
            "no_synthesis_queries",
            all(query.task_id not in synthesis_ids for query in query_set.queries),
        ),
        (
            "source_types_preserved",
            all(
                set(case.request.preferred_source_types).issubset(
                    set(query.preferred_source_types)
                )
                for query in query_set.queries
            ),
        ),
    ]

    for name, ok in checks:
        if not ok:
            failures.append(name)

    passed_count = sum(ok for _, ok in checks)
    return ResearchPlanningScore(
        schema_passed=True,
        graph_or_query_set_passed=True,
        checks_passed=passed_count,
        checks_total=len(checks),
        passed=passed_count == len(checks),
        failures=tuple(failures),
    )
