"""Tests for deterministic patent claim-chart construction."""

from __future__ import annotations

from app.research.patent_claim_chart_builder import (
    PATENT_CLAIM_CHART_SCOPE_NOTICE,
    DeterministicPatentClaimChartBuilder,
)
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


def evaluation(
    *,
    publication_number: str,
    evidence_id: str,
    level: EvidenceRelevanceLevel,
) -> PatentPriorArtEvidenceEvaluation:
    return PatentPriorArtEvidenceEvaluation(
        publication_number=publication_number,
        evidence_id=evidence_id,
        source_id=f"source-{evidence_id}",
        document_id=f"document-{evidence_id}",
        excerpt=f"excerpt for {evidence_id}",
        start_character=0,
        end_character=len(f"excerpt for {evidence_id}"),
        judgment=EvidenceRelevanceJudgment(
            relevance_level=level,
            relevance_score=0.8,
            rationale="fixture judgment",
            issues=[],
        ),
    )


def mapped_document() -> PatentClaimsDocumentEvidenceMapping:
    return PatentClaimsDocumentEvidenceMapping(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.1000000.B1/claims"
        ),
        claim_sets=(
            PatentClaimSetEvidenceMapping(
                language="DE",
                claims=(
                    PatentClaimEvidenceMapping(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="Deutscher Anspruch eins.",
                        elements=(
                            PatentClaimElementEvidenceMapping(
                                element_number=1,
                                element_text="deutsches Element eins",
                                evaluations=(
                                    evaluation(
                                        publication_number="EP2000000A1",
                                        evidence_id="evidence-001",
                                        level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                                    ),
                                ),
                            ),
                            PatentClaimElementEvidenceMapping(
                                element_number=2,
                                element_text="deutsches Element zwei",
                                evaluations=(),
                            ),
                        ),
                    ),
                ),
            ),
            PatentClaimSetEvidenceMapping(
                language="EN",
                claims=(
                    PatentClaimEvidenceMapping(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="English claim one.",
                        elements=(
                            PatentClaimElementEvidenceMapping(
                                element_number=1,
                                element_text="English element one",
                                evaluations=(
                                    evaluation(
                                        publication_number="EP3000000A1",
                                        evidence_id="evidence-002",
                                        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                                    ),
                                    evaluation(
                                        publication_number="EP4000000A1",
                                        evidence_id="evidence-003",
                                        level=EvidenceRelevanceLevel.IRRELEVANT,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_builder_preserves_target_identity_and_scope_notice() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    assert chart.target_publication_number == "EP1000000B1"
    assert chart.target_publication_docdb == "EP.1000000.B1"
    assert chart.scope_notice == PATENT_CLAIM_CHART_SCOPE_NOTICE


def test_builder_preserves_language_and_claim_order() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    assert tuple(claim_set.language for claim_set in chart.claim_sets) == ("DE", "EN")
    assert tuple(
        claim.claim_number
        for claim_set in chart.claim_sets
        for claim in claim_set.claims
    ) == (1, 1)


def test_builder_assigns_contiguous_global_row_numbers() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    assert tuple(
        row.row_number
        for claim_set in chart.claim_sets
        for claim in claim_set.claims
        for row in claim.rows
    ) == (1, 2, 3)


def test_builder_preserves_claim_and_element_identity() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    german = chart.claim_sets[0].claims[0]
    assert german.claim_number == 1
    assert german.provider_position == 1
    assert german.original_claim_text == "Deutscher Anspruch eins."
    assert tuple(row.element_number for row in german.rows) == (1, 2)
    assert tuple(row.element_text for row in german.rows) == (
        "deutsches Element eins",
        "deutsches Element zwei",
    )


def test_builder_preserves_zero_evaluation_rows() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    assert chart.claim_sets[0].claims[0].rows[1].evaluations == ()


def test_builder_preserves_all_evaluation_provenance_and_judgments() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())

    english_row = chart.claim_sets[1].claims[0].rows[0]
    assert tuple(
        evaluation.publication_number for evaluation in english_row.evaluations
    ) == ("EP3000000A1", "EP4000000A1")
    assert tuple(evaluation.evidence_id for evaluation in english_row.evaluations) == (
        "evidence-002",
        "evidence-003",
    )
    assert tuple(
        evaluation.judgment.relevance_level for evaluation in english_row.evaluations
    ) == (
        EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        EvidenceRelevanceLevel.IRRELEVANT,
    )


def test_builder_adds_no_new_legal_conclusion_fields() -> None:
    chart = DeterministicPatentClaimChartBuilder().build(mapped_document())
    serialized = repr(chart.model_dump()).casefold()

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
