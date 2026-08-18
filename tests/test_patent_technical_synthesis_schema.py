"""Tests for bounded patent technical synthesis schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.patent_technical_synthesis import (
    PatentTechnicalFindingSummary,
    PatentTechnicalSynthesis,
)


def test_synthesis_accepts_ordered_findings() -> None:
    value = PatentTechnicalSynthesis(
        overall_summary="Two publications are technically relevant.",
        finding_summaries=[
            PatentTechnicalFindingSummary(
                finding_id="finding-001",
                technical_summary="The cited excerpt describes seat sensing.",
            )
        ],
        limitations=["The current slice uses abstract evidence."],
    )

    assert value.finding_summaries[0].finding_id == "finding-001"


def test_synthesis_rejects_duplicate_finding_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="finding summary IDs must be unique",
    ):
        PatentTechnicalSynthesis(
            overall_summary="Summary.",
            finding_summaries=[
                PatentTechnicalFindingSummary(
                    finding_id="finding-001",
                    technical_summary="First.",
                ),
                PatentTechnicalFindingSummary(
                    finding_id="FINDING-001",
                    technical_summary="Second.",
                ),
            ],
        )


def test_synthesis_allows_zero_findings() -> None:
    value = PatentTechnicalSynthesis(
        overall_summary=("No semantically evaluated relevant finding was available."),
        finding_summaries=[],
        limitations=["One evidence item remained unevaluated."],
    )

    assert value.finding_summaries == []
