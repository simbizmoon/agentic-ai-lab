"""Budgeted semantic reranking for exact cross-source hybrid candidates."""

from __future__ import annotations

import time
from typing import Protocol

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    ensure_within_budget,
    record_attempt,
)
from app.exceptions import (
    ExecutionBudgetError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceBatchEvaluationResult,
    EvidenceRelevanceEvaluationResult,
)
from app.schemas.cross_source_evidence_reranking import (
    CrossSourceEvidenceRerankingRequest,
    CrossSourceEvidenceRerankingResult,
    CrossSourceEvidenceRerankItem,
    EvidenceRerankingEvaluationState,
    EvidenceRerankingUsage,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.hybrid_retrieval import HybridRetrievalMatch, HybridRetrievalResponse


class EvidenceRelevanceEvaluatorProtocol(Protocol):
    """Minimum injected evaluator interface for one evidence chunk."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult: ...


_BATCH_FALLBACK_ERRORS = (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)


class BoundedCrossSourceEvidenceReranker:
    """Evaluate a bounded hybrid candidate set and preserve every candidate."""

    def __init__(self, *, evaluator: EvidenceRelevanceEvaluatorProtocol) -> None:
        self._evaluator = evaluator

    @property
    def evaluator(self) -> EvidenceRelevanceEvaluatorProtocol:
        """Return the injected evaluator."""

        return self._evaluator

    def rerank(
        self,
        *,
        hybrid_response: HybridRetrievalResponse,
        request: CrossSourceEvidenceRerankingRequest,
    ) -> CrossSourceEvidenceRerankingResult:
        """Use batch-first evaluation with budgeted single-item fallback."""

        if not isinstance(hybrid_response, HybridRetrievalResponse):
            raise TypeError("hybrid_response must be a HybridRetrievalResponse")
        if not isinstance(request, CrossSourceEvidenceRerankingRequest):
            raise TypeError("request must be a CrossSourceEvidenceRerankingRequest")
        candidates = list(hybrid_response.matches)
        if len(candidates) > request.maximum_candidates:
            raise ValueError("hybrid candidates exceed maximum_candidates")
        if not candidates:
            return self._result(
                hybrid_response=hybrid_response,
                request=request,
                items=[],
                usage=BudgetUsage(),
                budget_exhausted=False,
            )

        budget = ExecutionBudget(
            max_attempts=request.budget.maximum_attempts,
            max_recorded_tokens=request.budget.maximum_recorded_tokens,
            max_elapsed_seconds=request.budget.maximum_elapsed_seconds,
        )
        usage = BudgetUsage()
        evaluated: list[CrossSourceEvidenceRerankItem] = []
        budget_exhausted = False

        batch_evaluate = getattr(self._evaluator, "evaluate_batch", None)
        if callable(batch_evaluate):
            item_ids = [f"item-{index:03d}" for index in range(1, len(candidates) + 1)]
            evidence_items = [
                (item_id, candidate.retrieval.chunk.text)
                for item_id, candidate in zip(item_ids, candidates, strict=True)
            ]
            started = time.perf_counter()
            try:
                ensure_can_start_attempt(budget=budget, usage=usage)
                batch_result: EvidenceRelevanceBatchEvaluationResult = batch_evaluate(
                    question=request.question,
                    objective=request.objective,
                    evidence_items=evidence_items,
                )
                if set(batch_result.judgments) != set(item_ids):
                    raise StructuredResponseParseError(
                        "batched reranking item IDs did not match candidates"
                    )
            except ExecutionBudgetError:
                budget_exhausted = True
                return self._result(
                    hybrid_response=hybrid_response,
                    request=request,
                    items=self._unevaluated(candidates),
                    usage=usage,
                    budget_exhausted=True,
                )
            except _BATCH_FALLBACK_ERRORS:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=0,
                    elapsed_seconds=max(0.0, time.perf_counter() - started),
                )
            else:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(
                        batch_result.usage.total_tokens
                        if batch_result.usage is not None
                        else 0
                    ),
                    elapsed_seconds=batch_result.elapsed_seconds,
                )
                try:
                    ensure_within_budget(budget=budget, usage=usage)
                except ExecutionBudgetError:
                    budget_exhausted = True
                evaluated = [
                    self._evaluated(
                        candidate=candidate,
                        result=batch_result,
                        judgment=batch_result.judgments[item_id],
                    )
                    for item_id, candidate in zip(item_ids, candidates, strict=True)
                ]
                return self._result(
                    hybrid_response=hybrid_response,
                    request=request,
                    items=evaluated,
                    usage=usage,
                    budget_exhausted=budget_exhausted,
                )

        remaining: list[CrossSourceEvidenceRerankItem] = []
        for index, candidate in enumerate(candidates):
            try:
                ensure_can_start_attempt(budget=budget, usage=usage)
            except ExecutionBudgetError:
                budget_exhausted = True
                remaining.extend(self._unevaluated(candidates[index:]))
                break

            result = self._evaluator.evaluate(
                question=request.question,
                objective=request.objective,
                evidence_excerpt=candidate.retrieval.chunk.text,
            )
            evaluated.append(
                CrossSourceEvidenceRerankItem(
                    hybrid_match=candidate,
                    evaluation_state=EvidenceRerankingEvaluationState.EVALUATED,
                    judgment=result.judgment,
                    response_id=result.response_id,
                    request_id=result.request_id,
                    final_rank=1,
                )
            )
            usage = record_attempt(
                usage=usage,
                recorded_tokens=(
                    result.usage.total_tokens if result.usage is not None else 0
                ),
                elapsed_seconds=result.elapsed_seconds,
            )
            try:
                ensure_within_budget(budget=budget, usage=usage)
            except ExecutionBudgetError:
                budget_exhausted = True
                remaining.extend(self._unevaluated(candidates[index + 1 :]))
                break

        return self._result(
            hybrid_response=hybrid_response,
            request=request,
            items=[*evaluated, *remaining],
            usage=usage,
            budget_exhausted=budget_exhausted,
        )

    @staticmethod
    def _evaluated(
        *,
        candidate: HybridRetrievalMatch,
        result: EvidenceRelevanceBatchEvaluationResult,
        judgment: EvidenceRelevanceJudgment,
    ) -> CrossSourceEvidenceRerankItem:
        return CrossSourceEvidenceRerankItem(
            hybrid_match=candidate,
            evaluation_state=EvidenceRerankingEvaluationState.EVALUATED,
            judgment=judgment,
            response_id=result.response_id,
            request_id=result.request_id,
            final_rank=1,
        )

    @staticmethod
    def _unevaluated(
        candidates: list[HybridRetrievalMatch],
    ) -> list[CrossSourceEvidenceRerankItem]:
        return [
            CrossSourceEvidenceRerankItem(
                hybrid_match=candidate,
                evaluation_state=EvidenceRerankingEvaluationState.UNEVALUATED,
                final_rank=1,
            )
            for candidate in candidates
        ]

    @classmethod
    def _result(
        cls,
        *,
        hybrid_response: HybridRetrievalResponse,
        request: CrossSourceEvidenceRerankingRequest,
        items: list[CrossSourceEvidenceRerankItem],
        usage: BudgetUsage,
        budget_exhausted: bool,
    ) -> CrossSourceEvidenceRerankingResult:
        ordered = sorted(items, key=cls._sort_key)
        ranked = [
            item.model_copy(update={"final_rank": rank})
            for rank, item in enumerate(ordered, start=1)
        ]
        evaluated_count = sum(
            item.evaluation_state is EvidenceRerankingEvaluationState.EVALUATED
            for item in ranked
        )
        return CrossSourceEvidenceRerankingResult(
            request=request,
            hybrid_response=hybrid_response,
            items=ranked,
            usage=EvidenceRerankingUsage(
                attempts=usage.attempts,
                recorded_tokens=usage.recorded_tokens,
                elapsed_seconds=usage.elapsed_seconds,
            ),
            budget_exhausted=budget_exhausted,
            candidate_count=len(hybrid_response.matches),
            evaluated_count=evaluated_count,
            unevaluated_count=len(ranked) - evaluated_count,
        )

    @staticmethod
    def _sort_key(item: CrossSourceEvidenceRerankItem) -> tuple[int | float | str, ...]:
        judgment = item.judgment
        if judgment is None:
            bucket = 2
            score = 0.0
        elif judgment.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT:
            bucket = 0
            score = judgment.relevance_score
        elif judgment.relevance_level is EvidenceRelevanceLevel.PARTIALLY_RELEVANT:
            bucket = 1
            score = judgment.relevance_score
        else:
            bucket = 3
            score = judgment.relevance_score
        return (
            bucket,
            -score,
            item.hybrid_match.retrieval.rank,
            item.hybrid_match.retrieval.chunk.chunk_id,
        )
