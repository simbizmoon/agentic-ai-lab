"""Generative claim builder for the single-agent research pipeline."""

from __future__ import annotations

from typing import Protocol

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    ensure_within_budget,
    record_attempt,
)
from app.exceptions import ExecutionBudgetError
from app.research.openai_evidence_claim_generator import (
    GeneratedClaimProposalResult,
)
from app.schemas.research_claim import (
    ResearchCitation,
    ResearchClaim,
    ResearchClaimSet,
    ResearchClaimStatus,
    ResearchClaimType,
)
from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
)


class EvidenceClaimGeneratorProtocol(Protocol):
    """Generate one claim proposal from one evidence item."""

    def generate(
        self,
        evidence: ResearchEvidence,
    ) -> GeneratedClaimProposalResult: ...


class GenerativePipelineClaimBuilder:
    """Build traceable draft claims from generated claim proposals."""

    def __init__(
        self,
        *,
        generator: EvidenceClaimGeneratorProtocol,
        budget: ExecutionBudget | None = None,
    ) -> None:
        self._generator = generator
        self._budget = budget
        self._last_usage = BudgetUsage()

    @property
    def last_usage(self) -> BudgetUsage:
        """Return usage recorded by the most recent build."""

        return self._last_usage

    def build(
        self,
        evidence_set: ResearchEvidenceSet,
    ) -> ResearchClaimSet:
        """Generate one traceable draft claim per evidence item."""

        return self._build(
            evidence_set,
            start_position=1,
        )

    def build_incremental(
        self,
        evidence_set: ResearchEvidenceSet,
        *,
        start_position: int,
    ) -> ResearchClaimSet:
        """Generate claims with IDs continuing after existing claims."""

        if start_position < 1:
            raise ValueError(
                "start_position must be greater than zero"
            )

        return self._build(
            evidence_set,
            start_position=start_position,
        )

    def _build(
        self,
        evidence_set: ResearchEvidenceSet,
        *,
        start_position: int,
    ) -> ResearchClaimSet:
        claims: list[ResearchClaim] = []
        usage = BudgetUsage()

        for position, evidence in enumerate(
            evidence_set.ordered_evidence(),
            start=start_position,
        ):
            if self._budget is not None:
                try:
                    ensure_can_start_attempt(
                        budget=self._budget,
                        usage=usage,
                    )
                except ExecutionBudgetError:
                    break

            claim, result = self._claim(
                evidence=evidence,
                position=position,
            )
            claims.append(claim)

            if self._budget is not None:
                recorded_tokens = (
                    result.usage.total_tokens
                    if result.usage is not None
                    else 0
                )
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=recorded_tokens,
                    elapsed_seconds=result.elapsed_seconds,
                )

                try:
                    ensure_within_budget(
                        budget=self._budget,
                        usage=usage,
                    )
                except ExecutionBudgetError:
                    break

        self._last_usage = usage

        return ResearchClaimSet(
            request_id=evidence_set.request_id,
            evidence_set=evidence_set,
            claims=claims,
        )

    def _claim(
        self,
        *,
        evidence: ResearchEvidence,
        position: int,
    ) -> tuple[
        ResearchClaim,
        GeneratedClaimProposalResult,
    ]:
        """Generate one claim while preserving deterministic provenance."""

        result = self._generator.generate(evidence)
        proposal = result.proposal

        citation = ResearchCitation(
            citation_id=(
                f"{evidence.request_id}-citation-"
                f"{position:03d}"
            ),
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            document_id=evidence.document_id,
            excerpt=evidence.excerpt,
            start_character=evidence.start_character,
            end_character=evidence.end_character,
            metadata={
                "builder": "generative-pipeline",
            },
        )

        metadata = {
            "builder": "generative-pipeline",
            "generator_response_id": result.response_id,
        }

        if result.request_id is not None:
            metadata["generator_request_id"] = result.request_id

        claim = ResearchClaim(
            claim_id=(
                f"{evidence.request_id}-claim-"
                f"{position:03d}"
            ),
            request_id=evidence.request_id,
            task_id=evidence.task_id,
            text=proposal.text,
            claim_type=ResearchClaimType.FACTUAL,
            status=ResearchClaimStatus.DRAFT,
            confidence_score=evidence.confidence_score,
            citations=[citation],
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            rationale=proposal.rationale,
            metadata=metadata,
        )

        return claim, result
