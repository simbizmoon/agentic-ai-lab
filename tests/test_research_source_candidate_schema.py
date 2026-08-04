"""Tests for normalized research source candidate schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQueryPriority,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_task import (
    ResearchTask,
    ResearchTaskGraph,
)


def task(
    *,
    task_id: str,
) -> ResearchTask:
    """Return one valid research task."""

    return ResearchTask(
        task_id=task_id,
        request_id="research-001",
        title=f"Investigate {task_id}",
        question=f"What should {task_id} investigate?",
        objective=(
            f"Produce verified findings for {task_id}."
        ),
        completion_criteria=[
            "Produce one supported finding"
        ],
        expected_output="Structured findings.",
    )


def task_graph() -> ResearchTaskGraph:
    """Return one valid research task graph."""

    return ResearchTaskGraph(
        request_id="research-001",
        tasks=[
            task(task_id="task-a"),
            task(task_id="task-b"),
        ],
    )


def query_set() -> ResearchSearchQuerySet:
    """Return one valid query set."""

    graph = task_graph()

    return ResearchSearchQuerySet(
        request_id="research-001",
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id="query-a",
                request_id="research-001",
                task_id="task-a",
                query_text="agent memory architecture",
                priority=(
                    ResearchSearchQueryPriority.HIGH
                ),
            ),
            ResearchSearchQuery(
                query_id="query-b",
                request_id="research-001",
                task_id="task-b",
                query_text="episodic memory agents",
                priority=(
                    ResearchSearchQueryPriority.MEDIUM
                ),
            ),
        ],
    )


def candidate(
    *,
    source_id: str = "source-001",
    query_id: str = "query-a",
    task_id: str = "task-a",
    url: str = "https://example.com/research",
    rank: int = 1,
    **overrides: object,
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    values: dict[str, object] = {
        "source_id": source_id,
        "request_id": "research-001",
        "task_id": task_id,
        "query_id": query_id,
        "title": "Agent memory research",
        "url": url,
        "source_type": (
            ResearchSourceType.PRIMARY_RESEARCH
        ),
        "snippet": (
            "A study of memory architectures in agents."
        ),
        "author": "Example Author",
        "publisher": "Example Publisher",
        "published_at": date(2026, 1, 15),
        "rank": rank,
        "status": (
            ResearchSourceCandidateStatus.DISCOVERED
        ),
        "metadata": {
            "provider": "in-memory",
        },
    }
    values.update(overrides)

    return ResearchSourceCandidate.model_validate(values)


def test_candidate_accepts_valid_values() -> None:
    value = candidate()

    assert value.source_id == "source-001"
    assert value.rank == 1
    assert value.status is (
        ResearchSourceCandidateStatus.DISCOVERED
    )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("source_id", " "),
        ("request_id", ""),
        ("task_id", "\t"),
        ("query_id", "\n"),
        ("title", " "),
        ("url", ""),
    ],
)
def test_candidate_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    values: dict[str, object] = {
        "source_id": "source-001",
        "request_id": "research-001",
        "task_id": "task-a",
        "query_id": "query-a",
        "title": "Agent memory research",
        "url": "https://example.com/research",
        "source_type": (
            ResearchSourceType.PRIMARY_RESEARCH
        ),
        "rank": 1,
    }
    values[field_name] = field_value

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        ResearchSourceCandidate.model_validate(values)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///tmp/source.txt",
        "example.com/research",
    ],
)
def test_candidate_rejects_unsupported_url(
    url: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="url must use http or https",
    ):
        candidate(url=url)


def test_candidate_rejects_url_without_host() -> None:
    with pytest.raises(
        ValidationError,
        match="url must contain a host",
    ):
        candidate(url="https:///research")


def test_candidate_rejects_blank_optional_text() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "author must not be blank when provided"
        ),
    ):
        candidate(author=" ")


def test_candidate_rejects_invalid_rank() -> None:
    with pytest.raises(ValidationError):
        candidate(rank=0)


def test_candidate_normalizes_url() -> None:
    value = candidate(
        url=(
            "HTTPS://Example.COM:443/research/"
            "?page=1#section"
        )
    )

    assert value.normalized_url() == (
        "https://example.com/research?page=1"
    )


def test_candidate_set_accepts_valid_values() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[
            candidate(),
            candidate(
                source_id="source-002",
                query_id="query-b",
                task_id="task-b",
                url="https://example.org/episodic",
            ),
        ],
    )

    assert len(value.candidates) == 2


def test_candidate_set_allows_empty_results() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[],
    )

    assert value.candidates == []


def test_candidate_set_rejects_duplicate_source_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="source IDs must be unique",
    ):
        ResearchSourceCandidateSet(
            request_id="research-001",
            query_set=query_set(),
            candidates=[
                candidate(source_id="source-001"),
                candidate(
                    source_id=" SOURCE-001 ",
                    query_id="query-b",
                    task_id="task-b",
                    url="https://example.org/other",
                ),
            ],
        )


def test_candidate_set_rejects_missing_query() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all candidates must reference "
            "existing queries"
        ),
    ):
        ResearchSourceCandidateSet(
            request_id="research-001",
            query_set=query_set(),
            candidates=[
                candidate(query_id="missing-query")
            ],
        )


def test_candidate_set_rejects_task_query_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate task_id must match "
            "the referenced query task_id"
        ),
    ):
        ResearchSourceCandidateSet(
            request_id="research-001",
            query_set=query_set(),
            candidates=[
                candidate(
                    query_id="query-a",
                    task_id="task-b",
                )
            ],
        )


def test_candidate_set_rejects_duplicate_url_per_query() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidates for the same query must not "
            "contain duplicate URLs"
        ),
    ):
        ResearchSourceCandidateSet(
            request_id="research-001",
            query_set=query_set(),
            candidates=[
                candidate(
                    source_id="source-001",
                    url="https://example.com/research/",
                    rank=1,
                ),
                candidate(
                    source_id="source-002",
                    url="HTTPS://EXAMPLE.COM:443/research",
                    rank=2,
                ),
            ],
        )


def test_candidate_set_allows_same_url_for_different_queries() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[
            candidate(
                source_id="source-001",
                query_id="query-a",
                task_id="task-a",
                rank=1,
            ),
            candidate(
                source_id="source-002",
                query_id="query-b",
                task_id="task-b",
                rank=1,
            ),
        ],
    )

    assert len(value.candidates) == 2


def test_candidate_set_rejects_duplicate_rank_per_query() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "candidate ranks must be unique "
            "within each query"
        ),
    ):
        ResearchSourceCandidateSet(
            request_id="research-001",
            query_set=query_set(),
            candidates=[
                candidate(
                    source_id="source-001",
                    rank=1,
                ),
                candidate(
                    source_id="source-002",
                    url="https://example.org/second",
                    rank=1,
                ),
            ],
        )


def test_candidate_set_orders_by_query_then_rank() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[
            candidate(
                source_id="source-b-2",
                query_id="query-b",
                task_id="task-b",
                url="https://example.org/b2",
                rank=2,
            ),
            candidate(
                source_id="source-a-2",
                query_id="query-a",
                task_id="task-a",
                url="https://example.org/a2",
                rank=2,
            ),
            candidate(
                source_id="source-a-1",
                query_id="query-a",
                task_id="task-a",
                url="https://example.org/a1",
                rank=1,
            ),
            candidate(
                source_id="source-b-1",
                query_id="query-b",
                task_id="task-b",
                url="https://example.org/b1",
                rank=1,
            ),
        ],
    )

    assert [
        item.source_id
        for item in value.ordered_candidates()
    ] == [
        "source-a-1",
        "source-a-2",
        "source-b-1",
        "source-b-2",
    ]


def test_candidate_set_returns_candidates_for_query() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[
            candidate(
                source_id="source-002",
                rank=2,
                url="https://example.org/second",
            ),
            candidate(
                source_id="source-001",
                rank=1,
            ),
        ],
    )

    assert [
        item.source_id
        for item in value.candidates_for_query(
            " QUERY-A "
        )
    ] == [
        "source-001",
        "source-002",
    ]


def test_candidate_set_rejects_blank_query_lookup() -> None:
    value = ResearchSourceCandidateSet(
        request_id="research-001",
        query_set=query_set(),
        candidates=[],
    )

    with pytest.raises(
        ValueError,
        match="query_id must not be blank",
    ):
        value.candidates_for_query(" ")
