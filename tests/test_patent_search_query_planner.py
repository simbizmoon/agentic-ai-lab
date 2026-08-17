"""Tests for deterministic explicit patent CQL planning."""

import pytest
from pydantic import ValidationError

from app.research.patent_search_query_planner import PatentSearchQueryPlanner
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import PatentSearchQueryPurpose


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="Which patent publications are technically relevant?",
        objective="Identify potentially relevant technical disclosures.",
        maximum_search_results=6,
        maximum_sources=3,
    )


def test_planner_creates_one_primary_candidate() -> None:
    value = request()

    result = PatentSearchQueryPlanner().plan(
        request=value,
        cql_queries=("ab=energy",),
    )

    assert result.request == value
    assert len(result.queries) == 1
    assert result.queries[0].cql_query == "ab=energy"
    assert result.queries[0].purpose is PatentSearchQueryPurpose.PRIMARY


def test_planner_creates_primary_and_alternate_candidates() -> None:
    result = PatentSearchQueryPlanner().plan(
        request=request(),
        cql_queries=(
            'ab="seat occupancy detection"',
            'ab="pressure sensor chair"',
        ),
    )

    assert [item.purpose for item in result.queries] == [
        PatentSearchQueryPurpose.PRIMARY,
        PatentSearchQueryPurpose.ALTERNATE,
    ]


def test_planner_preserves_caller_cql_without_rewriting() -> None:
    cql = 'ab="Seat Occupancy" and pa="Example Corp"'

    result = PatentSearchQueryPlanner().plan(
        request=request(),
        cql_queries=(cql,),
    )

    assert result.queries[0].cql_query == cql


def test_planner_rejects_bare_string_sequence() -> None:
    with pytest.raises(
        TypeError,
        match="must be a sequence of CQL strings",
    ):
        PatentSearchQueryPlanner().plan(
            request=request(),
            cql_queries="ab=energy",
        )


def test_planner_rejects_no_candidates() -> None:
    with pytest.raises(
        ValueError,
        match="at least one patent CQL query is required",
    ):
        PatentSearchQueryPlanner().plan(
            request=request(),
            cql_queries=(),
        )


def test_planner_rejects_more_than_two_candidates() -> None:
    with pytest.raises(
        ValueError,
        match="at most two CQL candidates",
    ):
        PatentSearchQueryPlanner().plan(
            request=request(),
            cql_queries=("ab=one", "ab=two", "ab=three"),
        )


def test_planner_rejects_duplicate_candidates_through_plan_contract() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain exact duplicates",
    ):
        PatentSearchQueryPlanner().plan(
            request=request(),
            cql_queries=("ab=energy", " ab=energy "),
        )


def test_planner_rejects_unsafe_candidate_through_query_contract() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain control characters",
    ):
        PatentSearchQueryPlanner().plan(
            request=request(),
            cql_queries=("ab=energy\npa=example",),
        )


def test_planner_is_deterministic() -> None:
    planner = PatentSearchQueryPlanner()
    value = request()
    candidates = ("ab=energy", "ab=battery")

    first = planner.plan(
        request=value,
        cql_queries=candidates,
    )
    second = planner.plan(
        request=value,
        cql_queries=candidates,
    )

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
