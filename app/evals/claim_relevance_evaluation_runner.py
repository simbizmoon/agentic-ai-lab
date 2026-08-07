"""Runner for claim relevance golden-dataset evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Protocol

from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceEvaluationResult,
)
from app.schemas.claim_relevance_evaluation import (
    ClaimRelevanceConfusionEntry,
    ClaimRelevanceEvaluationCase,
    ClaimRelevanceEvaluationCaseResult,
    ClaimRelevanceEvaluationDataset,
    ClaimRelevanceEvaluationRun,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


class ClaimRelevanceEvaluatorProtocol(Protocol):
    """Evaluator required by the claim relevance eval runner."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult:
        """Evaluate one request/claim pair."""


class ClaimRelevanceEvaluationRunner:
    """Evaluate a claim relevance judge on a golden dataset."""

    def __init__(
        self,
        *,
        evaluator: ClaimRelevanceEvaluatorProtocol,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError(
                "model must not be blank"
            )

        self._evaluator = evaluator
        self._model = model

    def run(
        self,
        *,
        dataset: ClaimRelevanceEvaluationDataset,
    ) -> ClaimRelevanceEvaluationRun:
        """Evaluate all cases in one claim relevance dataset."""

        results = [
            self._evaluate_case(case)
            for case in dataset.cases
        ]

        correct_count = sum(
            result.correct
            for result in results
        )
        case_count = len(results)

        confusion_counts = Counter(
            (
                result.expected_relevance_level,
                result.actual_relevance_level,
            )
            for result in results
        )

        confusion = [
            ClaimRelevanceConfusionEntry(
                expected=expected,
                actual=actual,
                count=count,
            )
            for (expected, actual), count
            in sorted(
                confusion_counts.items(),
                key=lambda item: (
                    item[0][0].value,
                    item[0][1].value,
                ),
            )
        ]

        false_directly_relevant_count = sum(
            (
                result.actual_relevance_level
                is ClaimRelevanceLevel.DIRECTLY_RELEVANT
                and result.expected_relevance_level
                is not ClaimRelevanceLevel.DIRECTLY_RELEVANT
            )
            for result in results
        )

        false_irrelevant_count = sum(
            (
                result.expected_relevance_level
                in {
                    ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                    ClaimRelevanceLevel.PARTIALLY_RELEVANT,
                }
                and result.actual_relevance_level
                is ClaimRelevanceLevel.IRRELEVANT
            )
            for result in results
        )

        accuracy = (
            correct_count / case_count
            if case_count
            else 0.0
        )

        return ClaimRelevanceEvaluationRun(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            model=self._model,
            case_count=case_count,
            correct_count=correct_count,
            accuracy=accuracy,
            false_directly_relevant_count=(
                false_directly_relevant_count
            ),
            false_irrelevant_count=false_irrelevant_count,
            results=results,
            confusion=confusion,
        )

    def _evaluate_case(
        self,
        case: ClaimRelevanceEvaluationCase,
    ) -> ClaimRelevanceEvaluationCaseResult:
        """Evaluate one golden case."""

        result = self._evaluator.evaluate(
            question=case.question,
            objective=case.objective,
            claim_text=case.claim,
        )

        actual = result.judgment.relevance_level

        return ClaimRelevanceEvaluationCaseResult(
            case_id=case.case_id,
            expected_relevance_level=(
                case.expected_relevance_level
            ),
            actual_relevance_level=actual,
            relevance_score=(
                result.judgment.relevance_score
            ),
            correct=(
                actual is case.expected_relevance_level
            ),
            rationale=result.judgment.rationale,
            issues=result.judgment.issues,
        )
