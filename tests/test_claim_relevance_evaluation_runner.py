"""Tests for claim relevance evaluation runner."""

from __future__ import annotations

from app.evals.claim_relevance_evaluation_runner import (
    ClaimRelevanceEvaluationRunner,
)
from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceEvaluationResult,
)
from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationDataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)


class FakeEvaluator:
    def __init__(
        self,
        levels: list[ClaimRelevanceLevel],
    ) -> None:
        self._levels = iter(levels)

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult:
        del question, objective, claim_text
        level = next(self._levels)
        return ClaimRelevanceEvaluationResult(
            judgment=ClaimRelevanceJudgment(
                relevance_level=level,
                relevance_score=0.5,
                rationale="Controlled test judgment.",
                issues=[],
            ),
            response_id="resp-test",
            request_id=None,
            usage=None,
            elapsed_seconds=0.01,
        )


def dataset() -> ClaimRelevanceEvaluationDataset:
    question = "How does the system control tool execution?"
    objective = "Explain the tool execution controls."
    return ClaimRelevanceEvaluationDataset(
        dataset_id="test-dataset",
        version="1.0.0",
        cases=[
            ClaimRelevanceEvaluationCase(
                case_id="direct",
                question=question,
                objective=objective,
                claim="It limits tool calls.",
                expected_relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                description="Direct.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="partial",
                question=question,
                objective=objective,
                claim="Tool calls can cost money.",
                expected_relevance_level=ClaimRelevanceLevel.PARTIALLY_RELEVANT,
                description="Partial.",
            ),
            ClaimRelevanceEvaluationCase(
                case_id="irrelevant",
                question=question,
                objective=objective,
                claim="The UI has a navigation bar.",
                expected_relevance_level=ClaimRelevanceLevel.IRRELEVANT,
                description="Irrelevant.",
            ),
        ],
    )


def test_runner_counts_correct_predictions() -> None:
    runner = ClaimRelevanceEvaluationRunner(
        evaluator=FakeEvaluator(
            [
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                ClaimRelevanceLevel.PARTIALLY_RELEVANT,
                ClaimRelevanceLevel.IRRELEVANT,
            ]
        ),
        model="gpt-5",
    )
    result = runner.run(dataset=dataset())

    assert result.case_count == 3
    assert result.correct_count == 3
    assert result.accuracy == 1.0
    assert result.false_directly_relevant_count == 0
    assert result.false_irrelevant_count == 0


def test_runner_counts_false_directly_relevant() -> None:
    runner = ClaimRelevanceEvaluationRunner(
        evaluator=FakeEvaluator(
            [
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
            ]
        ),
        model="gpt-5",
    )
    result = runner.run(dataset=dataset())

    assert result.false_directly_relevant_count == 2


def test_runner_counts_false_irrelevant() -> None:
    runner = ClaimRelevanceEvaluationRunner(
        evaluator=FakeEvaluator(
            [
                ClaimRelevanceLevel.IRRELEVANT,
                ClaimRelevanceLevel.IRRELEVANT,
                ClaimRelevanceLevel.IRRELEVANT,
            ]
        ),
        model="gpt-5",
    )
    result = runner.run(dataset=dataset())

    assert result.false_irrelevant_count == 2


def test_runner_builds_confusion_counts() -> None:
    runner = ClaimRelevanceEvaluationRunner(
        evaluator=FakeEvaluator(
            [
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                ClaimRelevanceLevel.IRRELEVANT,
            ]
        ),
        model="gpt-5",
    )
    result = runner.run(dataset=dataset())

    assert sum(entry.count for entry in result.confusion) == 3
    assert len(result.confusion) == 3
