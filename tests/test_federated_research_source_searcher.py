from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.research.federated_research_source_searcher import (
    FederatedResearchSourceSearcher,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_search_budget import ResearchSearchUsage
from app.schemas.research_search_query import (
    ResearchSearchQuery,
    ResearchSearchQuerySet,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateSet,
)
from app.schemas.research_task import ResearchTask, ResearchTaskGraph


def make_query_set(
    *,
    request_id: str = "request-001",
    query_text: str = "AIRA web local evidence",
) -> ResearchSearchQuerySet:
    task = ResearchTask(
        task_id=f"{request_id}-task",
        request_id=request_id,
        title="Integrated research",
        question="How does AIRA combine web and local evidence?",
        objective="Explain integrated evidence.",
        completion_criteria=["Use both source universes."],
        expected_output="Grounded claims.",
    )
    graph = ResearchTaskGraph(request_id=request_id, tasks=[task])
    return ResearchSearchQuerySet(
        request_id=request_id,
        task_graph=graph,
        queries=[
            ResearchSearchQuery(
                query_id=f"{request_id}-query",
                request_id=request_id,
                task_id=task.task_id,
                query_text=query_text,
                maximum_results=4,
            )
        ],
    )


def make_candidate(
    query_set: ResearchSearchQuerySet,
    *,
    source_id: str,
    url: str,
    rank: int,
    origin: str,
    query_index: int = 0,
) -> ResearchSourceCandidate:
    query = query_set.queries[query_index]
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id=query.request_id,
        task_id=query.task_id,
        query_id=query.query_id,
        title=source_id,
        url=url,
        source_type=ResearchSourceType.OTHER,
        snippet="Integrated Web and Local evidence.",
        rank=rank,
        metadata={"research_origin": origin},
    )


@dataclass
class StaticSetSearcher:
    result: ResearchSourceCandidateSet
    search_usage: ResearchSearchUsage = field(
        default_factory=ResearchSearchUsage
    )
    search_budget: object | None = None

    def search(self, query_set: ResearchSearchQuerySet) -> ResearchSourceCandidateSet:
        return self.result


def make_result(
    query_set: ResearchSearchQuerySet,
    candidates: list[ResearchSourceCandidate],
) -> ResearchSourceCandidateSet:
    return ResearchSourceCandidateSet(
        request_id=query_set.request_id,
        query_set=query_set,
        candidates=candidates,
    )


def federate(
    query_set: ResearchSearchQuerySet,
    web: list[ResearchSourceCandidate],
    local: list[ResearchSourceCandidate],
) -> FederatedResearchSourceSearcher:
    return FederatedResearchSourceSearcher(
        web_searcher=StaticSetSearcher(make_result(query_set, web)),
        local_searcher=StaticSetSearcher(make_result(query_set, local)),
    )


def test_merges_with_unique_rewritten_ranks_and_interleaving() -> None:
    queries = make_query_set()
    web = [
        make_candidate(
            queries,
            source_id=f"web-{rank}",
            url=f"https://example.com/web-{rank}",
            rank=rank,
            origin="web",
        )
        for rank in (1, 2)
    ]
    local = [
        make_candidate(
            queries,
            source_id=f"local-{rank}",
            url=f"https://local.aira.invalid/source/local-{rank}",
            rank=rank,
            origin="local",
        )
        for rank in (1, 2)
    ]

    result = federate(queries, web, local).search(queries)

    assert [item.source_id for item in result.candidates] == [
        "web-1",
        "local-1",
        "web-2",
        "local-2",
    ]
    assert [item.rank for item in result.candidates] == [1, 2, 3, 4]


@pytest.mark.parametrize("side", ["web", "local"])
def test_supports_one_sided_and_empty_child_results(side: str) -> None:
    queries = make_query_set()
    candidate = make_candidate(
        queries,
        source_id=side,
        url=f"https://example.com/{side}",
        rank=1,
        origin=side,
    )
    web = [candidate] if side == "web" else []
    local = [candidate] if side == "local" else []

    result = federate(queries, web, local).search(queries)

    assert result.candidates == [candidate]


def test_both_empty_children_produce_empty_set() -> None:
    queries = make_query_set()
    assert federate(queries, [], []).search(queries).candidates == []


@pytest.mark.parametrize("collision", ["source_id", "url"])
def test_first_interleaved_candidate_wins_collision(collision: str) -> None:
    queries = make_query_set()
    web = make_candidate(
        queries,
        source_id="shared" if collision == "source_id" else "web",
        url="https://example.com/shared",
        rank=1,
        origin="web",
    )
    local = make_candidate(
        queries,
        source_id="shared" if collision == "source_id" else "local",
        url=(
            "https://example.com/shared/"
            if collision == "url"
            else "https://local.aira.invalid/source/shared"
        ),
        rank=1,
        origin="local",
    )

    result = federate(queries, [web], [local]).search(queries)

    assert result.candidates == [web]


@pytest.mark.parametrize("mismatch", ["request", "query"])
def test_rejects_child_request_or_query_set_mismatch(mismatch: str) -> None:
    queries = make_query_set()
    other = make_query_set(
        request_id="other" if mismatch == "request" else "request-001",
        query_text="different query",
    )
    searcher = FederatedResearchSourceSearcher(
        web_searcher=StaticSetSearcher(make_result(other, [])),
        local_searcher=StaticSetSearcher(make_result(queries, [])),
    )

    with pytest.raises(ValueError, match="does not match"):
        searcher.search(queries)


def test_rank_and_url_deduplication_are_scoped_per_query() -> None:
    queries = make_query_set()
    first = queries.queries[0]
    second = first.model_copy(
        update={
            "query_id": "request-001-query-002",
            "query_text": "second integrated query",
        }
    )
    queries = queries.model_copy(update={"queries": [first, second]})
    shared_url = "https://example.com/shared"
    web = [
        make_candidate(
            queries,
            source_id=f"web-query-{index}",
            url=shared_url,
            rank=1,
            origin="web",
            query_index=index,
        )
        for index in (0, 1)
    ]
    local = [
        *[
            make_candidate(
                queries,
                source_id=f"local-collision-{index}",
                url=shared_url,
                rank=1,
                origin="local",
                query_index=index,
            )
            for index in (0, 1)
        ],
        *[
            make_candidate(
                queries,
                source_id=f"local-unique-{index}",
                url="https://example.com/unique",
                rank=2,
                origin="local",
                query_index=index,
            )
            for index in (0, 1)
        ],
    ]

    result = federate(queries, web, local).search(queries)

    assert [item.source_id for item in result.candidates] == [
        "web-query-0",
        "local-unique-0",
        "web-query-1",
        "local-unique-1",
    ]
    assert [
        [item.rank for item in result.candidates_for_query(query.query_id)]
        for query in queries.ordered_queries()
    ] == [[1, 2], [1, 2]]


def test_exposes_only_web_provider_usage() -> None:
    queries = make_query_set()
    web_usage = ResearchSearchUsage(
        provider_call_count=2,
        credit_used=1.5,
        latency_used_ms=30,
    )
    searcher = FederatedResearchSourceSearcher(
        web_searcher=StaticSetSearcher(make_result(queries, []), web_usage),
        local_searcher=StaticSetSearcher(
            make_result(queries, []),
            ResearchSearchUsage(provider_call_count=99, credit_used=99.0),
        ),
    )

    assert searcher.search_usage is web_usage
