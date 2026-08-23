"""Tests for deterministic multi-patent comparison runtime."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.patent_claim_chart_runtime import PatentClaimChartRuntimeResult
from app.research.patent_multi_patent_comparison_runtime import (
    PatentMultiPatentComparisonRuntime,
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


@dataclass(frozen=True)
class FakeMappingResult:
    marker: str = "mapping"


def evaluation(
    *,
    publication_number: str,
    evidence_id: str,
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
            relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            relevance_score=0.7,
            rationale="fixture technical relevance",
            issues=[],
        ),
    )


def chart(
    *,
    target_publication_number: str,
    target_publication_docdb: str,
    prior_art_publications: tuple[str, ...],
) -> PatentClaimChart:
    evaluations = tuple(
        evaluation(
            publication_number=publication_number,
            evidence_id=f"{publication_number}-001",
        )
        for publication_number in prior_art_publications
    )

    return PatentClaimChart(
        target_publication_number=target_publication_number,
        target_publication_docdb=target_publication_docdb,
        target_source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            f"published-data/publication/docdb/{target_publication_docdb}/claims"
        ),
        claim_sets=(
            PatentClaimChartClaimSet(
                language="EN",
                claims=(
                    PatentClaimChartClaim(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="English claim one.",
                        rows=(
                            PatentClaimChartRow(
                                row_number=1,
                                claim_number=1,
                                provider_position=1,
                                element_number=1,
                                element_text="English element one",
                                evaluations=evaluations,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        scope_notice="Step 4E technical claim chart only.",
    )


def chart_result(
    *charts: PatentClaimChart,
) -> PatentClaimChartRuntimeResult:
    return PatentClaimChartRuntimeResult(
        mapping_result=FakeMappingResult(),  # type: ignore[arg-type]
        charts=charts,
    )


def test_runtime_builds_one_comparison_per_chart() -> None:
    first = chart(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        prior_art_publications=("EP2000000A1", "EP3000000A1"),
    )
    second = chart(
        target_publication_number="EP4000000B1",
        target_publication_docdb="EP.4000000.B1",
        prior_art_publications=("EP5000000A1",),
    )

    result = PatentMultiPatentComparisonRuntime().build(chart_result(first, second))

    assert tuple(
        comparison.target_publication_number for comparison in result.comparisons
    ) == ("EP1000000B1", "EP4000000B1")


def test_runtime_preserves_exact_chart_result_object() -> None:
    input_result = chart_result(
        chart(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            prior_art_publications=("EP2000000A1",),
        )
    )

    result = PatentMultiPatentComparisonRuntime().build(input_result)

    assert result.chart_result is input_result


def test_runtime_preserves_prior_art_publication_axis() -> None:
    input_result = chart_result(
        chart(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            prior_art_publications=("EP2000000A1", "EP3000000A1"),
        )
    )

    result = PatentMultiPatentComparisonRuntime().build(input_result)

    assert result.comparisons[0].prior_art_publications == (
        "EP2000000A1",
        "EP3000000A1",
    )


def test_runtime_preserves_exact_evidence_provenance() -> None:
    input_result = chart_result(
        chart(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            prior_art_publications=("EP2000000A1",),
        )
    )

    source_evaluation = (
        input_result.charts[0].claim_sets[0].claims[0].rows[0].evaluations[0]
    )

    result = PatentMultiPatentComparisonRuntime().build(input_result)

    built_evaluation = (
        result.comparisons[0]
        .claim_sets[0]
        .claims[0]
        .rows[0]
        .publications[0]
        .evaluations[0]
    )

    assert built_evaluation is source_evaluation
    assert built_evaluation.evidence_id == "EP2000000A1-001"
    assert built_evaluation.source_id == "source-EP2000000A1-001"
    assert built_evaluation.document_id == "document-EP2000000A1-001"


def test_runtime_zero_charts_produce_zero_comparisons() -> None:
    result = PatentMultiPatentComparisonRuntime().build(chart_result())

    assert result.comparisons == ()


def test_runtime_adds_no_legal_or_ranking_fields() -> None:
    input_result = chart_result(
        chart(
            target_publication_number="EP1000000B1",
            target_publication_docdb="EP.1000000.B1",
            prior_art_publications=("EP2000000A1", "EP3000000A1"),
        )
    )

    comparison = PatentMultiPatentComparisonRuntime().build(input_result).comparisons[0]
    serialized = repr(comparison.model_dump()).casefold()

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
        "'rank':",
    ):
        assert forbidden not in serialized
