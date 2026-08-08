"""Semantic citation verification over research claim sets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from app.budget import BudgetUsage, record_attempt
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationVerification,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_evidence import ResearchEvidenceSet


class SemanticCitationEvaluatorProtocol(Protocol):
    """Evaluate semantic support for one claim/evidence pair."""

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult: ...


class SemanticCitationVerificationService:
    """Verify every claim citation against its linked evidence."""

    def __init__(
        self,
        *,
        evaluator: SemanticCitationEvaluatorProtocol,
        verification_id_factory: (
            Callable[[], str] | None
        ) = None,
    ) -> None:
        self._evaluator = evaluator
        self._last_usage = BudgetUsage()
        self._verification_id_factory = (
            verification_id_factory
            or (
                lambda: (
                    "citation-verification-"
                    f"{uuid4()}"
                )
            )
        )

    @property
    def last_usage(self) -> BudgetUsage:
        return self._last_usage

    def verify(
        self,
        *,
        claim_set: ResearchClaimSet,
        evidence_set: ResearchEvidenceSet,
    ) -> list[ResearchCitationVerification]:
        """Verify citations in stable claim/citation order."""

        if claim_set.request_id != evidence_set.request_id:
            raise ValueError(
                "claim_set and evidence_set request_id "
                "must match"
            )

        evidence_by_id = {
            evidence.evidence_id: evidence
            for evidence in evidence_set.evidence
        }

        verifications: list[
            ResearchCitationVerification
        ] = []
        usage = BudgetUsage()

        for claim in claim_set.claims:
            for citation in claim.ordered_citations():
                evidence = evidence_by_id.get(
                    citation.evidence_id
                )

                if evidence is None:
                    raise ValueError(
                        "citation must reference "
                        "existing evidence"
                    )

                result = self._evaluator.evaluate(
                    claim_text=claim.text,
                    evidence_excerpt=evidence.excerpt,
                )

                verification_id = (
                    self._verification_id_factory().strip()
                )

                if not verification_id:
                    raise ValueError(
                        "verification_id factory "
                        "returned blank value"
                    )

                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(
                        result.usage.total_tokens
                        if result.usage is not None
                        else 0
                    ),
                    elapsed_seconds=result.elapsed_seconds,
                )
                verifications.append(
                    ResearchCitationVerification(
                        verification_id=verification_id,
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        evidence_id=evidence.evidence_id,
                        source_id=evidence.source_id,
                        decision=result.decision,
                        support_level=(
                            result.judgment.support_level
                        ),
                        entailment_score=(
                            result.judgment.entailment_score
                        ),
                        traceability_score=1.0,
                        citation_accuracy_score=1.0,
                        rationale=result.judgment.rationale,
                        issues=result.judgment.issues,
                        metadata={
                            "response_id": (
                                result.response_id
                            ),
                        },
                    )
                )

        self._last_usage = usage
        return verifications
