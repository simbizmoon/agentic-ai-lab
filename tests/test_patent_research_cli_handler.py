"""Tests for the patent research CLI adapter."""

from datetime import date
from types import SimpleNamespace

from app.research.patent_research_cli_handler import PatentResearchCliHandler
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.patent_research_request import PatentResearchRequest
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
from app.schemas.patent_technical_synthesis_verification import (
    PatentTechnicalOverallSummaryVerification,
    PatentTechnicalSummaryVerification,
    PatentTechnicalSynthesisVerificationResult,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


class FakeRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[PatentResearchRequest, str]] = []

    def execute(
        self,
        request: PatentResearchRequest,
        *,
        request_id: str,
        task_id: str = "patent-technical-relevance",
    ) -> object:
        self.calls.append((request, request_id))
        return self.result


def build_result() -> object:
    excerpt = "A pressure sensor detects seat occupancy."
    finding = PatentTechnicalFinding(
        finding_id="finding-001",
        publication_number="WO2023156109A1",
        title="VEHICLE SEAT",
        source_url="https://ops.epo.org/example",
        publication_date=date(2023, 8, 24),
        source_family=PatentSourceFamily.EPO_OPS,
        metadata_verification_state=PatentMetadataVerificationState.VERIFIED,
        relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.86,
        relevance_rationale="The excerpt directly describes seat occupancy.",
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
    report = PatentTechnicalResearchReport(
        report_id="report-001",
        request_id="request-001",
        task_id="patent-technical-relevance",
        question="How do pressure sensors detect seat occupancy?",
        objective="Identify technically relevant patent publications.",
        prior_art_cutoff_date=date(2026, 8, 18),
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
        scope_notice="Technical relevance only; no patent-law conclusion.",
        builder="deterministic-patent-technical-report-builder",
    )
    synthesis = PatentTechnicalSynthesis(
        overall_summary="The publication describes pressure-based seat sensing.",
        finding_summaries=[
            PatentTechnicalFindingSummary(
                finding_id="finding-001",
                technical_summary=(
                    "The excerpt describes pressure-based occupancy sensing."
                ),
            )
        ],
        limitations=["Only the supplied abstract excerpt was analyzed."],
    )
    verification = PatentTechnicalSynthesisVerificationResult(
        request_id="request-001",
        report_id="report-001",
        finding_verifications=[
            PatentTechnicalSummaryVerification(
                finding_id="finding-001",
                evidence_id="evidence-001",
                decision=ResearchCitationDecision.VERIFIED,
                support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
                entailment_score=0.98,
                rationale="The summary is fully supported.",
                issues=[],
                response_id="resp-001",
            )
        ],
        overall_verification=PatentTechnicalOverallSummaryVerification(
            decision=ResearchCitationDecision.VERIFIED,
            support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
            entailment_score=0.98,
            rationale="The overall summary is fully supported.",
            issues=[],
            response_id="resp-002",
            deterministic=False,
        ),
        accepted=True,
    )
    synthesis_result = SimpleNamespace(
        report=report,
        synthesis=SimpleNamespace(synthesis=synthesis),
    )
    return SimpleNamespace(
        synthesis=synthesis_result,
        verification=SimpleNamespace(verification=verification),
    )


def test_handler_renders_separated_patent_result_sections(capsys) -> None:
    runtime = FakeRuntime(build_result())
    request = PatentResearchRequest(
        question="How do pressure sensors detect seat occupancy?",
        objective="Identify technically relevant patent publications.",
        prior_art_cutoff_date=date(2026, 8, 18),
        maximum_search_results=2,
        maximum_sources=1,
    )

    value = PatentResearchCliHandler(
        runtime_factory=lambda: runtime,  # type: ignore[arg-type]
        request_id_factory=lambda: "request-001",
    )(request)

    output = capsys.readouterr().out
    assert value == 0
    assert runtime.calls == [(request, "request-001")]
    assert "=== VERIFIED METADATA / TECHNICAL RELEVANCE ===" in output
    assert "publication_number=WO2023156109A1" in output
    assert "relevance_level=directly_relevant" in output
    assert "=== EVIDENCE / PROVENANCE ===" in output
    assert "excerpt=A pressure sensor detects seat occupancy." in output
    assert "=== SYNTHESIS ===" in output
    assert "=== SUPPORT VERIFICATION ===" in output
    assert "overall_support_level=fully_supported" in output
    assert "=== SCOPE NOTICE ===" in output
    assert "no patent-law conclusion" in output
