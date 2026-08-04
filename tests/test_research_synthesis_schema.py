"""Tests for research synthesis report schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_synthesis import (
    ResearchSynthesisCitation,
    ResearchSynthesisReport,
    ResearchSynthesisSection,
)


def citation(
    *,
    citation_id: str = "citation-001",
    evidence_id: str = "evidence-001",
    source_id: str = "source-001",
    label: str = "[1]",
) -> ResearchSynthesisCitation:
    """Return one valid report citation."""

    return ResearchSynthesisCitation(
        citation_id=citation_id,
        evidence_id=evidence_id,
        source_id=source_id,
        document_id=f"document-{source_id}",
        label=label,
        title="Agent memory research",
        url=f"https://example.com/{source_id}",
        excerpt=(
            "Agent memory stores contextual information."
        ),
    )


def section(
    *,
    section_id: str = "section-001",
    order: int = 1,
    claim_ids: list[str] | None = None,
    citation_ids: list[str] | None = None,
) -> ResearchSynthesisSection:
    """Return one valid report section."""

    return ResearchSynthesisSection(
        section_id=section_id,
        task_id="task-001",
        title="Agent memory",
        content=(
            "1. Agent memory stores information. [1]"
        ),
        order=order,
        claim_ids=claim_ids or ["claim-001"],
        citation_ids=(
            citation_ids
            if citation_ids is not None
            else ["citation-001"]
        ),
    )


def report(
    **overrides: object,
) -> ResearchSynthesisReport:
    """Return one valid synthesized report."""

    values: dict[str, object] = {
        "report_id": "research-001-report",
        "workspace_id": "workspace-001",
        "request_id": "research-001",
        "title": "Research Report: Agent memory",
        "executive_summary": (
            "This report summarizes agent memory."
        ),
        "sections": [section()],
        "citations": [citation()],
        "claim_count": 1,
        "citation_count": 1,
        "source_count": 1,
        "synthesizer": "test-synthesizer",
    }
    values.update(overrides)

    return ResearchSynthesisReport.model_validate(
        values
    )


def test_report_accepts_valid_values() -> None:
    value = report()

    assert value.claim_count == 1
    assert value.citation_count == 1
    assert value.source_count == 1


def test_section_rejects_duplicate_claim_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="claim_ids must not contain duplicates",
    ):
        section(
            claim_ids=[
                "claim-001",
                " CLAIM-001 ",
            ]
        )


def test_report_rejects_duplicate_section_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="section IDs must be unique",
    ):
        report(
            sections=[
                section(section_id="section-001"),
                section(
                    section_id=" SECTION-001 ",
                    order=2,
                ),
            ],
        )


def test_report_rejects_duplicate_section_orders() -> None:
    with pytest.raises(
        ValidationError,
        match="section orders must be unique",
    ):
        report(
            sections=[
                section(section_id="section-001"),
                section(
                    section_id="section-002",
                    order=1,
                ),
            ],
        )


def test_report_rejects_duplicate_citation_labels() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "report citation labels must be unique"
        ),
    ):
        report(
            citations=[
                citation(),
                citation(
                    citation_id="citation-002",
                    evidence_id="evidence-002",
                    source_id="source-002",
                    label="[1]",
                ),
            ],
            citation_count=2,
            source_count=2,
        )


def test_report_rejects_missing_section_citation() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "section citations must reference "
            "report citations"
        ),
    ):
        report(
            sections=[
                section(
                    citation_ids=["missing-citation"]
                )
            ]
        )


def test_report_validates_claim_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "claim_count must match section claims"
        ),
    ):
        report(claim_count=2)


def test_report_validates_citation_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "citation_count must match citations"
        ),
    ):
        report(citation_count=2)


def test_report_validates_source_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "source_count must match citation sources"
        ),
    ):
        report(source_count=2)


def test_report_orders_sections() -> None:
    value = report(
        sections=[
            section(
                section_id="section-002",
                order=2,
                claim_ids=["claim-002"],
            ),
            section(
                section_id="section-001",
                order=1,
                claim_ids=["claim-001"],
            ),
        ],
        claim_count=2,
    )

    assert [
        item.section_id
        for item in value.ordered_sections()
    ] == [
        "section-001",
        "section-002",
    ]


def test_report_returns_citation_by_id() -> None:
    value = report()

    result = value.citation_by_id(
        " CITATION-001 "
    )

    assert result is not None
    assert result.label == "[1]"
    assert (
        value.citation_by_id("missing")
        is None
    )


def test_report_rejects_blank_citation_lookup() -> None:
    with pytest.raises(
        ValueError,
        match="citation_id must not be blank",
    ):
        report().citation_by_id(" ")
