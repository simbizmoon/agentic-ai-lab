"""Tests for patent technical report schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.patent_source_metadata import (
    PatentCpcClassification,
    PatentIpcClassification,
    PatentMetadataVerificationState,
    PatentParty,
    PatentPriorityClaim,
    PatentSourceFamily,
)
from app.schemas.patent_technical_report import (
    PatentTechnicalEvidenceReference,
    PatentTechnicalFinding,
    PatentTechnicalResearchReport,
)


def evidence_reference() -> PatentTechnicalEvidenceReference:
    text = "A seat pressure sensor detects occupancy."
    return PatentTechnicalEvidenceReference(
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=text,
        start_character=0,
        end_character=len(text),
    )


def finding(
    *,
    relevance_level: EvidenceRelevanceLevel = (
        EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    ),
) -> PatentTechnicalFinding:
    return PatentTechnicalFinding(
        finding_id="request-001-patent-finding-001",
        publication_number="CN122100948A",
        application_number="CN2026122100948",
        priority_claims=(
            PatentPriorityClaim(
                priority_number="KR20250015704",
                priority_date=date(2025, 2, 7),
            ),
        ),
        ipc_classifications=(
            PatentIpcClassification(text="H02J 3/ 32 A I"),
            PatentIpcClassification(text="H02J 3/ 46 A I"),
        ),
        cpc_classifications=(
            PatentCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="32",
            ),
            PatentCpcClassification(
                section="H",
                class_number="02",
                subclass="J",
                main_group="3",
                subgroup="46",
            ),
        ),
        applicants=(PatentParty(name="Seat Research Institute"),),
        inventors=(
            PatentParty(name="HEO, Sewan"),
            PatentParty(name="KU, Tai-yeon"),
        ),
        title="Vehicle seat occupancy detection method",
        source_url="https://ops.epo.org/3.2/rest-services/example",
        publication_date=date(2026, 1, 1),
        source_family=PatentSourceFamily.EPO_OPS,
        metadata_verification_state=(PatentMetadataVerificationState.VERIFIED),
        relevance_level=relevance_level,
        relevance_score=0.86,
        relevance_rationale=("The passage describes seat occupancy sensing."),
        evidence=evidence_reference(),
        abstract_language="en",
    )


def report(**overrides: object) -> PatentTechnicalResearchReport:
    values: dict[str, object] = {
        "report_id": "request-001-patent-technical-report",
        "request_id": "request-001",
        "task_id": "patent-technical-relevance",
        "question": "How is seat occupancy detected?",
        "objective": "Find technically relevant patent publications.",
        "prior_art_cutoff_date": date(2026, 8, 18),
        "title": "Patent Technical Relevance Report",
        "findings": [finding()],
        "unevaluated_evidence_ids": [],
        "finding_count": 1,
        "source_count": 1,
        "document_count": 1,
        "verified_record_count": 1,
        "input_evidence_count": 1,
        "executed_query_purpose": "primary",
        "executed_cql": 'ta all "seat occupancy"',
        "scope_notice": "Technical relevance only; no legal conclusion.",
        "builder": "deterministic-patent-technical-report-builder",
    }
    values.update(overrides)
    return PatentTechnicalResearchReport.model_validate(values)


def test_report_accepts_valid_finding() -> None:
    value = report()
    assert value.finding_count == 1
    assert value.findings[0].publication_number == "CN122100948A"
    assert value.findings[0].application_number == "CN2026122100948"
    assert value.findings[0].priority_claims == (
        PatentPriorityClaim(
            priority_number="KR20250015704",
            priority_date=date(2025, 2, 7),
        ),
    )
    assert value.findings[0].ipc_classifications == (
        PatentIpcClassification(text="H02J 3/ 32 A I"),
        PatentIpcClassification(text="H02J 3/ 46 A I"),
    )
    assert value.findings[0].cpc_classifications == (
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="32",
        ),
        PatentCpcClassification(
            section="H",
            class_number="02",
            subclass="J",
            main_group="3",
            subgroup="46",
        ),
    )
    assert value.findings[0].applicants == (
        PatentParty(name="Seat Research Institute"),
    )
    assert value.findings[0].inventors == (
        PatentParty(name="HEO, Sewan"),
        PatentParty(name="KU, Tai-yeon"),
    )


def test_finding_rejects_irrelevant_judgment() -> None:
    with pytest.raises(
        ValidationError,
        match="completed relevant judgment",
    ):
        finding(relevance_level=EvidenceRelevanceLevel.IRRELEVANT)


def test_report_accepts_only_unevaluated_input() -> None:
    value = report(
        findings=[],
        unevaluated_evidence_ids=["evidence-001"],
        finding_count=0,
        source_count=0,
        input_evidence_count=1,
    )
    assert value.findings == []
    assert value.unevaluated_evidence_ids == ["evidence-001"]


def test_report_rejects_inconsistent_input_evidence_count() -> None:
    with pytest.raises(
        ValidationError,
        match="input_evidence_count",
    ):
        report(input_evidence_count=2)
