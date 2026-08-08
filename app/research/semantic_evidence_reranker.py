"""LLM-assisted semantic reranking for shortlisted research evidence."""

from __future__ import annotations

import time
from dataclasses import dataclass
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
from app.research.embedding_semantic_evidence_shortlister import (
    SemanticEvidenceShortlistItem,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceBatchEvaluationResult,
    EvidenceRelevanceEvaluationResult,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)


class EvidenceRelevanceEvaluatorProtocol(Protocol):
    """Evaluate one evidence passage against a research request."""

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


@dataclass(frozen=True)
class SemanticEvidenceRerankItem:
    """One shortlisted candidate with optional LLM relevance judgment."""

    shortlist_item: SemanticEvidenceShortlistItem
    judgment: EvidenceRelevanceJudgment | None
    response_id: str | None = None
    request_id: str | None = None

    @property
    def evaluated(self) -> bool:
        """Return whether the candidate received an LLM judgment."""

        return self.judgment is not None


@dataclass(frozen=True)
class SemanticEvidenceRerankResult:
    """Ordered reranking output and accumulated LLM budget usage."""

    items: list[SemanticEvidenceRerankItem]
    usage: BudgetUsage
    budget_exhausted: bool


class SemanticEvidenceReranker:
    """Rerank embedding-shortlisted evidence using semantic judgments."""

    def __init__(
        self,
        *,
        evaluator: EvidenceRelevanceEvaluatorProtocol,
        budget: ExecutionBudget,
    ) -> None:
        self._evaluator = evaluator
        self._budget = budget

    @property
    def evaluator(self) -> EvidenceRelevanceEvaluatorProtocol:
        """Return the configured semantic evaluator."""

        return self._evaluator

    @property
    def budget(self) -> ExecutionBudget:
        """Return the configured LLM execution budget."""

        return self._budget

    def rerank(
        self,
        *,
        question: str,
        objective: str,
        shortlist: list[SemanticEvidenceShortlistItem],
    ) -> SemanticEvidenceRerankResult:
        """Evaluate candidates until budget exhaustion and rerank safely."""

        if not question.strip():
            raise ValueError("question must not be blank")
        if not objective.strip():
            raise ValueError("objective must not be blank")
        if not shortlist:
            return SemanticEvidenceRerankResult(
                items=[],
                usage=BudgetUsage(),
                budget_exhausted=False,
            )

        usage = BudgetUsage()
        evaluated: list[SemanticEvidenceRerankItem] = []
        budget_exhausted = False

        batch_evaluate = getattr(
            self._evaluator,
            "evaluate_batch",
            None,
        )
        if callable(batch_evaluate):
            try:
                ensure_can_start_attempt(
                    budget=self._budget,
                    usage=usage,
                )
            except ExecutionBudgetError:
                return SemanticEvidenceRerankResult(
                    items=sorted(
                        [
                            SemanticEvidenceRerankItem(
                                shortlist_item=item,
                                judgment=None,
                            )
                            for item in shortlist
                        ],
                        key=self._sort_key,
                    ),
                    usage=usage,
                    budget_exhausted=True,
                )

            batch_items = [
                (f"item-{index:03d}", item.candidate.text)
                for index, item in enumerate(shortlist, start=1)
            ]
            batch_started = time.perf_counter()
            try:
                batch_result: EvidenceRelevanceBatchEvaluationResult = (
                    batch_evaluate(
                        question=question,
                        objective=objective,
                        evidence_items=batch_items,
                    )
                )
            except _BATCH_FALLBACK_ERRORS:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=0,
                    elapsed_seconds=max(
                        0.0,
                        time.perf_counter() - batch_started,
                    ),
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
                    ensure_within_budget(
                        budget=self._budget,
                        usage=usage,
                    )
                except ExecutionBudgetError:
                    budget_exhausted = True

                evaluated = [
                    SemanticEvidenceRerankItem(
                        shortlist_item=shortlist_item,
                        judgment=batch_result.judgments[item_id],
                        response_id=batch_result.response_id,
                        request_id=batch_result.request_id,
                    )
                    for (item_id, _), shortlist_item in zip(
                        batch_items,
                        shortlist,
                        strict=True,
                    )
                ]
                return SemanticEvidenceRerankResult(
                    items=sorted(
                        evaluated,
                        key=self._sort_key,
                    ),
                    usage=usage,
                    budget_exhausted=budget_exhausted,
                )

        remaining: list[SemanticEvidenceRerankItem] = []
        for index, shortlist_item in enumerate(shortlist):
            try:
                ensure_can_start_attempt(
                    budget=self._budget,
                    usage=usage,
                )
            except ExecutionBudgetError:
                budget_exhausted = True
                remaining.extend(
                    SemanticEvidenceRerankItem(
                        shortlist_item=item,
                        judgment=None,
                    )
                    for item in shortlist[index:]
                )
                break

            result = self._evaluator.evaluate(
                question=question,
                objective=objective,
                evidence_excerpt=shortlist_item.candidate.text,
            )

            evaluated.append(
                SemanticEvidenceRerankItem(
                    shortlist_item=shortlist_item,
                    judgment=result.judgment,
                    response_id=result.response_id,
                    request_id=result.request_id,
                )
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

        ordered = sorted(
            [*evaluated, *remaining],
            key=self._sort_key,
        )

        return SemanticEvidenceRerankResult(
            items=ordered,
            usage=usage,
            budget_exhausted=budget_exhausted,
        )

    @staticmethod
    def _sort_key(
        item: SemanticEvidenceRerankItem,
    ) -> tuple[float | int, ...]:
        """Order direct, partial, unknown, then irrelevant evidence."""

        judgment = item.judgment
        shortlist_item = item.shortlist_item
        candidate = shortlist_item.candidate

        if judgment is None:
            bucket = 2
            relevance_score = 0.0
        elif (
            judgment.relevance_level
            is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
        ):
            bucket = 0
            relevance_score = judgment.relevance_score
        elif (
            judgment.relevance_level
            is EvidenceRelevanceLevel.PARTIALLY_RELEVANT
        ):
            bucket = 1
            relevance_score = judgment.relevance_score
        else:
            bucket = 3
            relevance_score = judgment.relevance_score

        return (
            bucket,
            -relevance_score,
            -shortlist_item.semantic_score,
            -candidate.lexical_score,
            candidate.start,
            candidate.end,
        )
