"""Tests for grounded patent technical-concept contracts."""

import pytest
from pydantic import ValidationError

from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_technical_concept import (
    MAXIMUM_PATENT_TECHNICAL_TERM_CHARACTERS,
    PatentTechnicalConcept,
    PatentTechnicalConceptPlan,
    PatentTechnicalConceptRole,
    PatentTechnicalConceptSelection,
)


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question=("How can pressure sensors detect seat occupancy without user input?"),
        objective=(
            "Identify technical disclosures about pressure sensors, "
            "seat occupancy, and automatic state detection."
        ),
    )


def concept(
    *terms: str,
    role: PatentTechnicalConceptRole = PatentTechnicalConceptRole.PRIMARY,
) -> PatentTechnicalConcept:
    return PatentTechnicalConcept(role=role, terms=terms)


def test_concept_accepts_bounded_terms() -> None:
    value = concept("pressure sensors", "seat occupancy")

    assert value.terms == ("pressure sensors", "seat occupancy")


@pytest.mark.parametrize("term", ["", " pressure sensors", "pressure sensors "])
def test_concept_rejects_blank_or_outer_whitespace(term: str) -> None:
    with pytest.raises(ValidationError):
        concept(term)


@pytest.mark.parametrize(
    "term",
    [
        "pressure\nsensors",
        "pressure\tsensors",
        "pressure\x00sensors",
        "pressure\x7fsensors",
    ],
)
def test_concept_rejects_control_characters(term: str) -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain control characters",
    ):
        concept(term)


def test_concept_rejects_long_term() -> None:
    with pytest.raises(ValidationError, match="too long"):
        concept("x" * (MAXIMUM_PATENT_TECHNICAL_TERM_CHARACTERS + 1))


def test_concept_rejects_case_insensitive_duplicate_terms() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        concept("seat occupancy", "Seat Occupancy")


def test_selection_accepts_structured_output_json_enum_values() -> None:
    value = PatentTechnicalConceptSelection.model_validate_json(
        """
        {
          "concepts": [
            {
              "role": "primary",
              "terms": ["pressure sensors", "seat occupancy"]
            },
            {
              "role": "alternate",
              "terms": ["automatic state detection"]
            }
          ]
        }
        """
    )

    assert value.concepts[0].role is PatentTechnicalConceptRole.PRIMARY
    assert value.concepts[1].role is PatentTechnicalConceptRole.ALTERNATE


def test_selection_requires_primary_first() -> None:
    with pytest.raises(
        ValidationError,
        match="first patent technical concept must be primary",
    ):
        PatentTechnicalConceptSelection(
            concepts=(
                concept(
                    "seat occupancy",
                    role=PatentTechnicalConceptRole.ALTERNATE,
                ),
            )
        )


def test_selection_accepts_primary_then_alternate() -> None:
    value = PatentTechnicalConceptSelection(
        concepts=(
            concept("pressure sensors", "seat occupancy"),
            concept(
                "automatic state detection",
                role=PatentTechnicalConceptRole.ALTERNATE,
            ),
        )
    )

    assert len(value.concepts) == 2


def test_selection_rejects_primary_as_second_concept() -> None:
    with pytest.raises(
        ValidationError,
        match="second patent technical concept must be alternate",
    ):
        PatentTechnicalConceptSelection(
            concepts=(
                concept("pressure sensors"),
                concept("seat occupancy"),
            )
        )


def test_selection_rejects_duplicate_concepts_independent_of_term_order() -> None:
    with pytest.raises(ValidationError, match="must not be duplicates"):
        PatentTechnicalConceptSelection(
            concepts=(
                concept("pressure sensors", "seat occupancy"),
                concept(
                    "seat occupancy",
                    "PRESSURE SENSORS",
                    role=PatentTechnicalConceptRole.ALTERNATE,
                ),
            )
        )


def test_plan_requires_every_term_to_be_grounded_in_request() -> None:
    with pytest.raises(
        ValidationError,
        match="must be grounded in question or objective",
    ):
        PatentTechnicalConceptPlan(
            request=request(),
            concepts=(concept("capacitive sensor"),),
        )


def test_plan_accepts_case_insensitive_grounded_terms() -> None:
    value = PatentTechnicalConceptPlan(
        request=request(),
        concepts=(concept("Pressure Sensors", "SEAT OCCUPANCY"),),
    )

    assert len(value.concepts) == 1


def test_plan_accepts_korean_grounded_terms() -> None:
    korean_request = PatentResearchRequest(
        question="압력센서로 착석 상태를 자동 감지하는 기술은 무엇인가?",
        objective="착석 상태와 압력센서의 기술적 관계를 조사한다.",
    )

    value = PatentTechnicalConceptPlan(
        request=korean_request,
        concepts=(concept("압력센서", "착석 상태"),),
    )

    assert value.concepts[0].terms == ("압력센서", "착석 상태")
