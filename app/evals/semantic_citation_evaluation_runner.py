"""Runner for semantic citation golden-dataset evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Protocol

from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.schemas.semantic_citation_evaluation import (
    SemanticCitationConfusionEntry,
    SemanticCitationEvaluationCase,
    SemanticCitationEvaluationCaseResult,
    SemanticCitationEvaluationDataset,
    SemanticCitationEvaluationRun,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


class SemanticCitationEvaluatorProtocol(Protocol):
    """Evaluator required by the semantic citation eval runner."""

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        """Evaluate one claim/evidence pair."""


class SemanticCitationEvaluationRunner:
    """Evaluate a semantic citation judge on a golden dataset."""

    def __init__(
        self,
        *,
        evaluator: SemanticCitationEvaluatorProtocol,
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
        dataset: SemanticCitationEvaluationDataset,
    ) -> SemanticCitationEvaluationRun:
        """Evaluate all cases in one semantic citation dataset."""

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
                result.expected_support_level,
                result.actual_support_level,
            )
            for result in results
        )

        confusion = [
            SemanticCitationConfusionEntry(
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

        false_fully_supported_count = sum(
            (
                result.actual_support_level
                is SemanticCitationSupportLevel.FULLY_SUPPORTED
                and result.expected_support_level
                is not SemanticCitationSupportLevel.FULLY_SUPPORTED
            )
            for result in results
        )

        false_rejected_count = sum(
            (
                result.expected_support_level
                in {
                    SemanticCitationSupportLevel
                    .FULLY_SUPPORTED,
                    SemanticCitationSupportLevel
                    .PARTIALLY_SUPPORTED,
                }
                and result.actual_support_level
                in {
                    SemanticCitationSupportLevel.UNSUPPORTED,
                    SemanticCitationSupportLevel.CONTRADICTED,
                }
            )
            for result in results
        )

        accuracy = (
            correct_count / case_count
            if case_count
            else 0.0
        )

        return SemanticCitationEvaluationRun(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            model=self._model,
            case_count=case_count,
            correct_count=correct_count,
            accuracy=accuracy,
            false_fully_supported_count=(
                false_fully_supported_count
            ),
            false_rejected_count=false_rejected_count,
            results=results,
            confusion=confusion,
        )

    def _evaluate_case(
        self,
        case: SemanticCitationEvaluationCase,
    ) -> SemanticCitationEvaluationCaseResult:
        """Evaluate one golden case."""

        result = self._evaluator.evaluate(
            claim_text=case.claim,
            evidence_excerpt=case.evidence,
        )

        actual = result.judgment.support_level

        return SemanticCitationEvaluationCaseResult(
            case_id=case.case_id,
            expected_support_level=(
                case.expected_support_level
            ),
            actual_support_level=actual,
            entailment_score=(
                result.judgment.entailment_score
            ),
            correct=(
                actual is case.expected_support_level
            ),
            rationale=result.judgment.rationale,
            issues=result.judgment.issues,
        )
