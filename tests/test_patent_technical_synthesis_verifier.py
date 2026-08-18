"""Tests for patent technical synthesis support verification."""

from types import SimpleNamespace

import pytest

from app.research.patent_technical_synthesis_verifier import (
    ZERO_FINDING_OVERALL_SUMMARY,
    PatentTechnicalSynthesisVerifier,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.patent_source_metadata import (
    PatentMetadataVerificationState,
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
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)


class FakeEvaluator:
    def __init__(self, levels: list[SemanticCitationSupportLevel]) -> None:
        self.levels = list(levels)
        self.calls: list[dict[str, str]] = []

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> object:
        self.calls.append(
            {
                "claim_text": claim_text,
                "evidence_excerpt": evidence_excerpt,
            }
        )
        level = self.levels.pop(0)
        decision = {
            SemanticCitationSupportLevel.FULLY_SUPPORTED: (
                ResearchCitationDecision.VERIFIED
            ),
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: (
                ResearchCitationDecision.NEEDS_REVISION
            ),
            SemanticCitationSupportLevel.UNSUPPORTED: (
                ResearchCitationDecision.REJECTED
            ),
            SemanticCitationSupportLevel.CONTRADICTED: (
                ResearchCitationDecision.REJECTED
            ),
        }[level]
        return SimpleNamespace(
            judgment=SemanticCitationJudgment(
                support_level=level,
                entailment_score=0.95,
                rationale="Judged against supplied evidence.",
                issues=[],
            ),
            decision=decision,
            response_id=f"resp-{len(self.calls):03d}",
        )


def report() -> PatentTechnicalResearchReport:
    excerpt = "A seat pressure sensor detects occupancy."
    finding = PatentTechnicalFinding(
        finding_id="request-001-patent-finding-001",
        publication_number="CN122100948A",
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
        scope_notice="Technical relevance only.",
        builder="deterministic-patent-technical-report-builder",
    )


def synthesis() -> PatentTechnicalSynthesis:
    return PatentTechnicalSynthesis(
        overall_summary="The publication describes seat occupancy sensing.",
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


def test_verifier_accepts_only_fully_supported_synthesis() -> None:
    evaluator = FakeEvaluator(
        [
            SemanticCitationSupportLevel.FULLY_SUPPORTED,
            SemanticCitationSupportLevel.FULLY_SUPPORTED,
        ]
    )
    value = PatentTechnicalSynthesisVerifier(evaluator=evaluator).verify(
        report=report(),
        synthesis=synthesis(),
    )

    assert value.accepted is True
    assert len(value.finding_verifications) == 1
    assert len(evaluator.calls) == 2


def test_verifier_marks_partial_summary_needs_revision() -> None:
    evaluator = FakeEvaluator(
        [
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
            SemanticCitationSupportLevel.FULLY_SUPPORTED,
        ]
    )
    value = PatentTechnicalSynthesisVerifier(evaluator=evaluator).verify(
        report=report(),
        synthesis=synthesis(),
    )

    assert value.accepted is False
    assert value.finding_verifications[0].decision is (
        ResearchCitationDecision.NEEDS_REVISION
    )


def test_verifier_rejects_finding_id_drift() -> None:
    drifted = synthesis().model_copy(
        update={
            "finding_summaries": [
                PatentTechnicalFindingSummary(
                    finding_id="wrong-finding",
                    technical_summary="Summary.",
                )
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="finding IDs must exactly match",
    ):
        PatentTechnicalSynthesisVerifier(evaluator=FakeEvaluator([])).verify(
            report=report(),
            synthesis=drifted,
        )


def test_zero_finding_summary_is_deterministically_verified() -> None:
    empty_report = report().model_copy(
        update={
            "findings": [],
            "finding_count": 0,
            "source_count": 0,
            "input_evidence_count": 1,
            "unevaluated_evidence_ids": ["evidence-001"],
        }
    )
    empty_synthesis = PatentTechnicalSynthesis(
        overall_summary=ZERO_FINDING_OVERALL_SUMMARY,
        finding_summaries=[],
        limitations=["One evidence item remained unevaluated."],
    )
    evaluator = FakeEvaluator([])

    value = PatentTechnicalSynthesisVerifier(evaluator=evaluator).verify(
        report=empty_report,
        synthesis=empty_synthesis,
    )

    assert value.accepted is True
    assert value.overall_verification.deterministic is True
    assert evaluator.calls == []
