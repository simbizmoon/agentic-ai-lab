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
        application_number="WO2023APP001",
        priority_claims=(
            PatentPriorityClaim(
                priority_number="KR20250015704",
                priority_date=date(2025, 2, 7),
            ),
            PatentPriorityClaim(
                priority_number="US202563756683P",
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
    assert "result_status=findings_available" in output
    assert "synthesis_accepted=true" in output
    assert "=== VERIFIED METADATA / TECHNICAL RELEVANCE ===" in output
    assert "publication_number=WO2023156109A1" in output
    assert "application_number=WO2023APP001" in output
    assert "priority_claim_count=2" in output
    assert "priority_claim[1].number=KR20250015704" in output
    assert "priority_claim[1].date=2025-02-07" in output
    assert "priority_claim[2].number=US202563756683P" in output
    assert "priority_claim[2].date=unknown" in output
    assert "ipc_classification_count=2" in output
    assert "ipc_classification[1].text=H02J 3/ 32 A I" in output
    assert "ipc_classification[2].text=H02J 3/ 46 A I" in output
    assert "cpc_classification_count=2" in output
    assert "cpc_classification[1].section=H" in output
    assert "cpc_classification[1].class_number=02" in output
    assert "cpc_classification[1].subclass=J" in output
    assert "cpc_classification[1].main_group=3" in output
    assert "cpc_classification[1].subgroup=32" in output
    assert "cpc_classification[2].subgroup=46" in output
    assert "applicant_count=1" in output
    assert "applicant[1].name=Seat Research Institute" in output
    assert "inventor_count=2" in output
    assert "inventor[1].name=HEO, Sewan" in output
    assert "inventor[2].name=KU, Tai-yeon" in output
    assert "relevance_level=directly_relevant" in output
    assert "=== EVIDENCE / PROVENANCE ===" in output
    assert "excerpt=A pressure sensor detects seat occupancy." in output
    assert "=== SYNTHESIS ===" in output
    assert "=== SUPPORT VERIFICATION ===" in output
    assert "overall_support_level=fully_supported" in output
    assert "=== SCOPE NOTICE ===" in output
    assert "no patent-law conclusion" in output


def test_handler_renders_missing_application_number_as_unknown(capsys) -> None:
    result = build_result()
    finding = result.synthesis.report.findings[0].model_copy(
        update={
            "application_number": None,
            "priority_claims": (),
            "ipc_classifications": (),
            "cpc_classifications": (),
            "applicants": (),
            "inventors": (),
        }
    )
    report = result.synthesis.report.model_copy(update={"findings": [finding]})
    runtime = FakeRuntime(
        SimpleNamespace(
            synthesis=SimpleNamespace(
                report=report,
                synthesis=result.synthesis.synthesis,
            ),
            verification=result.verification,
        )
    )
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
    assert "publication_number=WO2023156109A1" in output
    assert "application_number=unknown" in output
    assert "priority_claim_count=0" in output
    assert "ipc_classification_count=0" in output
    assert "cpc_classification_count=0" in output
    assert "applicant_count=0" in output
    assert "inventor_count=0" in output


def test_handler_renders_zero_finding_as_not_applicable(capsys) -> None:
    report = PatentTechnicalResearchReport(
        report_id="report-zero",
        request_id="request-zero",
        task_id="patent-technical-relevance",
        question="How does an unavailable mechanism work?",
        objective="Identify technically relevant patent publications.",
        prior_art_cutoff_date=date(2026, 8, 18),
        title="Patent Technical Relevance Report",
        findings=[],
        unevaluated_evidence_ids=[],
        finding_count=0,
        source_count=0,
        document_count=0,
        verified_record_count=0,
        input_evidence_count=0,
        executed_query_purpose="primary",
        executed_cql='ta all "unavailable mechanism"',
        scope_notice="Technical relevance only; no patent-law conclusion.",
        builder="deterministic-patent-technical-report-builder",
    )
    synthesis = PatentTechnicalSynthesis(
        overall_summary=("No semantically evaluated relevant finding was available."),
        finding_summaries=[],
        limitations=[],
    )
    verification = PatentTechnicalSynthesisVerificationResult(
        request_id="request-zero",
        report_id="report-zero",
        finding_verifications=[],
        overall_verification=PatentTechnicalOverallSummaryVerification(
            decision=ResearchCitationDecision.VERIFIED,
            support_level=None,
            entailment_score=1.0,
            rationale=("The zero-finding summary is deterministic report-state text."),
            issues=[],
            response_id=None,
            deterministic=True,
        ),
        accepted=True,
    )
    runtime = FakeRuntime(
        SimpleNamespace(
            synthesis=SimpleNamespace(
                report=report,
                synthesis=SimpleNamespace(synthesis=synthesis),
            ),
            verification=SimpleNamespace(verification=verification),
        )
    )
    request = PatentResearchRequest(
        question="How does an unavailable mechanism work?",
        objective="Identify technically relevant patent publications.",
    )

    value = PatentResearchCliHandler(
        runtime_factory=lambda: runtime,  # type: ignore[arg-type]
        request_id_factory=lambda: "request-zero",
    )(request)

    output = capsys.readouterr().out
    assert value == 0
    assert "result_status=no_relevant_findings" in output
    assert "synthesis_accepted=not_applicable" in output
    assert "verification_status=not_applicable" in output
    assert "accepted=true" not in output
    assert "overall_decision=verified" not in output
