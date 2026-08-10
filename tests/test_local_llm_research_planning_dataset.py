"""Tests for AIRA-native local LLM research-planning benchmark."""

import json

from app.evals.local_llm_research_planning_dataset import (
    ResearchQuerySetDraft,
    ResearchTaskGraphDraft,
    query_draft_schema,
    research_planning_cases,
    task_draft_schema,
    validate_query_draft,
    validate_task_draft,
)
from app.research.research_search_query_planner import (
    ResearchSearchQueryPlanner,
)
from app.research.research_task_decomposer import (
    ResearchTaskDecomposer,
)


def test_cases_are_stable() -> None:
    assert [case.case_id for case in research_planning_cases()] == [
        "memory-001",
        "seat-001",
        "rag-agent-001",
    ]


def test_task_schema_is_strict_object_schema() -> None:
    schema = task_draft_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "tasks" in schema["required"]


def test_query_schema_is_strict_object_schema() -> None:
    schema = query_draft_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "queries" in schema["required"]


def test_deterministic_task_graph_passes_benchmark_validation() -> None:
    case = research_planning_cases()[0]
    graph = ResearchTaskDecomposer().decompose(case.request).task_graph
    response = ResearchTaskGraphDraft(
        tasks=graph.tasks
    ).model_dump_json()

    rebuilt, score = validate_task_draft(
        case=case,
        response=response,
    )

    assert rebuilt is not None
    assert score.passed is True
    assert score.checks_passed == score.checks_total


def test_deterministic_query_plan_passes_benchmark_validation() -> None:
    case = research_planning_cases()[0]
    graph = ResearchTaskDecomposer().decompose(case.request).task_graph
    query_set = ResearchSearchQueryPlanner().plan(
        request=case.request,
        task_graph=graph,
    ).query_set
    response = ResearchQuerySetDraft(
        queries=query_set.queries
    ).model_dump_json()

    score = validate_query_draft(
        case=case,
        graph=graph,
        response=response,
    )

    assert score.passed is True


def test_invalid_task_json_fails_schema() -> None:
    case = research_planning_cases()[0]

    _, score = validate_task_draft(
        case=case,
        response=json.dumps({"tasks": "bad"}),
    )

    assert score.schema_passed is False
    assert score.passed is False


def test_query_for_synthesis_task_fails_semantic_checks() -> None:
    case = research_planning_cases()[0]
    graph = ResearchTaskDecomposer().decompose(case.request).task_graph
    query_set = ResearchSearchQueryPlanner().plan(
        request=case.request,
        task_graph=graph,
    ).query_set
    synthesis = graph.tasks[-1]

    bad_query = query_set.queries[0].model_copy(
        update={"task_id": synthesis.task_id}
    )
    response = ResearchQuerySetDraft(
        queries=[bad_query, *query_set.queries[1:]]
    ).model_dump_json()

    score = validate_query_draft(
        case=case,
        graph=graph,
        response=response,
    )

    assert score.passed is False
