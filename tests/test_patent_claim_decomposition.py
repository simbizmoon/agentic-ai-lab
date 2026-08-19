"""Tests for provider-neutral patent claim-element decomposition contracts."""

import pytest
from pydantic import ValidationError

from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
    PatentClaimElementSelection,
)


def element(number: int, text: str) -> PatentClaimElement:
    return PatentClaimElement(element_number=number, text=text)


def test_element_accepts_clean_text() -> None:
    value = element(1, "a pressure sensor configured to detect seat occupancy")

    assert value.element_number == 1
    assert value.text.startswith("a pressure sensor")


@pytest.mark.parametrize("text", ["", " ", " leading", "trailing "])
def test_element_rejects_blank_or_outer_whitespace(text: str) -> None:
    with pytest.raises(ValidationError):
        element(1, text)


@pytest.mark.parametrize(
    "text",
    [
        "pressure\nsensor",
        "pressure\tsensor",
        "pressure\x00sensor",
        "pressure\x7fsensor",
    ],
)
def test_element_rejects_control_characters(text: str) -> None:
    with pytest.raises(ValidationError, match="control characters"):
        element(1, text)


def test_element_rejects_nonpositive_number() -> None:
    with pytest.raises(ValidationError):
        element(0, "pressure sensor")


def test_selection_accepts_contiguous_ordered_elements() -> None:
    value = PatentClaimElementSelection(
        elements=(
            element(1, "a pressure sensor"),
            element(2, "a controller configured to detect occupancy"),
        )
    )

    assert tuple(item.element_number for item in value.elements) == (1, 2)


@pytest.mark.parametrize(
    "numbers",
    [
        (2,),
        (1, 3),
        (1, 1),
    ],
)
def test_selection_rejects_noncontiguous_or_duplicate_numbers(
    numbers: tuple[int, ...],
) -> None:
    with pytest.raises(ValidationError, match="contiguous from 1"):
        PatentClaimElementSelection(
            elements=tuple(
                element(number, f"technical element {index}")
                for index, number in enumerate(numbers, start=1)
            )
        )


def test_selection_rejects_case_insensitive_duplicate_text() -> None:
    with pytest.raises(ValidationError, match="texts must be unique"):
        PatentClaimElementSelection(
            elements=(
                element(1, "Pressure Sensor"),
                element(2, "pressure sensor"),
            )
        )


def test_selection_rejects_empty_elements() -> None:
    with pytest.raises(ValidationError):
        PatentClaimElementSelection(elements=())


def test_decomposition_preserves_source_claim_identity_and_text() -> None:
    value = PatentClaimDecomposition(
        claim_number=1,
        provider_position=1,
        original_claim_text=("A system comprising a pressure sensor and a controller."),
        elements=(
            element(1, "a pressure sensor"),
            element(2, "a controller"),
        ),
    )

    assert value.claim_number == 1
    assert value.provider_position == 1
    assert value.original_claim_text.startswith("A system")
    assert len(value.elements) == 2


@pytest.mark.parametrize("text", ["", " ", " claim", "claim "])
def test_decomposition_rejects_blank_or_outer_whitespace_original_claim(
    text: str,
) -> None:
    with pytest.raises(ValidationError):
        PatentClaimDecomposition(
            claim_number=1,
            provider_position=1,
            original_claim_text=text,
            elements=(element(1, "pressure sensor"),),
        )


def test_decomposition_rejects_noncontiguous_elements() -> None:
    with pytest.raises(ValidationError, match="contiguous from 1"):
        PatentClaimDecomposition(
            claim_number=1,
            provider_position=1,
            original_claim_text="A system comprising a pressure sensor.",
            elements=(element(2, "pressure sensor"),),
        )


def test_decomposition_rejects_duplicate_element_texts() -> None:
    with pytest.raises(ValidationError, match="texts must be unique"):
        PatentClaimDecomposition(
            claim_number=1,
            provider_position=1,
            original_claim_text=(
                "A system comprising a pressure sensor and another pressure sensor."
            ),
            elements=(
                element(1, "pressure sensor"),
                element(2, "PRESSURE SENSOR"),
            ),
        )


def test_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PatentClaimElement.model_validate(
            {
                "element_number": 1,
                "text": "pressure sensor",
                "unexpected": "value",
            }
        )


def test_claim_set_decomposition_preserves_language_and_claim_order() -> None:
    first = PatentClaimDecomposition(
        claim_number=1,
        provider_position=1,
        original_claim_text="A system comprising a sensor.",
        elements=(element(1, "sensor"),),
    )
    second = PatentClaimDecomposition(
        claim_number=2,
        provider_position=2,
        original_claim_text="The system comprising a controller.",
        elements=(element(1, "controller"),),
    )

    from app.schemas.patent_claim_decomposition import PatentClaimSetDecomposition

    value = PatentClaimSetDecomposition(
        language="EN",
        claims=(first, second),
    )

    assert value.language == "EN"
    assert tuple(item.claim_number for item in value.claims) == (1, 2)


def test_claim_set_decomposition_rejects_noncontiguous_provider_positions() -> None:
    from app.schemas.patent_claim_decomposition import PatentClaimSetDecomposition

    value = PatentClaimDecomposition(
        claim_number=2,
        provider_position=2,
        original_claim_text="A system comprising a sensor.",
        elements=(element(1, "sensor"),),
    )

    with pytest.raises(ValidationError, match="provider positions must be contiguous"):
        PatentClaimSetDecomposition(language="EN", claims=(value,))


def test_document_decomposition_preserves_exact_publication_identity() -> None:
    from app.schemas.patent_claim_decomposition import (
        PatentClaimsDocumentDecomposition,
        PatentClaimSetDecomposition,
    )

    claim_value = PatentClaimDecomposition(
        claim_number=1,
        provider_position=1,
        original_claim_text="A system comprising a sensor.",
        elements=(element(1, "sensor"),),
    )
    value = PatentClaimsDocumentDecomposition(
        publication_number="EP123456A1",
        publication_docdb="EP.123456.A1",
        source_endpoint="/published-data/publication/docdb/EP.123456.A1/claims",
        claim_sets=(
            PatentClaimSetDecomposition(
                language="EN",
                claims=(claim_value,),
            ),
        ),
    )

    assert value.publication_number == "EP123456A1"
    assert value.publication_docdb == "EP.123456.A1"
