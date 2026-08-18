"""Tests for patent technical synthesis verification schema."""

import pytest
from pydantic import ValidationError

from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.patent_technical_synthesis_verification import (
    PatentTechnicalOverallSummaryVerification,
    PatentTechnicalSummaryVerification,
    PatentTechnicalSynthesisVerificationResult,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def test_result_rejects_false_acceptance() -> None:
    partial = PatentTechnicalSummaryVerification(
        finding_id="finding-001",
        evidence_id="evidence-001",
        decision=ResearchCitationDecision.NEEDS_REVISION,
        support_level=SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
        entailment_score=0.7,
        rationale="The summary is broader than the evidence.",
        issues=["Broader scope."],
        response_id="resp-001",
    )
    overall = PatentTechnicalOverallSummaryVerification(
        decision=ResearchCitationDecision.VERIFIED,
        support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
        entailment_score=0.95,
        rationale="The overall summary is supported.",
        issues=[],
        response_id="resp-002",
        deterministic=False,
    )

    with pytest.raises(
        ValidationError,
        match="accepted must match",
    ):
        PatentTechnicalSynthesisVerificationResult(
            request_id="request-001",
            report_id="report-001",
            finding_verifications=[partial],
            overall_verification=overall,
            accepted=True,
        )
