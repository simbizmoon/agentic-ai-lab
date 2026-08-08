"""Semantic citation verification over research claim sets."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from app.budget import BudgetUsage, record_attempt
from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationBatchEvaluationResult,
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


_BATCH_FALLBACK_ERRORS = (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)


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

        pairs = []
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
                pairs.append(
                    (
                        claim,
                        citation,
                        evidence,
                    )
                )

        if not pairs:
            self._last_usage = BudgetUsage()
            return []

        batch_evaluate = getattr(
            self._evaluator,
            "evaluate_batch",
            None,
        )
        if callable(batch_evaluate):
            return self._verify_batch_capable(
                pairs=pairs,
                batch_evaluate=batch_evaluate,
            )

        return self._verify_sequential(pairs=pairs)

    def _verify_sequential(
        self,
        *,
        pairs: list[tuple[object, object, object]],
        initial_usage: BudgetUsage | None = None,
    ) -> list[ResearchCitationVerification]:
        """Preserve the original single-pair evaluator contract."""

        usage = initial_usage or BudgetUsage()
        verifications: list[
            ResearchCitationVerification
        ] = []

        for claim, citation, evidence in pairs:
            result = self._evaluator.evaluate(
                claim_text=claim.text,
                evidence_excerpt=evidence.excerpt,
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
                self._build_verification(
                    claim=claim,
                    citation=citation,
                    evidence=evidence,
                    judgment=result.judgment,
                    decision=result.decision,
                    response_id=result.response_id,
                )
            )

        self._last_usage = usage
        return verifications

    def _verify_batch_capable(
        self,
        *,
        pairs: list[tuple[object, object, object]],
        batch_evaluate: Callable[
            ...,
            SemanticCitationBatchEvaluationResult,
        ],
    ) -> list[ResearchCitationVerification]:
        """Use one batch call for all claim/citation pairs."""

        batch_items = [
            (
                f"item-{index:03d}",
                claim.text,
                evidence.excerpt,
            )
            for index, (claim, _citation, evidence)
            in enumerate(pairs, start=1)
        ]

        started = time.perf_counter()
        try:
            batch_result = batch_evaluate(
                citation_items=batch_items,
            )
        except _BATCH_FALLBACK_ERRORS:
            failed_usage = record_attempt(
                usage=BudgetUsage(),
                recorded_tokens=0,
                elapsed_seconds=max(
                    0.0,
                    time.perf_counter() - started,
                ),
            )
            return self._verify_sequential(
                pairs=pairs,
                initial_usage=failed_usage,
            )

        batch_tokens = (
            batch_result.usage.total_tokens
            if batch_result.usage is not None
            else 0
        )
        self._last_usage = record_attempt(
            usage=BudgetUsage(),
            recorded_tokens=batch_tokens,
            elapsed_seconds=batch_result.elapsed_seconds,
        )

        return [
            self._build_verification(
                claim=claim,
                citation=citation,
                evidence=evidence,
                judgment=batch_result.judgments[item_id],
                decision=batch_result.decisions[item_id],
                response_id=batch_result.response_id,
            )
            for (item_id, _claim_text, _evidence_excerpt), (
                claim,
                citation,
                evidence,
            ) in zip(
                batch_items,
                pairs,
                strict=True,
            )
        ]

    def _build_verification(
        self,
        *,
        claim: object,
        citation: object,
        evidence: object,
        judgment: object,
        decision: object,
        response_id: str,
    ) -> ResearchCitationVerification:
        """Build code-owned citation provenance around one judgment."""

        verification_id = (
            self._verification_id_factory().strip()
        )

        if not verification_id:
            raise ValueError(
                "verification_id factory returned blank value"
            )

        return ResearchCitationVerification(
            verification_id=verification_id,
            claim_id=claim.claim_id,
            citation_id=citation.citation_id,
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            decision=decision,
            support_level=judgment.support_level,
            entailment_score=judgment.entailment_score,
            traceability_score=1.0,
            citation_accuracy_score=1.0,
            rationale=judgment.rationale,
            issues=judgment.issues,
            metadata={
                "response_id": response_id,
            },
        )
