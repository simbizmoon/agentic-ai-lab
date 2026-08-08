"""Runner for semantic answer coverage golden-dataset evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Protocol

from app.evals.answer_coverage_evaluation import (
    AnswerCoverageConfusionEntry,
    AnswerCoverageEvaluationCase,
    AnswerCoverageEvaluationCaseResult,
    AnswerCoverageEvaluationDataset,
    AnswerCoverageEvaluationRun,
)
from app.research.openai_answer_coverage_evaluator import (
    AnswerCoverageEvaluationResult,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


class AnswerCoverageEvaluatorProtocol(Protocol):
    """Evaluator required by the answer coverage eval runner."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claims: list[str],
    ) -> AnswerCoverageEvaluationResult:
        """Evaluate one request/claim-set pair."""


class AnswerCoverageEvaluationRunner:
    """Evaluate an answer coverage judge on a golden dataset."""

    def __init__(
        self,
        *,
        evaluator: AnswerCoverageEvaluatorProtocol,
        model: str,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")

        self._evaluator = evaluator
        self._model = model

    def run(
        self,
        *,
        dataset: AnswerCoverageEvaluationDataset,
    ) -> AnswerCoverageEvaluationRun:
        """Evaluate all cases in one answer coverage dataset."""

        results = [
            self._evaluate_case(case)
            for case in dataset.cases
        ]

        correct_count = sum(result.correct for result in results)
        case_count = len(results)

        confusion_counts = Counter(
            (
                result.expected_coverage_level,
                result.actual_coverage_level,
            )
            for result in results
        )

        confusion = [
            AnswerCoverageConfusionEntry(
                expected=expected,
                actual=actual,
                count=count,
            )
            for (expected, actual), count in sorted(
                confusion_counts.items(),
                key=lambda item: (
                    item[0][0].value,
                    item[0][1].value,
                ),
            )
        ]

        false_fully_covered_count = sum(
            (
                result.actual_coverage_level
                is AnswerCoverageLevel.FULLY_COVERED
                and result.expected_coverage_level
                is not AnswerCoverageLevel.FULLY_COVERED
            )
            for result in results
        )

        false_insufficient_count = sum(
            (
                result.actual_coverage_level
                is AnswerCoverageLevel.INSUFFICIENT
                and result.expected_coverage_level
                is not AnswerCoverageLevel.INSUFFICIENT
            )
            for result in results
        )

        accuracy = (
            correct_count / case_count
            if case_count
            else 0.0
        )

        return AnswerCoverageEvaluationRun(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            model=self._model,
            case_count=case_count,
            correct_count=correct_count,
            accuracy=accuracy,
            false_fully_covered_count=false_fully_covered_count,
            false_insufficient_count=false_insufficient_count,
            results=results,
            confusion=confusion,
        )

    def _evaluate_case(
        self,
        case: AnswerCoverageEvaluationCase,
    ) -> AnswerCoverageEvaluationCaseResult:
        """Evaluate one golden case."""

        result = self._evaluator.evaluate(
            question=case.question,
            objective=case.objective,
            claims=case.claims,
        )

        actual = result.judgment.coverage_level

        return AnswerCoverageEvaluationCaseResult(
            case_id=case.case_id,
            expected_coverage_level=(
                case.expected_coverage_level
            ),
            actual_coverage_level=actual,
            coverage_score=result.judgment.coverage_score,
            correct=(
                actual is case.expected_coverage_level
            ),
            covered_aspects=result.judgment.covered_aspects,
            missing_aspects=result.judgment.missing_aspects,
            rationale=result.judgment.rationale,
        )
