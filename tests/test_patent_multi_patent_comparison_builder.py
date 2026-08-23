"""Tests for deterministic multi-patent comparison construction."""

from __future__ import annotations

from app.research.patent_multi_patent_comparison_builder import (
    PATENT_MULTI_PATENT_COMPARISON_SCOPE_NOTICE,
    DeterministicPatentMultiPatentComparisonBuilder,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_claim_chart import (
    PatentClaimChart,
    PatentClaimChartClaim,
    PatentClaimChartClaimSet,
    PatentClaimChartRow,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)


def evaluation(
    *,
    publication_number: str,
    evidence_id: str,
    level: EvidenceRelevanceLevel,
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
            relevance_score=0.8,
            rationale="fixture technical relevance",
            issues=[],
        ),
    )


def chart() -> PatentClaimChart:
    return PatentClaimChart(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        target_source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.1000000.B1/claims"
        ),
        claim_sets=(
            PatentClaimChartClaimSet(
                language="DE",
                claims=(
                    PatentClaimChartClaim(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="Deutscher Anspruch eins.",
                        rows=(
                            PatentClaimChartRow(
                                row_number=1,
                                claim_number=1,
                                provider_position=1,
                                element_number=1,
                                element_text="deutsches Element eins",
                                evaluations=(
                                    evaluation(
                                        publication_number="EP3000000A1",
                                        evidence_id="evidence-001",
                                        level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                                    ),
                                    evaluation(
                                        publication_number="EP2000000A1",
                                        evidence_id="evidence-002",
                                        level=EvidenceRelevanceLevel.IRRELEVANT,
                                    ),
                                ),
                            ),
                            PatentClaimChartRow(
                                row_number=2,
                                claim_number=1,
                                provider_position=1,
                                element_number=2,
                                element_text="deutsches Element zwei",
                                evaluations=(),
                            ),
                        ),
                    ),
                ),
            ),
            PatentClaimChartClaimSet(
                language="EN",
                claims=(
                    PatentClaimChartClaim(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="English claim one.",
                        rows=(
                            PatentClaimChartRow(
                                row_number=3,
                                claim_number=1,
                                provider_position=1,
                                element_number=1,
                                element_text="English element one",
                                evaluations=(
                                    evaluation(
                                        publication_number="EP2000000A1",
                                        evidence_id="evidence-003",
                                        level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                                    ),
                                    evaluation(
                                        publication_number="EP4000000A1",
                                        evidence_id="evidence-004",
                                        level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                                    ),
                                    evaluation(
                                        publication_number="EP2000000A1",
                                        evidence_id="evidence-005",
                                        level=EvidenceRelevanceLevel.IRRELEVANT,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        scope_notice="Step 4E technical chart only.",
    )


def test_builder_preserves_target_identity_and_adds_scope_notice() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())

    assert result.target_publication_number == "EP1000000B1"
    assert result.target_publication_docdb == "EP.1000000.B1"
    assert result.target_source_endpoint.endswith("/EP.1000000.B1/claims")
    assert result.scope_notice == PATENT_MULTI_PATENT_COMPARISON_SCOPE_NOTICE


def test_builder_uses_first_seen_publication_order_as_comparison_axis() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())

    assert result.prior_art_publications == (
        "EP3000000A1",
        "EP2000000A1",
        "EP4000000A1",
    )


def test_builder_preserves_language_claim_and_row_order() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())

    assert tuple(claim_set.language for claim_set in result.claim_sets) == ("DE", "EN")
    assert tuple(
        row.row_number
        for claim_set in result.claim_sets
        for claim in claim_set.claims
        for row in claim.rows
    ) == (1, 2, 3)


def test_builder_groups_same_publication_evaluations_in_one_cell() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())

    english_row = result.claim_sets[1].claims[0].rows[0]
    assert tuple(item.publication_number for item in english_row.publications) == (
        "EP2000000A1",
        "EP4000000A1",
    )

    first_cell = english_row.publications[0]
    assert tuple(item.evidence_id for item in first_cell.evaluations) == (
        "evidence-003",
        "evidence-005",
    )
    assert tuple(item.judgment.relevance_level for item in first_cell.evaluations) == (
        EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        EvidenceRelevanceLevel.IRRELEVANT,
    )


def test_builder_preserves_exact_evaluation_objects() -> None:
    source = chart()
    source_evaluation = source.claim_sets[1].claims[0].rows[0].evaluations[0]

    result = DeterministicPatentMultiPatentComparisonBuilder().build(source)
    built_evaluation = (
        result.claim_sets[1].claims[0].rows[0].publications[0].evaluations[0]
    )

    assert built_evaluation is source_evaluation


def test_builder_preserves_zero_evaluation_rows() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())

    assert result.claim_sets[0].claims[0].rows[1].publications == ()


def test_builder_adds_no_legal_conclusion_fields() -> None:
    result = DeterministicPatentMultiPatentComparisonBuilder().build(chart())
    serialized = repr(result.model_dump()).casefold()

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
        "'winner':",
        "'best_patent':",
        "'coverage_percentage':",
    ):
        assert forbidden not in serialized
