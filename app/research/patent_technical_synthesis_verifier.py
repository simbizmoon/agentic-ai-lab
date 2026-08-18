"""Verify synthesized patent technical prose against its evidence."""

from __future__ import annotations

from typing import Protocol

from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.patent_technical_report import PatentTechnicalResearchReport
from app.schemas.patent_technical_synthesis import (
    PATENT_ZERO_FINDING_OVERALL_SUMMARY,
    PatentTechnicalSynthesis,
)
from app.schemas.patent_technical_synthesis_verification import (
    PatentTechnicalOverallSummaryVerification,
    PatentTechnicalSummaryVerification,
    PatentTechnicalSynthesisVerificationResult,
)

ZERO_FINDING_OVERALL_SUMMARY = PATENT_ZERO_FINDING_OVERALL_SUMMARY


class PatentTechnicalSupportEvaluatorProtocol(Protocol):
    """Evaluate support between synthesized prose and supplied evidence."""

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult: ...


class PatentTechnicalSynthesisVerifier:
    """Verify bounded patent synthesis with the generic entailment evaluator."""

    def __init__(
        self,
        *,
        evaluator: PatentTechnicalSupportEvaluatorProtocol,
    ) -> None:
        self._evaluator = evaluator

    def verify(
        self,
        *,
        report: PatentTechnicalResearchReport,
        synthesis: PatentTechnicalSynthesis,
    ) -> PatentTechnicalSynthesisVerificationResult:
        expected_ids = [finding.finding_id for finding in report.findings]
        summary_by_id = {item.finding_id: item for item in synthesis.finding_summaries}

        if len(summary_by_id) != len(expected_ids) or set(summary_by_id) != set(
            expected_ids
        ):
            raise ValueError(
                "synthesis finding IDs must exactly match report finding IDs"
            )

        finding_verifications = []
        for finding in report.findings:
            result = self._evaluator.evaluate(
                claim_text=summary_by_id[finding.finding_id].technical_summary,
                evidence_excerpt=finding.evidence.excerpt,
            )
            finding_verifications.append(
                PatentTechnicalSummaryVerification(
                    finding_id=finding.finding_id,
                    evidence_id=finding.evidence.evidence_id,
                    decision=result.decision,
                    support_level=result.judgment.support_level,
                    entailment_score=result.judgment.entailment_score,
                    rationale=result.judgment.rationale,
                    issues=result.judgment.issues,
                    response_id=result.response_id,
                )
            )

        if not report.findings:
            if synthesis.overall_summary.strip() != ZERO_FINDING_OVERALL_SUMMARY:
                raise ValueError(
                    "zero-finding overall summary must use deterministic text"
                )
            overall = PatentTechnicalOverallSummaryVerification(
                decision=ResearchCitationDecision.VERIFIED,
                support_level=None,
                entailment_score=1.0,
                rationale=(
                    "The zero-finding summary is deterministic report-state text."
                ),
                issues=[],
                response_id=None,
                deterministic=True,
            )
        else:
            combined_evidence = "\n\n".join(
                f"[{finding.finding_id}] {finding.evidence.excerpt}"
                for finding in report.findings
            )
            result = self._evaluator.evaluate(
                claim_text=synthesis.overall_summary,
                evidence_excerpt=combined_evidence,
            )
            overall = PatentTechnicalOverallSummaryVerification(
                decision=result.decision,
                support_level=result.judgment.support_level,
                entailment_score=result.judgment.entailment_score,
                rationale=result.judgment.rationale,
                issues=result.judgment.issues,
                response_id=result.response_id,
                deterministic=False,
            )

        accepted = overall.decision is ResearchCitationDecision.VERIFIED and all(
            item.decision is ResearchCitationDecision.VERIFIED
            for item in finding_verifications
        )

        return PatentTechnicalSynthesisVerificationResult(
            request_id=report.request_id,
            report_id=report.report_id,
            finding_verifications=finding_verifications,
            overall_verification=overall,
            accepted=accepted,
        )
