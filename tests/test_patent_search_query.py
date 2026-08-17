"""Tests for bounded patent search-query contracts."""

import pytest
from pydantic import ValidationError

from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import (
    MAXIMUM_PATENT_CQL_LENGTH,
    PatentSearchQuery,
    PatentSearchQueryPlan,
    PatentSearchQueryPurpose,
)


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question="Which patent publications are technically relevant?",
        objective="Identify potentially relevant technical disclosures.",
    )


def query(
    cql_query: str = 'ab="seat occupancy detection"',
    purpose: PatentSearchQueryPurpose = PatentSearchQueryPurpose.PRIMARY,
) -> PatentSearchQuery:
    return PatentSearchQuery(
        cql_query=cql_query,
        purpose=purpose,
    )


def test_query_accepts_explicit_cql() -> None:
    value = query()

    assert value.cql_query == 'ab="seat occupancy detection"'
    assert value.purpose is PatentSearchQueryPurpose.PRIMARY


@pytest.mark.parametrize("value", ["", "   "])
def test_query_rejects_blank_cql(value: str) -> None:
    with pytest.raises(ValidationError, match="cql_query must not be blank"):
        query(value)


@pytest.mark.parametrize(
    "value",
    [
        "ab=energy\npa=example",
        "ab=energy\tpa=example",
        "ab=energy\x00",
        "ab=energy\x7f",
    ],
)
def test_query_rejects_control_characters(value: str) -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain control characters",
    ):
        query(value)


def test_query_rejects_excessive_length() -> None:
    with pytest.raises(ValidationError):
        query("a" * (MAXIMUM_PATENT_CQL_LENGTH + 1))


def test_duplicate_key_only_trims_outer_whitespace() -> None:
    assert query("  ab=Energy  ").duplicate_key() == "ab=Energy"


def test_plan_accepts_one_primary_query() -> None:
    value = PatentSearchQueryPlan(
        request=request(),
        queries=(query(),),
    )

    assert value.queries[0].purpose is PatentSearchQueryPurpose.PRIMARY


def test_plan_accepts_primary_then_alternate() -> None:
    value = PatentSearchQueryPlan(
        request=request(),
        queries=(
            query(),
            query(
                'ab="pressure sensor chair"',
                PatentSearchQueryPurpose.ALTERNATE,
            ),
        ),
    )

    assert [item.purpose for item in value.queries] == [
        PatentSearchQueryPurpose.PRIMARY,
        PatentSearchQueryPurpose.ALTERNATE,
    ]


def test_plan_rejects_alternate_as_first_query() -> None:
    with pytest.raises(
        ValidationError,
        match="first patent search query must be primary",
    ):
        PatentSearchQueryPlan(
            request=request(),
            queries=(
                query(
                    "ab=energy",
                    PatentSearchQueryPurpose.ALTERNATE,
                ),
            ),
        )


def test_plan_rejects_primary_as_second_query() -> None:
    with pytest.raises(
        ValidationError,
        match="second patent search query must be alternate",
    ):
        PatentSearchQueryPlan(
            request=request(),
            queries=(
                query("ab=energy"),
                query("ab=battery"),
            ),
        )


def test_plan_rejects_exact_duplicate_after_outer_trim() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain exact duplicates",
    ):
        PatentSearchQueryPlan(
            request=request(),
            queries=(
                query("ab=energy"),
                query(
                    "  ab=energy  ",
                    PatentSearchQueryPurpose.ALTERNATE,
                ),
            ),
        )


def test_plan_does_not_over_normalize_cql_for_duplicates() -> None:
    value = PatentSearchQueryPlan(
        request=request(),
        queries=(
            query("ab=Energy"),
            query(
                "ab=energy",
                PatentSearchQueryPurpose.ALTERNATE,
            ),
        ),
    )

    assert len(value.queries) == 2


def test_plan_rejects_more_than_two_queries() -> None:
    with pytest.raises(ValidationError):
        PatentSearchQueryPlan(
            request=request(),
            queries=(
                query("ab=one"),
                query(
                    "ab=two",
                    PatentSearchQueryPurpose.ALTERNATE,
                ),
                query(
                    "ab=three",
                    PatentSearchQueryPurpose.ALTERNATE,
                ),
            ),
        )
