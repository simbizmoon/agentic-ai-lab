"""Tests for patent claim-chart runtime integration."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.patent_claim_chart_runtime import (
    PatentClaimChartRuntime,
)
from app.research.patent_prior_art_evidence_mapping_runtime import (
    PatentPriorArtEvidenceMappingRuntimeResult,
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


@dataclass(frozen=True)
class FakeDecompositionResult:
    marker: str = "decomposition"


@dataclass(frozen=True)
class FakeEvidenceResult:
    marker: str = "evidence"


def evaluation(
    evidence_id: str,
    publication_number: str,
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


def mapping_document(
    *,
    publication_number: str,
    publication_docdb: str,
    language: str,
    element_text: str,
    evidence_id: str,
    prior_art_publication: str,
) -> PatentClaimsDocumentEvidenceMapping:
    return PatentClaimsDocumentEvidenceMapping(
        publication_number=publication_number,
        publication_docdb=publication_docdb,
        source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            f"published-data/publication/docdb/{publication_docdb}/claims"
        ),
        claim_sets=(
            PatentClaimSetEvidenceMapping(
                language=language,
                claims=(
                    PatentClaimEvidenceMapping(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text=f"{language} claim one.",
                        elements=(
                            PatentClaimElementEvidenceMapping(
                                element_number=1,
                                element_text=element_text,
                                evaluations=(
                                    evaluation(
                                        evidence_id,
                                        prior_art_publication,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def runtime_input(
    *documents: PatentClaimsDocumentEvidenceMapping,
) -> PatentPriorArtEvidenceMappingRuntimeResult:
    return PatentPriorArtEvidenceMappingRuntimeResult(
        decomposition_result=FakeDecompositionResult(),  # type: ignore[arg-type]
        evidence_result=FakeEvidenceResult(),  # type: ignore[arg-type]
        mapping_documents=documents,
    )


def test_runtime_builds_one_chart_per_mapping_document() -> None:
    first = mapping_document(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        language="EN",
        element_text="first element",
        evidence_id="001",
        prior_art_publication="EP2000000A1",
    )
    second = mapping_document(
        publication_number="EP3000000B1",
        publication_docdb="EP.3000000.B1",
        language="DE",
        element_text="zweites Element",
        evidence_id="002",
        prior_art_publication="EP4000000A1",
    )

    result = PatentClaimChartRuntime().build(runtime_input(first, second))

    assert tuple(chart.target_publication_number for chart in result.charts) == (
        "EP1000000B1",
        "EP3000000B1",
    )


def test_runtime_preserves_exact_input_mapping_result() -> None:
    mapping_result = runtime_input(
        mapping_document(
            publication_number="EP1000000B1",
            publication_docdb="EP.1000000.B1",
            language="EN",
            element_text="first element",
            evidence_id="001",
            prior_art_publication="EP2000000A1",
        )
    )

    result = PatentClaimChartRuntime().build(mapping_result)

    assert result.mapping_result is mapping_result


def test_runtime_preserves_mapping_provenance_in_chart() -> None:
    mapping = mapping_document(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        language="EN",
        element_text="first element",
        evidence_id="001",
        prior_art_publication="EP2000000A1",
    )

    result = PatentClaimChartRuntime().build(runtime_input(mapping))
    evaluation_result = result.charts[0].claim_sets[0].claims[0].rows[0].evaluations[0]

    assert evaluation_result.publication_number == "EP2000000A1"
    assert evaluation_result.evidence_id == "001"
    assert evaluation_result.source_id == "source-001"
    assert evaluation_result.document_id == "document-001"
    assert evaluation_result.excerpt == "excerpt-001"


def test_runtime_zero_mapping_documents_produces_zero_charts() -> None:
    result = PatentClaimChartRuntime().build(runtime_input())

    assert result.charts == ()


def test_runtime_adds_no_legal_conclusion_fields() -> None:
    mapping = mapping_document(
        publication_number="EP1000000B1",
        publication_docdb="EP.1000000.B1",
        language="EN",
        element_text="first element",
        evidence_id="001",
        prior_art_publication="EP2000000A1",
    )

    chart = PatentClaimChartRuntime().build(runtime_input(mapping)).charts[0]
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
