"""Tests for provider-neutral patent claim-chart contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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

SCOPE_NOTICE = (
    "This claim chart is a technical comparison artifact only. "
    "It does not determine novelty, anticipation, obviousness, inventive step, "
    "validity, invalidity, infringement, freedom to operate, legal status, "
    "or claim scope."
)


def evaluation() -> PatentPriorArtEvidenceEvaluation:
    return PatentPriorArtEvidenceEvaluation(
        publication_number="EP2000000A1",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        excerpt="A pressure sensor detects occupancy.",
        start_character=10,
        end_character=46,
        judgment=EvidenceRelevanceJudgment(
            relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            relevance_score=0.91,
            rationale="The excerpt describes the same technical feature.",
            issues=[],
        ),
    )


def row(
    *,
    row_number: int = 1,
    claim_number: int = 1,
    provider_position: int = 1,
    element_number: int = 1,
) -> PatentClaimChartRow:
    return PatentClaimChartRow(
        row_number=row_number,
        claim_number=claim_number,
        provider_position=provider_position,
        element_number=element_number,
        element_text="a pressure sensor configured to detect occupancy",
        evaluations=(evaluation(),),
    )


def claim(*rows: PatentClaimChartRow) -> PatentClaimChartClaim:
    return PatentClaimChartClaim(
        claim_number=1,
        provider_position=1,
        original_claim_text=(
            "1. A system comprising a pressure sensor configured to detect occupancy."
        ),
        rows=rows or (row(),),
    )


def claim_set(*claims: PatentClaimChartClaim) -> PatentClaimChartClaimSet:
    return PatentClaimChartClaimSet(
        language="EN",
        claims=claims or (claim(),),
    )


def chart(*claim_sets: PatentClaimChartClaimSet) -> PatentClaimChart:
    return PatentClaimChart(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        target_source_endpoint=(
            "https://ops.epo.org/3.2/rest-services/"
            "published-data/publication/docdb/EP.1000000.B1/claims"
        ),
        claim_sets=claim_sets or (claim_set(),),
        scope_notice=SCOPE_NOTICE,
    )


def test_claim_chart_accepts_traceable_technical_mapping() -> None:
    result = chart()

    assert result.target_publication_number == "EP1000000B1"
    assert result.claim_sets[0].claims[0].rows[0].evaluations[0].evidence_id == (
        "evidence-001"
    )


def test_claim_chart_row_allows_zero_evaluations() -> None:
    result = PatentClaimChartRow(
        row_number=1,
        claim_number=1,
        provider_position=1,
        element_number=1,
        element_text="a pressure sensor",
        evaluations=(),
    )

    assert result.evaluations == ()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("element_text", ""),
        ("element_text", " pressure sensor"),
        ("element_text", "pressure sensor "),
    ],
)
def test_claim_chart_row_rejects_invalid_element_text(
    field_name: str,
    value: str,
) -> None:
    values = row().model_dump()
    values[field_name] = value

    with pytest.raises(ValidationError):
        PatentClaimChartRow(**values)


def test_claim_chart_claim_requires_contiguous_element_numbers() -> None:
    with pytest.raises(ValidationError, match="contiguous from 1"):
        claim(
            row(row_number=1, element_number=1),
            row(row_number=2, element_number=3),
        )


def test_claim_chart_claim_rejects_row_claim_identity_drift() -> None:
    with pytest.raises(ValidationError, match="claim_number must match"):
        PatentClaimChartClaim(
            claim_number=1,
            provider_position=1,
            original_claim_text="1. A system.",
            rows=(
                row(
                    claim_number=2,
                    provider_position=1,
                    element_number=1,
                ),
            ),
        )


def test_claim_chart_claim_rejects_row_provider_position_drift() -> None:
    with pytest.raises(ValidationError, match="provider_position must match"):
        PatentClaimChartClaim(
            claim_number=1,
            provider_position=1,
            original_claim_text="1. A system.",
            rows=(
                row(
                    claim_number=1,
                    provider_position=2,
                    element_number=1,
                ),
            ),
        )


def test_claim_chart_claim_set_requires_unique_claim_numbers() -> None:
    duplicate = PatentClaimChartClaim(
        claim_number=1,
        provider_position=2,
        original_claim_text="1. Another claim.",
        rows=(
            PatentClaimChartRow(
                row_number=2,
                claim_number=1,
                provider_position=2,
                element_number=1,
                element_text="another element",
                evaluations=(),
            ),
        ),
    )

    with pytest.raises(ValidationError, match="claim numbers must be unique"):
        claim_set(claim(), duplicate)


def test_claim_chart_claim_set_requires_contiguous_provider_positions() -> None:
    second = PatentClaimChartClaim(
        claim_number=2,
        provider_position=3,
        original_claim_text="2. Another claim.",
        rows=(
            PatentClaimChartRow(
                row_number=2,
                claim_number=2,
                provider_position=3,
                element_number=1,
                element_text="another element",
                evaluations=(),
            ),
        ),
    )

    with pytest.raises(ValidationError, match="provider positions must be contiguous"):
        claim_set(claim(), second)


def test_claim_chart_requires_contiguous_global_row_numbers() -> None:
    bad_claim = PatentClaimChartClaim(
        claim_number=1,
        provider_position=1,
        original_claim_text="1. A system.",
        rows=(
            row(row_number=1, element_number=1),
            row(row_number=3, element_number=2),
        ),
    )

    with pytest.raises(ValidationError, match="row numbers must be contiguous"):
        chart(claim_set(bad_claim))


@pytest.mark.parametrize(
    "field_name",
    (
        "target_publication_number",
        "target_publication_docdb",
        "target_source_endpoint",
        "scope_notice",
    ),
)
def test_claim_chart_rejects_blank_required_text(field_name: str) -> None:
    values = chart().model_dump()
    values[field_name] = " "

    with pytest.raises(ValidationError):
        PatentClaimChart(**values)


def test_claim_chart_contains_no_legal_conclusion_fields() -> None:
    serialized = repr(chart().model_dump()).casefold()

    forbidden_keys = (
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
    )

    for forbidden in forbidden_keys:
        assert forbidden not in serialized
