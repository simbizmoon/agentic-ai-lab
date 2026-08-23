"""Tests for deterministic Step 4G patent comparison formatting."""

from __future__ import annotations

import json

import pytest

from app.research.patent_multi_patent_comparison_formatter import (
    DeterministicPatentMultiPatentComparisonFormatter,
    PatentMultiPatentComparisonFormats,
)
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


def evaluation(
    *,
    publication_number: str,
    evidence_id: str,
    excerpt: str,
    level: EvidenceRelevanceLevel = EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
) -> PatentPriorArtEvidenceEvaluation:
    return PatentPriorArtEvidenceEvaluation(
        publication_number=publication_number,
        evidence_id=evidence_id,
        source_id=f"source-{evidence_id}",
        document_id=f"document-{evidence_id}",
        excerpt=excerpt,
        start_character=7,
        end_character=7 + len(excerpt),
        judgment=EvidenceRelevanceJudgment(
            relevance_level=level,
            relevance_score=(
                0.7 if level is not EvidenceRelevanceLevel.IRRELEVANT else 0.1
            ),
            rationale=f"Technical rationale for {evidence_id}.",
            issues=[f"Technical gap for {evidence_id}."],
        ),
    )


def comparison() -> PatentMultiPatentComparison:
    first = evaluation(
        publication_number="EP2000000A1",
        evidence_id="evidence-001",
        excerpt="Exact pressure-sensor excerpt.",
    )
    second = evaluation(
        publication_number="EP3000000A1",
        evidence_id="evidence-002",
        excerpt="Exact multilingual 증거 excerpt with ``` embedded fence.",
        level=EvidenceRelevanceLevel.IRRELEVANT,
    )
    return PatentMultiPatentComparison(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        target_source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.1000000.B1/claims"
        ),
        prior_art_publications=("EP2000000A1", "EP3000000A1"),
        claim_sets=(
            PatentMultiPatentComparisonClaimSet(
                language="EN",
                claims=(
                    PatentMultiPatentComparisonClaim(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="A target claim with two elements.",
                        rows=(
                            PatentMultiPatentComparisonRow(
                                row_number=1,
                                claim_number=1,
                                provider_position=1,
                                element_number=1,
                                element_text="A pressure sensing element.",
                                publications=(
                                    PatentPriorArtPublicationComparison(
                                        publication_number="EP2000000A1",
                                        evaluations=(first,),
                                    ),
                                    PatentPriorArtPublicationComparison(
                                        publication_number="EP3000000A1",
                                        evaluations=(second,),
                                    ),
                                ),
                            ),
                            PatentMultiPatentComparisonRow(
                                row_number=2,
                                claim_number=1,
                                provider_position=1,
                                element_number=2,
                                element_text="An element with no mapped evidence.",
                                publications=(),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        scope_notice=(
            "This is a technical comparison only. It does not determine novelty."
        ),
    )


def test_formatter_returns_json_and_markdown() -> None:
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(comparison())

    assert isinstance(formatted, PatentMultiPatentComparisonFormats)
    assert formatted.markdown.startswith("# Patent Multi-Patent Technical Comparison\n")
    assert formatted.json_text.startswith("{\n")
    assert formatted.markdown.endswith("\n")
    assert formatted.json_text.endswith("\n")


def test_json_round_trips_to_exact_comparison() -> None:
    source = comparison()
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(source)

    assert (
        PatentMultiPatentComparison.model_validate_json(formatted.json_text) == source
    )
    assert json.loads(formatted.json_text) == source.model_dump(mode="json")


def test_repeated_formatting_is_deterministic() -> None:
    formatter = DeterministicPatentMultiPatentComparisonFormatter()
    source = comparison()

    assert formatter.format(source) == formatter.format(source)


def test_markdown_preserves_order_and_exact_provenance() -> None:
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(comparison())
    markdown = formatted.markdown

    assert markdown.index("Publication EP2000000A1") < markdown.index(
        "Publication EP3000000A1"
    )
    assert markdown.index("Row 1 — Element 1") < markdown.index("Row 2 — Element 2")
    for expected in (
        "evidence-001",
        "source-evidence-001",
        "document-evidence-001",
        "7:37",
        "Exact pressure-sensor excerpt.",
        "evidence-002",
        "source-evidence-002",
        "document-evidence-002",
        "Exact multilingual 증거 excerpt with ``` embedded fence.",
    ):
        assert expected in markdown


def test_markdown_renders_judgments_issues_and_scope_verbatim() -> None:
    source = comparison()
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(source)

    assert "partially_relevant (0.700)" in formatted.markdown
    assert "irrelevant (0.100)" in formatted.markdown
    assert "Technical rationale for evidence-001." in formatted.markdown
    assert "Technical gap for evidence-002." in formatted.markdown
    assert source.scope_notice in formatted.markdown


def test_markdown_keeps_zero_evidence_row_visible() -> None:
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(comparison())

    row_start = formatted.markdown.index("Row 2 — Element 2")
    scope_start = formatted.markdown.index("## Scope Notice")
    assert "No mapped evidence." in formatted.markdown[row_start:scope_start]


def test_embedded_backticks_use_a_longer_markdown_fence() -> None:
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(comparison())

    excerpt = "Exact multilingual 증거 excerpt with ``` embedded fence."
    assert f"````\n{excerpt}\n````" in formatted.markdown


def test_formatter_rejects_wrong_input_type() -> None:
    with pytest.raises(
        TypeError,
        match="comparison must be a PatentMultiPatentComparison",
    ):
        DeterministicPatentMultiPatentComparisonFormatter().format(object())  # type: ignore[arg-type]


def test_output_adds_no_legal_or_ranking_fields() -> None:
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(comparison())
    keys = collect_keys(json.loads(formatted.json_text))

    assert {
        "novelty",
        "anticipation",
        "obviousness",
        "inventive_step",
        "invalidity",
        "infringement",
        "freedom_to_operate",
        "legal_status",
        "claim_scope",
        "essentiality",
        "depends_on",
        "winner",
        "best_patent",
        "coverage_percentage",
        "rank",
    }.isdisjoint(keys)


def collect_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key).casefold() for key in value}
        for nested in value.values():
            keys.update(collect_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(collect_keys(nested))
        return keys
    return set()
