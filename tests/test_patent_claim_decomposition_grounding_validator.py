"""Tests for deterministic patent claim-decomposition grounding."""

import pytest

from app.research.patent_claim_decomposition_grounding_validator import (
    PatentClaimDecompositionGroundingError,
    PatentClaimDecompositionGroundingValidator,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimDecomposition,
    PatentClaimElement,
)
from app.schemas.patent_claims import PatentClaim


def source_claim() -> PatentClaim:
    return PatentClaim(
        claim_number=1,
        provider_position=1,
        text=(
            "A system comprising a pressure sensor configured to detect "
            "seat occupancy and a controller configured to generate an alert "
            "when occupancy persists for a threshold duration."
        ),
    )


def decomposition(
    *,
    claim_number: int = 1,
    provider_position: int = 1,
    original_claim_text: str | None = None,
    element_texts: tuple[str, ...] = (
        "a pressure sensor configured to detect seat occupancy",
        (
            "a controller configured to generate an alert when occupancy "
            "persists for a threshold duration"
        ),
    ),
) -> PatentClaimDecomposition:
    claim = source_claim()
    return PatentClaimDecomposition(
        claim_number=claim_number,
        provider_position=provider_position,
        original_claim_text=(
            claim.text if original_claim_text is None else original_claim_text
        ),
        elements=tuple(
            PatentClaimElement(
                element_number=index,
                text=text,
            )
            for index, text in enumerate(element_texts, start=1)
        ),
    )


def test_validator_accepts_ordered_lexically_grounded_elements() -> None:
    value = decomposition()

    validated = PatentClaimDecompositionGroundingValidator().validate(
        claim=source_claim(),
        decomposition=value,
    )

    assert validated is value


def test_validator_allows_noncontiguous_source_words_when_order_is_preserved() -> None:
    value = decomposition(
        element_texts=(
            "pressure sensor detect seat occupancy",
            "controller generate alert threshold duration",
        )
    )

    PatentClaimDecompositionGroundingValidator().validate(
        claim=source_claim(),
        decomposition=value,
    )


def test_validator_is_case_insensitive_for_grounding() -> None:
    value = decomposition(
        element_texts=("PRESSURE SENSOR configured to DETECT seat occupancy",)
    )

    PatentClaimDecompositionGroundingValidator().validate(
        claim=source_claim(),
        decomposition=value,
    )


def test_validator_rejects_claim_number_drift() -> None:
    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="claim number drifted",
    ):
        PatentClaimDecompositionGroundingValidator().validate(
            claim=source_claim(),
            decomposition=decomposition(claim_number=2),
        )


def test_validator_rejects_provider_position_drift() -> None:
    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="provider position drifted",
    ):
        PatentClaimDecompositionGroundingValidator().validate(
            claim=source_claim(),
            decomposition=decomposition(provider_position=2),
        )


def test_validator_rejects_original_claim_text_drift() -> None:
    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="original claim text drifted",
    ):
        PatentClaimDecompositionGroundingValidator().validate(
            claim=source_claim(),
            decomposition=decomposition(
                original_claim_text="A different patent claim."
            ),
        )


def test_validator_rejects_invented_technical_wording() -> None:
    value = decomposition(
        element_texts=("a capacitive sensor configured to detect seat occupancy",)
    )

    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="wording or order not grounded",
    ):
        PatentClaimDecompositionGroundingValidator().validate(
            claim=source_claim(),
            decomposition=value,
        )


def test_validator_rejects_reordered_source_wording() -> None:
    value = decomposition(element_texts=("seat occupancy pressure sensor",))

    with pytest.raises(
        PatentClaimDecompositionGroundingError,
        match="wording or order not grounded",
    ):
        PatentClaimDecompositionGroundingValidator().validate(
            claim=source_claim(),
            decomposition=value,
        )


def test_validator_accepts_korean_ordered_grounding() -> None:
    claim = PatentClaim(
        claim_number=1,
        provider_position=1,
        text=(
            "압력센서와 상기 압력센서의 신호에 기초하여 "
            "착석 상태를 판정하는 제어부를 포함하는 시스템."
        ),
    )
    value = PatentClaimDecomposition(
        claim_number=1,
        provider_position=1,
        original_claim_text=claim.text,
        elements=(
            PatentClaimElement(
                element_number=1,
                text="압력센서",
            ),
            PatentClaimElement(
                element_number=2,
                text="압력센서의 신호에 기초하여 착석 상태를 판정하는 제어부를",
            ),
        ),
    )

    PatentClaimDecompositionGroundingValidator().validate(
        claim=claim,
        decomposition=value,
    )


def test_validator_does_not_require_full_claim_coverage() -> None:
    value = decomposition(element_texts=("pressure sensor",))

    PatentClaimDecompositionGroundingValidator().validate(
        claim=source_claim(),
        decomposition=value,
    )


def test_validator_accepts_korean_particle_suffix_grounding() -> None:
    claim = PatentClaim(
        claim_number=1,
        provider_position=1,
        text="압력센서와 제어부를 포함하는 시스템.",
    )
    value = PatentClaimDecomposition(
        claim_number=1,
        provider_position=1,
        original_claim_text=claim.text,
        elements=(
            PatentClaimElement(
                element_number=1,
                text="압력센서",
            ),
            PatentClaimElement(
                element_number=2,
                text="제어부",
            ),
        ),
    )

    PatentClaimDecompositionGroundingValidator().validate(
        claim=claim,
        decomposition=value,
    )
