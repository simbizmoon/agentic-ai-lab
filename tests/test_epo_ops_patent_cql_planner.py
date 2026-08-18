"""Tests for deterministic grounded-concept to EPO OPS CQL planning."""

from datetime import date

import pytest

from app.research.epo_ops_patent_cql_planner import EpoOpsPatentCqlPlanner
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_search_query import PatentSearchQueryPurpose
from app.schemas.patent_technical_concept import (
    PatentTechnicalConcept,
    PatentTechnicalConceptPlan,
    PatentTechnicalConceptRole,
)


def request(
    *,
    cutoff: date | None = None,
) -> PatentResearchRequest:
    return PatentResearchRequest(
        question=("How can pressure sensors detect seat occupancy without user input?"),
        objective=(
            "Identify pressure sensors and automatic state detection "
            "for seat occupancy."
        ),
        prior_art_cutoff_date=cutoff,
        maximum_search_results=4,
        maximum_sources=2,
    )


def concept_plan(
    *,
    cutoff: date | None = None,
    include_alternate: bool = False,
) -> PatentTechnicalConceptPlan:
    concepts = [
        PatentTechnicalConcept(
            role=PatentTechnicalConceptRole.PRIMARY,
            terms=("pressure sensors", "seat occupancy"),
        )
    ]

    if include_alternate:
        concepts.append(
            PatentTechnicalConcept(
                role=PatentTechnicalConceptRole.ALTERNATE,
                terms=("automatic state detection", "seat occupancy"),
            )
        )

    return PatentTechnicalConceptPlan(
        request=request(cutoff=cutoff),
        concepts=tuple(concepts),
    )


def test_planner_renders_one_primary_title_abstract_query() -> None:
    result = EpoOpsPatentCqlPlanner().plan(concept_plan())

    assert result.request == concept_plan().request
    assert len(result.queries) == 1
    assert result.queries[0].purpose is PatentSearchQueryPurpose.PRIMARY
    assert result.queries[0].cql_query == (
        'ta all "pressure sensors" and ta all "seat occupancy"'
    )


def test_planner_maps_second_concept_to_alternate_query() -> None:
    result = EpoOpsPatentCqlPlanner().plan(concept_plan(include_alternate=True))

    assert [query.purpose for query in result.queries] == [
        PatentSearchQueryPurpose.PRIMARY,
        PatentSearchQueryPurpose.ALTERNATE,
    ]
    assert result.queries[1].cql_query == (
        'ta all "automatic state detection" and ta all "seat occupancy"'
    )


def test_planner_adds_publication_date_search_bound() -> None:
    result = EpoOpsPatentCqlPlanner().plan(concept_plan(cutoff=date(2026, 5, 1)))

    assert result.queries[0].cql_query == (
        'ta all "pressure sensors" and ta all "seat occupancy" and pd < 20260501'
    )


def test_planner_preserves_request_identity_values() -> None:
    source = concept_plan(
        cutoff=date(2026, 5, 1),
        include_alternate=True,
    )

    result = EpoOpsPatentCqlPlanner().plan(source)

    assert result.request == source.request


@pytest.mark.parametrize(
    "term",
    [
        'pressure "sensor"',
        "pressure*sensor",
        "pressure?sensor",
        "pressure#sensor",
    ],
)
def test_planner_rejects_first_slice_cql_metacharacters(term: str) -> None:
    source_request = PatentResearchRequest(
        question=f"How does {term} detect seat occupancy?",
        objective=f"Identify {term} and seat occupancy.",
    )
    source = PatentTechnicalConceptPlan(
        request=source_request,
        concepts=(
            PatentTechnicalConcept(
                role=PatentTechnicalConceptRole.PRIMARY,
                terms=(term,),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="CQL metacharacters",
    ):
        EpoOpsPatentCqlPlanner().plan(source)


def test_planner_fails_fast_for_non_ascii_terms() -> None:
    source_request = PatentResearchRequest(
        question="압력센서로 착석 상태를 감지하는 기술은?",
        objective="압력센서와 착석 상태를 조사한다.",
    )
    source = PatentTechnicalConceptPlan(
        request=source_request,
        concepts=(
            PatentTechnicalConcept(
                role=PatentTechnicalConceptRole.PRIMARY,
                terms=("압력센서", "착석 상태"),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="requires ASCII technical terms",
    ):
        EpoOpsPatentCqlPlanner().plan(source)


def test_planner_is_deterministic() -> None:
    planner = EpoOpsPatentCqlPlanner()
    source = concept_plan(
        cutoff=date(2026, 5, 1),
        include_alternate=True,
    )

    first = planner.plan(source)
    second = planner.plan(source)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
