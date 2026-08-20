"""Tests for patent claim-element to prior-art evidence mapping contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentClaimElementEvidenceMapping,
    PatentClaimEvidenceMapping,
    PatentClaimsDocumentEvidenceMapping,
    PatentClaimSetEvidenceMapping,
    PatentPriorArtEvidenceEvaluation,
)


def judgment(
    level: EvidenceRelevanceLevel = EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
) -> EvidenceRelevanceJudgment:
    return EvidenceRelevanceJudgment(
        relevance_level=level,
        relevance_score=0.9 if level is not EvidenceRelevanceLevel.IRRELEVANT else 0.1,
        rationale="Technical relationship evaluated against the exact excerpt.",
        issues=[],
    )


def evaluation(
    *,
    evidence_id: str = "evidence-001",
    publication_number: str = "EP123456A1",
) -> PatentPriorArtEvidenceEvaluation:
    excerpt = "A pressure sensor determines whether a seat is occupied."
    return PatentPriorArtEvidenceEvaluation(
        publication_number=publication_number,
        evidence_id=evidence_id,
        source_id="patent-source-001",
        document_id="patent-document-001",
        excerpt=excerpt,
        start_character=0,
        end_character=len(excerpt),
        judgment=judgment(),
    )


def element_mapping(
    number: int = 1,
    *,
    evaluations: tuple[PatentPriorArtEvidenceEvaluation, ...] | None = None,
) -> PatentClaimElementEvidenceMapping:
    return PatentClaimElementEvidenceMapping(
        element_number=number,
        element_text=(
            "a pressure sensor configured to determine whether a seat is occupied"
        ),
        evaluations=evaluations if evaluations is not None else (evaluation(),),
    )


def claim_mapping() -> PatentClaimEvidenceMapping:
    return PatentClaimEvidenceMapping(
        claim_number=1,
        provider_position=1,
        original_claim_text=(
            "1. A system comprising a pressure sensor configured to determine "
            "whether a seat is occupied."
        ),
        elements=(element_mapping(),),
    )


def test_evaluation_preserves_exact_prior_art_provenance() -> None:
    value = evaluation()

    assert value.publication_number == "EP123456A1"
    assert value.evidence_id == "evidence-001"
    assert value.source_id == "patent-source-001"
    assert value.document_id == "patent-document-001"
    assert value.excerpt == ("A pressure sensor determines whether a seat is occupied.")
    assert value.start_character == 0
    assert value.end_character == len(value.excerpt)
    assert value.judgment.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("publication_number", " "),
        ("evidence_id", " "),
        ("source_id", " "),
        ("document_id", " "),
        ("excerpt", " "),
    ],
)
def test_evaluation_rejects_blank_identity_or_excerpt(
    field_name: str,
    value: str,
) -> None:
    payload = evaluation().model_dump()
    payload[field_name] = value

    with pytest.raises(ValidationError, match=f"{field_name} must not be blank"):
        PatentPriorArtEvidenceEvaluation.model_validate(payload)


def test_evaluation_rejects_invalid_character_range() -> None:
    payload = evaluation().model_dump()
    payload["start_character"] = 10
    payload["end_character"] = 10

    with pytest.raises(
        ValidationError,
        match="end_character must be greater than start_character",
    ):
        PatentPriorArtEvidenceEvaluation.model_validate(payload)


def test_element_mapping_allows_zero_evaluations() -> None:
    value = element_mapping(evaluations=())

    assert value.evaluations == ()


def test_element_mapping_preserves_irrelevant_evaluation() -> None:
    value = element_mapping(
        evaluations=(
            evaluation().model_copy(
                update={"judgment": judgment(EvidenceRelevanceLevel.IRRELEVANT)}
            ),
        )
    )

    assert (
        value.evaluations[0].judgment.relevance_level
        is EvidenceRelevanceLevel.IRRELEVANT
    )


def test_element_mapping_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="unique evidence IDs per element",
    ):
        PatentClaimElementEvidenceMapping(
            element_number=1,
            element_text="a pressure sensor",
            evaluations=(
                evaluation(evidence_id="evidence-001"),
                evaluation(evidence_id="EVIDENCE-001"),
            ),
        )


def test_claim_mapping_requires_contiguous_element_numbers() -> None:
    with pytest.raises(
        ValidationError,
        match="element mapping numbers must be contiguous",
    ):
        PatentClaimEvidenceMapping(
            claim_number=1,
            provider_position=1,
            original_claim_text="A system with a pressure sensor.",
            elements=(element_mapping(2),),
        )


def test_document_mapping_preserves_target_claim_identity() -> None:
    value = PatentClaimsDocumentEvidenceMapping(
        publication_number="EP999999B1",
        publication_docdb="EP.999999.B1",
        source_endpoint="/published-data/publication/docdb/EP.999999.B1/claims",
        claim_sets=(
            PatentClaimSetEvidenceMapping(
                language="EN",
                claims=(claim_mapping(),),
            ),
        ),
    )

    assert value.publication_number == "EP999999B1"
    assert value.publication_docdb == "EP.999999.B1"
    assert value.claim_sets[0].language == "EN"
    assert value.claim_sets[0].claims[0].claim_number == 1


def test_schema_does_not_encode_legal_conclusions() -> None:
    dumped = PatentClaimsDocumentEvidenceMapping(
        publication_number="EP999999B1",
        publication_docdb="EP.999999.B1",
        source_endpoint="/published-data/publication/docdb/EP.999999.B1/claims",
        claim_sets=(
            PatentClaimSetEvidenceMapping(
                language="EN",
                claims=(claim_mapping(),),
            ),
        ),
    ).model_dump()

    serialized_keys = repr(dumped).casefold()
    for forbidden in (
        "novelty",
        "anticipation",
        "obviousness",
        "invalidity",
        "infringement",
        "freedom_to_operate",
        "essentiality",
        "depends_on",
    ):
        assert forbidden not in serialized_keys
