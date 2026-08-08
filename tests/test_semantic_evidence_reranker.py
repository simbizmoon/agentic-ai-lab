"""Tests for semantic evidence reranking."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.budget import ExecutionBudget
from app.research.embedding_semantic_evidence_shortlister import (
    SemanticEvidenceShortlistItem,
)
from app.research.openai_evidence_relevance_evaluator import (
    EvidenceRelevanceEvaluationResult,
)
from app.research.paragraph_evidence_extractor import (
    ParagraphEvidenceCandidate,
)
from app.research.semantic_evidence_reranker import (
    SemanticEvidenceReranker,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.services.text_generation import TokenUsage


def judgment(
    level: EvidenceRelevanceLevel,
    score: float,
) -> EvidenceRelevanceJudgment:
    return EvidenceRelevanceJudgment(
        relevance_level=level,
        relevance_score=score,
        rationale="Controlled semantic relevance judgment.",
        issues=[],
    )


@dataclass
class ControlledEvaluator:
    """Return judgments keyed by evidence excerpt."""

    judgments: dict[
        str,
        tuple[EvidenceRelevanceLevel, float, int, float],
    ]

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        evidence_excerpt: str,
    ) -> EvidenceRelevanceEvaluationResult:
        level, score, tokens, elapsed = self.judgments[evidence_excerpt]
        return EvidenceRelevanceEvaluationResult(
            judgment=judgment(level, score),
            response_id=f"resp-{evidence_excerpt}",
            request_id=f"req-{evidence_excerpt}",
            usage=TokenUsage(
                input_tokens=max(tokens - 1, 0),
                cached_input_tokens=0,
                output_tokens=1 if tokens else 0,
                reasoning_tokens=0,
                total_tokens=tokens,
            ),
            elapsed_seconds=elapsed,
        )


def item(
    *,
    text: str,
    semantic_score: float,
    lexical_score: float,
    rank: int,
    start: int,
) -> SemanticEvidenceShortlistItem:
    candidate = ParagraphEvidenceCandidate(
        start=start,
        end=start + len(text),
        text=text,
        lexical_score=lexical_score,
    )
    return SemanticEvidenceShortlistItem(
        candidate=candidate,
        semantic_score=semantic_score,
        rank=rank,
    )


def generous_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_attempts=8,
        max_recorded_tokens=8_000,
        max_elapsed_seconds=60.0,
    )


def test_rerank_orders_direct_partial_irrelevant() -> None:
    direct = item(
        text="direct",
        semantic_score=0.70,
        lexical_score=0.10,
        rank=2,
        start=100,
    )
    partial = item(
        text="partial",
        semantic_score=0.95,
        lexical_score=0.90,
        rank=1,
        start=0,
    )
    irrelevant = item(
        text="irrelevant",
        semantic_score=0.99,
        lexical_score=0.99,
        rank=3,
        start=200,
    )
    evaluator = ControlledEvaluator(
        {
            "direct": (
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                0.80,
                10,
                0.1,
            ),
            "partial": (
                EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
                0.90,
                10,
                0.1,
            ),
            "irrelevant": (
                EvidenceRelevanceLevel.IRRELEVANT,
                0.05,
                10,
                0.1,
            ),
        }
    )
    reranker = SemanticEvidenceReranker(
        evaluator=evaluator,
        budget=generous_budget(),
    )

    result = reranker.rerank(
        question="Question",
        objective="Objective",
        shortlist=[partial, irrelevant, direct],
    )

    assert [
        ranked.shortlist_item.candidate.text
        for ranked in result.items
    ] == ["direct", "partial", "irrelevant"]
    assert result.usage.attempts == 3
    assert result.usage.recorded_tokens == 30
    assert result.budget_exhausted is False


def test_same_category_uses_judgment_then_embedding_score() -> None:
    higher_judgment = item(
        text="higher-judgment",
        semantic_score=0.50,
        lexical_score=0.10,
        rank=2,
        start=100,
    )
    higher_embedding = item(
        text="higher-embedding",
        semantic_score=0.95,
        lexical_score=0.90,
        rank=1,
        start=0,
    )
    evaluator = ControlledEvaluator(
        {
            "higher-judgment": (
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                0.90,
                1,
                0.1,
            ),
            "higher-embedding": (
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                0.80,
                1,
                0.1,
            ),
        }
    )

    result = SemanticEvidenceReranker(
        evaluator=evaluator,
        budget=generous_budget(),
    ).rerank(
        question="Question",
        objective="Objective",
        shortlist=[higher_embedding, higher_judgment],
    )

    assert result.items[0].shortlist_item is higher_judgment


def test_budget_exhaustion_keeps_unknown_before_irrelevant() -> None:
    first = item(
        text="known-irrelevant",
        semantic_score=0.99,
        lexical_score=0.99,
        rank=1,
        start=0,
    )
    second = item(
        text="unknown-best",
        semantic_score=0.90,
        lexical_score=0.10,
        rank=2,
        start=100,
    )
    third = item(
        text="unknown-next",
        semantic_score=0.80,
        lexical_score=0.20,
        rank=3,
        start=200,
    )
    evaluator = ControlledEvaluator(
        {
            "known-irrelevant": (
                EvidenceRelevanceLevel.IRRELEVANT,
                0.05,
                10,
                0.1,
            )
        }
    )
    reranker = SemanticEvidenceReranker(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=100,
            max_elapsed_seconds=10.0,
        ),
    )

    result = reranker.rerank(
        question="Question",
        objective="Objective",
        shortlist=[first, second, third],
    )

    assert result.budget_exhausted is True
    assert result.usage.attempts == 1
    assert [
        ranked.shortlist_item.candidate.text
        for ranked in result.items
    ] == [
        "unknown-best",
        "unknown-next",
        "known-irrelevant",
    ]
    assert result.items[0].judgment is None
    assert result.items[1].judgment is None


def test_successful_call_crossing_token_budget_is_retained() -> None:
    first = item(
        text="direct-crossing",
        semantic_score=0.8,
        lexical_score=0.1,
        rank=1,
        start=0,
    )
    second = item(
        text="not-called",
        semantic_score=0.7,
        lexical_score=0.1,
        rank=2,
        start=100,
    )
    evaluator = ControlledEvaluator(
        {
            "direct-crossing": (
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                0.9,
                11,
                0.1,
            )
        }
    )
    reranker = SemanticEvidenceReranker(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=8,
            max_recorded_tokens=10,
            max_elapsed_seconds=10.0,
        ),
    )

    result = reranker.rerank(
        question="Question",
        objective="Objective",
        shortlist=[first, second],
    )

    assert result.usage.recorded_tokens == 11
    assert result.budget_exhausted is True
    assert result.items[0].shortlist_item is first
    assert result.items[0].judgment is not None
    assert result.items[1].shortlist_item is second
    assert result.items[1].judgment is None


def test_non_budget_evaluator_error_propagates() -> None:
    class FailingEvaluator:
        def evaluate(
            self,
            *,
            question: str,
            objective: str,
            evidence_excerpt: str,
        ) -> EvidenceRelevanceEvaluationResult:
            raise RuntimeError("evaluator failed")

    reranker = SemanticEvidenceReranker(
        evaluator=FailingEvaluator(),
        budget=generous_budget(),
    )

    with pytest.raises(RuntimeError, match="evaluator failed"):
        reranker.rerank(
            question="Question",
            objective="Objective",
            shortlist=[
                item(
                    text="candidate",
                    semantic_score=0.5,
                    lexical_score=0.5,
                    rank=1,
                    start=0,
                )
            ],
        )


def test_empty_shortlist_does_not_call_evaluator() -> None:
    evaluator = ControlledEvaluator({})
    result = SemanticEvidenceReranker(
        evaluator=evaluator,
        budget=generous_budget(),
    ).rerank(
        question="Question",
        objective="Objective",
        shortlist=[],
    )

    assert result.items == []
    assert result.usage.attempts == 0
    assert result.budget_exhausted is False


@pytest.mark.parametrize(
    ("question", "objective", "message"),
    [
        (" ", "Objective", "question must not be blank"),
        ("Question", " ", "objective must not be blank"),
    ],
)
def test_rerank_rejects_blank_request_text(
    question: str,
    objective: str,
    message: str,
) -> None:
    reranker = SemanticEvidenceReranker(
        evaluator=ControlledEvaluator({}),
        budget=generous_budget(),
    )

    with pytest.raises(ValueError, match=message):
        reranker.rerank(
            question=question,
            objective=objective,
            shortlist=[],
        )
