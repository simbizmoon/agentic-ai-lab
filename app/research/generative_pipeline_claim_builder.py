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
    GeneratedClaimProposalBatchResult,
    GeneratedClaimProposalResult,
    StructuredClaimGenerationError,
)
from app.schemas.generated_claim_proposal import GeneratedClaimProposal
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
        self._last_api_usage = BudgetUsage()

    @property
    def last_usage(self) -> BudgetUsage:
        """Return logical evidence-item usage for the most recent build."""

        return self._last_usage

    @property
    def last_api_usage(self) -> BudgetUsage:
        """Return physical generator/API usage for observability."""

        return self._last_api_usage

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
        eligible: list[tuple[int, ResearchEvidence]] = []
        logical_usage = BudgetUsage()

        for position, evidence in enumerate(
            evidence_set.ordered_evidence(),
            start=start_position,
        ):
            if self._budget is not None:
                try:
                    ensure_can_start_attempt(
                        budget=self._budget,
                        usage=logical_usage,
                    )
                except ExecutionBudgetError:
                    break

            eligible.append((position, evidence))

            if self._budget is not None:
                logical_usage = record_attempt(
                    usage=logical_usage,
                    recorded_tokens=0,
                    elapsed_seconds=0.0,
                )

        if not eligible:
            self._last_usage = BudgetUsage()
            self._last_api_usage = BudgetUsage()
            return ResearchClaimSet(
                request_id=evidence_set.request_id,
                evidence_set=evidence_set,
                claims=[],
            )

        batch_generate = getattr(
            self._generator,
            "generate_batch",
            None,
        )

        if callable(batch_generate):
            batch_items = [
                (f"item-{index:03d}", evidence)
                for index, (_position, evidence)
                in enumerate(eligible, start=1)
            ]

            try:
                batch_result: GeneratedClaimProposalBatchResult = (
                    batch_generate(batch_items)
                )
            except StructuredClaimGenerationError:
                failed_api_usage = record_attempt(
                    usage=BudgetUsage(),
                    recorded_tokens=0,
                    elapsed_seconds=0.0,
                )
                return self._build_sequential(
                    evidence_set=evidence_set,
                    eligible=eligible,
                    initial_api_usage=failed_api_usage,
                )

            claims = [
                self._claim_from_proposal(
                    evidence=evidence,
                    position=position,
                    proposal=batch_result.proposals[item_id],
                    response_id=batch_result.response_id,
                    request_id=batch_result.request_id,
                )
                for (item_id, _batch_evidence), (
                    position,
                    evidence,
                ) in zip(
                    batch_items,
                    eligible,
                    strict=True,
                )
            ]

            recorded_tokens = (
                batch_result.usage.total_tokens
                if batch_result.usage is not None
                else 0
            )
            self._last_api_usage = record_attempt(
                usage=BudgetUsage(),
                recorded_tokens=recorded_tokens,
                elapsed_seconds=batch_result.elapsed_seconds,
            )
            self._last_usage = BudgetUsage(
                attempts=logical_usage.attempts,
                recorded_tokens=recorded_tokens,
                elapsed_seconds=batch_result.elapsed_seconds,
            )

            return ResearchClaimSet(
                request_id=evidence_set.request_id,
                evidence_set=evidence_set,
                claims=claims,
            )

        return self._build_sequential(
            evidence_set=evidence_set,
            eligible=eligible,
        )

    def _build_sequential(
        self,
        *,
        evidence_set: ResearchEvidenceSet,
        eligible: list[tuple[int, ResearchEvidence]],
        initial_api_usage: BudgetUsage | None = None,
    ) -> ResearchClaimSet:
        claims: list[ResearchClaim] = []
        logical_usage = BudgetUsage()
        api_usage = initial_api_usage or BudgetUsage()

        for position, evidence in eligible:
            if self._budget is not None:
                try:
                    ensure_can_start_attempt(
                        budget=self._budget,
                        usage=logical_usage,
                    )
                except ExecutionBudgetError:
                    break

            claim, result = self._claim(
                evidence=evidence,
                position=position,
            )
            claims.append(claim)

            recorded_tokens = (
                result.usage.total_tokens
                if result.usage is not None
                else 0
            )
            api_usage = record_attempt(
                usage=api_usage,
                recorded_tokens=recorded_tokens,
                elapsed_seconds=result.elapsed_seconds,
            )

            if self._budget is not None:
                logical_usage = record_attempt(
                    usage=logical_usage,
                    recorded_tokens=recorded_tokens,
                    elapsed_seconds=result.elapsed_seconds,
                )

                try:
                    ensure_within_budget(
                        budget=self._budget,
                        usage=logical_usage,
                    )
                except ExecutionBudgetError:
                    break

        self._last_usage = logical_usage
        self._last_api_usage = api_usage

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
        claim = self._claim_from_proposal(
            evidence=evidence,
            position=position,
            proposal=result.proposal,
            response_id=result.response_id,
            request_id=result.request_id,
        )
        return claim, result

    def _claim_from_proposal(
        self,
        *,
        evidence: ResearchEvidence,
        position: int,
        proposal: GeneratedClaimProposal,
        response_id: str,
        request_id: str | None,
    ) -> ResearchClaim:
        """Build code-owned provenance around one generated proposal."""

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
            "generator_response_id": response_id,
        }

        if request_id is not None:
            metadata["generator_request_id"] = request_id

        return ResearchClaim(
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
