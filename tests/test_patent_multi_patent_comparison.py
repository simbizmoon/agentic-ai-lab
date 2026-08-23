"""Tests for multi-patent technical comparison contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_multi_patent_comparison import (
    PatentMultiPatentComparison,
    PatentMultiPatentComparisonClaim,
    PatentMultiPatentComparisonClaimSet,
    PatentMultiPatentComparisonRow,
    PatentPriorArtPublicationComparison,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)

SCOPE_NOTICE = (
    "This is a technical multi-patent comparison only. "
    "It does not determine novelty, anticipation, obviousness, inventive step, "
    "validity, invalidity, infringement, freedom to operate, legal status, "
    "claim scope, essentiality, or claim dependency."
)


def evaluation(
    *,
    publication_number: str,
    evidence_id: str,
    level: EvidenceRelevanceLevel = EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
) -> PatentPriorArtEvidenceEvaluation:
    excerpt = f"excerpt-{evidence_id}"
    return PatentPriorArtEvidenceEvaluation(
        publication_number=publication_number,
        evidence_id=evidence_id,
        source_id=f"source-{evidence_id}",
        document_id=f"document-{evidence_id}",
        excerpt=excerpt,
        start_character=0,
        end_character=len(excerpt),
        judgment=EvidenceRelevanceJudgment(
            relevance_level=level,
            relevance_score=0.7,
            rationale="fixture technical relevance",
            issues=[],
        ),
    )


def publication_cell(
    publication_number: str,
    *evaluations: PatentPriorArtEvidenceEvaluation,
) -> PatentPriorArtPublicationComparison:
    return PatentPriorArtPublicationComparison(
        publication_number=publication_number,
        evaluations=evaluations
        or (
            evaluation(
                publication_number=publication_number,
                evidence_id=f"{publication_number}-001",
            ),
        ),
    )


def row(
    *,
    row_number: int = 1,
    element_number: int = 1,
    publications: tuple[PatentPriorArtPublicationComparison, ...] = (),
) -> PatentMultiPatentComparisonRow:
    return PatentMultiPatentComparisonRow(
        row_number=row_number,
        claim_number=1,
        provider_position=1,
        element_number=element_number,
        element_text=f"technical element {element_number}",
        publications=publications,
    )


def claim(
    *rows: PatentMultiPatentComparisonRow,
) -> PatentMultiPatentComparisonClaim:
    return PatentMultiPatentComparisonClaim(
        claim_number=1,
        provider_position=1,
        original_claim_text="1. A target technical claim.",
        rows=rows or (row(),),
    )


def claim_set(
    *claims: PatentMultiPatentComparisonClaim,
) -> PatentMultiPatentComparisonClaimSet:
    return PatentMultiPatentComparisonClaimSet(
        language="EN",
        claims=claims or (claim(),),
    )


def comparison() -> PatentMultiPatentComparison:
    first = publication_cell("EP2000000A1")
    second = publication_cell("EP3000000A1")
    return PatentMultiPatentComparison(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        target_source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.1000000.B1/claims"
        ),
        prior_art_publications=("EP2000000A1", "EP3000000A1"),
        claim_sets=(
            claim_set(
                claim(
                    row(
                        row_number=1,
                        element_number=1,
                        publications=(first, second),
                    ),
                    row(
                        row_number=2,
                        element_number=2,
                        publications=(second,),
                    ),
                )
            ),
        ),
        scope_notice=SCOPE_NOTICE,
    )


def test_comparison_accepts_multiple_prior_art_publications() -> None:
    result = comparison()

    assert result.prior_art_publications == (
        "EP2000000A1",
        "EP3000000A1",
    )
    assert tuple(
        item.publication_number
        for item in result.claim_sets[0].claims[0].rows[0].publications
    ) == ("EP2000000A1", "EP3000000A1")


def test_publication_cell_allows_multiple_evaluations_from_same_publication() -> None:
    result = publication_cell(
        "EP2000000A1",
        evaluation(
            publication_number="EP2000000A1",
            evidence_id="evidence-001",
        ),
        evaluation(
            publication_number="EP2000000A1",
            evidence_id="evidence-002",
            level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        ),
    )

    assert len(result.evaluations) == 2


def test_publication_cell_rejects_publication_identity_drift() -> None:
    with pytest.raises(ValidationError, match="must match its cell"):
        publication_cell(
            "EP2000000A1",
            evaluation(
                publication_number="EP3000000A1",
                evidence_id="evidence-001",
            ),
        )


def test_publication_cell_rejects_duplicate_evidence_ids() -> None:
    duplicate = evaluation(
        publication_number="EP2000000A1",
        evidence_id="same",
    )

    with pytest.raises(ValidationError, match="unique evidence IDs"):
        publication_cell("EP2000000A1", duplicate, duplicate)


def test_row_allows_zero_prior_art_publications() -> None:
    result = row()

    assert result.publications == ()


def test_row_rejects_duplicate_publication_cells() -> None:
    cell = publication_cell("EP2000000A1")

    with pytest.raises(ValidationError, match="unique within one row"):
        row(publications=(cell, cell))


def test_claim_requires_contiguous_element_numbers() -> None:
    with pytest.raises(ValidationError, match="contiguous from 1"):
        claim(
            row(row_number=1, element_number=1),
            row(row_number=2, element_number=3),
        )


def test_claim_rejects_row_claim_identity_drift() -> None:
    bad = row().model_copy(update={"claim_number": 2})

    with pytest.raises(ValidationError, match="claim_number must match"):
        PatentMultiPatentComparisonClaim(
            claim_number=1,
            provider_position=1,
            original_claim_text="1. A target claim.",
            rows=(bad,),
        )


def test_claim_set_requires_contiguous_provider_positions() -> None:
    second = PatentMultiPatentComparisonClaim(
        claim_number=2,
        provider_position=3,
        original_claim_text="2. Another target claim.",
        rows=(
            PatentMultiPatentComparisonRow(
                row_number=2,
                claim_number=2,
                provider_position=3,
                element_number=1,
                element_text="another element",
                publications=(),
            ),
        ),
    )

    with pytest.raises(ValidationError, match="provider positions must be contiguous"):
        claim_set(claim(), second)


def test_comparison_requires_contiguous_global_row_numbers() -> None:
    with pytest.raises(ValidationError, match="row numbers must be contiguous"):
        PatentMultiPatentComparison(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            target_source_endpoint="https://ops.epo.org/claims",
            prior_art_publications=(),
            claim_sets=(
                claim_set(
                    claim(
                        row(row_number=1, element_number=1),
                        row(row_number=3, element_number=2),
                    )
                ),
            ),
            scope_notice=SCOPE_NOTICE,
        )


def test_comparison_rejects_duplicate_publication_axis() -> None:
    cell = publication_cell("EP2000000A1")

    with pytest.raises(ValidationError, match="must be unique"):
        PatentMultiPatentComparison(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            target_source_endpoint="https://ops.epo.org/claims",
            prior_art_publications=("EP2000000A1", "EP2000000A1"),
            claim_sets=(claim_set(claim(row(publications=(cell,)))),),
            scope_notice=SCOPE_NOTICE,
        )


def test_comparison_requires_row_publications_to_follow_axis_order() -> None:
    first = publication_cell("EP2000000A1")
    second = publication_cell("EP3000000A1")

    with pytest.raises(ValidationError, match="must follow"):
        PatentMultiPatentComparison(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            target_source_endpoint="https://ops.epo.org/claims",
            prior_art_publications=("EP2000000A1", "EP3000000A1"),
            claim_sets=(
                claim_set(
                    claim(
                        row(
                            publications=(second, first),
                        )
                    )
                ),
            ),
            scope_notice=SCOPE_NOTICE,
        )


def test_comparison_axis_must_match_first_seen_publications() -> None:
    first = publication_cell("EP2000000A1")

    with pytest.raises(ValidationError, match="must match first-seen"):
        PatentMultiPatentComparison(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            target_source_endpoint="https://ops.epo.org/claims",
            prior_art_publications=("EP2000000A1", "EP3000000A1"),
            claim_sets=(claim_set(claim(row(publications=(first,)))),),
            scope_notice=SCOPE_NOTICE,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "target_publication_number",
        "target_publication_docdb",
        "target_source_endpoint",
        "scope_notice",
    ),
)
def test_comparison_rejects_blank_required_text(field_name: str) -> None:
    values = comparison().model_dump()
    values[field_name] = " "

    with pytest.raises(ValidationError):
        PatentMultiPatentComparison(**values)


def test_comparison_contains_no_legal_conclusion_fields() -> None:
    serialized = repr(comparison().model_dump()).casefold()

    for forbidden in (
        "'novelty':",
        "'anticipation':",
        "'obviousness':",
        "'inventive_step':",
        "'invalidity':",
        "'infringement':",
        "'freedom_to_operate':",
        "'legal_status':",
        "'claim_scope':",
        "'essentiality':",
        "'depends_on':",
    ):
        assert forbidden not in serialized
