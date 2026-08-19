"""Tests for OpenAI-backed bounded patent technical synthesis."""

import json
from types import SimpleNamespace

import pytest

from app.exceptions import StructuredResponseParseError
from app.research.openai_patent_technical_synthesizer import (
    OpenAIPatentTechnicalSynthesizer,
)
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
from app.schemas.patent_technical_synthesis import (
    PatentTechnicalFindingSummary,
    PatentTechnicalSynthesis,
)


class FakeResponses:
    def __init__(self, parsed: PatentTechnicalSynthesis) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return SimpleNamespace(
            id="resp-001",
            status="completed",
            output_parsed=self.parsed,
            usage=None,
            _request_id="req-001",
            output=[],
        )


class FakeClient:
    def __init__(self, parsed: PatentTechnicalSynthesis) -> None:
        self.responses = FakeResponses(parsed)


def report() -> PatentTechnicalResearchReport:
    excerpt = "A seat pressure sensor detects occupancy."
    finding = PatentTechnicalFinding(
        finding_id="request-001-patent-finding-001",
        publication_number="CN122100948A",
        application_number="CN2026122100948",
        priority_claims=(
            PatentPriorityClaim(
                priority_number="KR20250015704",
                priority_date=None,
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
        source_family=PatentSourceFamily.EPO_OPS,
        metadata_verification_state=(PatentMetadataVerificationState.VERIFIED),
        relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.86,
        relevance_rationale=("The passage directly describes seat occupancy sensing."),
        evidence=PatentTechnicalEvidenceReference(
            evidence_id="evidence-001",
            source_id="source-001",
            document_id="document-001",
            excerpt=excerpt,
            start_character=0,
            end_character=len(excerpt),
        ),
        abstract_language="en",
    )
    return PatentTechnicalResearchReport(
        report_id="request-001-patent-technical-report",
        request_id="request-001",
        task_id="patent-technical-relevance",
        question="How is seat occupancy detected?",
        objective="Find technically relevant patent publications.",
        title="Patent Technical Relevance Report",
        findings=[finding],
        unevaluated_evidence_ids=[],
        finding_count=1,
        source_count=1,
        document_count=1,
        verified_record_count=1,
        input_evidence_count=1,
        executed_query_purpose="primary",
        executed_cql='ta all "seat occupancy"',
        scope_notice=("This report summarizes bounded technical relevance only."),
        builder="deterministic-patent-technical-report-builder",
    )


def test_synthesizer_preserves_exact_finding_id() -> None:
    parsed = PatentTechnicalSynthesis(
        overall_summary="One publication is technically relevant.",
        finding_summaries=[
            PatentTechnicalFindingSummary(
                finding_id="request-001-patent-finding-001",
                technical_summary=(
                    "The cited excerpt describes pressure-based seat sensing."
                ),
            )
        ],
        limitations=["The result is based on abstract evidence."],
    )
    client = FakeClient(parsed)

    result = OpenAIPatentTechnicalSynthesizer(
        client=client,
        model="gpt-5",
    ).synthesize(report())

    assert result.synthesis.finding_summaries[0].finding_id == (
        "request-001-patent-finding-001"
    )
    call = client.responses.calls[0]
    payload = json.loads(call["input"])
    assert payload["findings"][0]["application_number"] == "CN2026122100948"
    assert payload["findings"][0]["priority_claims"] == [
        {
            "priority_number": "KR20250015704",
            "priority_date": None,
        }
    ]
    assert payload["findings"][0]["ipc_classifications"] == [
        {"text": "H02J 3/ 32 A I"},
        {"text": "H02J 3/ 46 A I"},
    ]
    assert payload["findings"][0]["cpc_classifications"] == [
        {
            "section": "H",
            "class_number": "02",
            "subclass": "J",
            "main_group": "3",
            "subgroup": "32",
        },
        {
            "section": "H",
            "class_number": "02",
            "subclass": "J",
            "main_group": "3",
            "subgroup": "46",
        },
    ]
    assert payload["findings"][0]["applicants"] == [{"name": "Seat Research Institute"}]
    assert payload["findings"][0]["inventors"] == [
        {"name": "HEO, Sewan"},
        {"name": "KU, Tai-yeon"},
    ]
    assert call["text_format"] is PatentTechnicalSynthesis
    assert call["store"] is False


def test_synthesizer_rejects_finding_id_drift() -> None:
    parsed = PatentTechnicalSynthesis(
        overall_summary="Summary.",
        finding_summaries=[
            PatentTechnicalFindingSummary(
                finding_id="invented-finding",
                technical_summary="Invented mapping.",
            )
        ],
    )

    with pytest.raises(
        StructuredResponseParseError,
        match="finding IDs did not match report",
    ):
        OpenAIPatentTechnicalSynthesizer(
            client=FakeClient(parsed),
            model="gpt-5",
        ).synthesize(report())


def test_synthesizer_accepts_zero_finding_report() -> None:
    empty = report().model_copy(
        update={
            "findings": [],
            "finding_count": 0,
            "source_count": 0,
            "input_evidence_count": 1,
            "unevaluated_evidence_ids": ["evidence-001"],
        }
    )
    parsed = PatentTechnicalSynthesis(
        overall_summary=("No semantically evaluated relevant finding was available."),
        finding_summaries=[],
        limitations=["One evidence item remained unevaluated."],
    )

    client = FakeClient(parsed)
    result = OpenAIPatentTechnicalSynthesizer(
        client=client,
        model="gpt-5",
    ).synthesize(empty)

    assert result.synthesis.finding_summaries == []
    assert result.response_id is None
    assert result.elapsed_seconds == 0.0
    assert client.responses.calls == []
