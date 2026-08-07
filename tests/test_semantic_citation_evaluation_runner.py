"""Tests for semantic citation evaluation runner."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.evals.semantic_citation_evaluation_runner import (
    SemanticCitationEvaluationRunner,
)
from app.research.openai_semantic_citation_evaluator import (
    SemanticCitationEvaluationResult,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.semantic_citation_evaluation import (
    SemanticCitationEvaluationCase,
    SemanticCitationEvaluationDataset,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)


@dataclass(frozen=True)
class Prediction:
    support_level: SemanticCitationSupportLevel
    score: float


class FakeSemanticCitationEvaluator:
    """Return controlled semantic predictions by claim text."""

    def __init__(
        self,
        predictions: dict[str, Prediction],
    ) -> None:
        self._predictions = predictions

    def evaluate(
        self,
        *,
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        del evidence_excerpt

        prediction = self._predictions[claim_text]

        decision = {
            SemanticCitationSupportLevel.FULLY_SUPPORTED: (
                ResearchCitationDecision.VERIFIED
            ),
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: (
                ResearchCitationDecision.NEEDS_REVISION
            ),
            SemanticCitationSupportLevel.UNSUPPORTED: (
                ResearchCitationDecision.REJECTED
            ),
            SemanticCitationSupportLevel.CONTRADICTED: (
                ResearchCitationDecision.REJECTED
            ),
        }[prediction.support_level]

        return SemanticCitationEvaluationResult(
            judgment=SemanticCitationJudgment(
                support_level=prediction.support_level,
                entailment_score=prediction.score,
                rationale="Controlled evaluation.",
                issues=[],
            ),
            decision=decision,
            response_id="response-test",
            request_id=None,
            usage=None,
            elapsed_seconds=0.01,
        )


def dataset() -> SemanticCitationEvaluationDataset:
    """Return a small controlled semantic dataset."""

    return SemanticCitationEvaluationDataset(
        dataset_id="semantic-test",
        version="1.0.0",
        cases=[
            SemanticCitationEvaluationCase(
                case_id="case-fully",
                claim="claim-fully",
                evidence="evidence-fully",
                expected_support_level=(
                    SemanticCitationSupportLevel.FULLY_SUPPORTED
                ),
                description="Expected fully supported.",
            ),
            SemanticCitationEvaluationCase(
                case_id="case-partial",
                claim="claim-partial",
                evidence="evidence-partial",
                expected_support_level=(
                    SemanticCitationSupportLevel
                    .PARTIALLY_SUPPORTED
                ),
                description="Expected partial support.",
            ),
            SemanticCitationEvaluationCase(
                case_id="case-unsupported",
                claim="claim-unsupported",
                evidence="evidence-unsupported",
                expected_support_level=(
                    SemanticCitationSupportLevel.UNSUPPORTED
                ),
                description="Expected unsupported.",
            ),
            SemanticCitationEvaluationCase(
                case_id="case-contradicted",
                claim="claim-contradicted",
                evidence="evidence-contradicted",
                expected_support_level=(
                    SemanticCitationSupportLevel.CONTRADICTED
                ),
                description="Expected contradiction.",
            ),
        ],
    )


def test_runner_reports_perfect_predictions() -> None:
    evaluator = FakeSemanticCitationEvaluator(
        {
            "claim-fully": Prediction(
                SemanticCitationSupportLevel.FULLY_SUPPORTED,
                1.0,
            ),
            "claim-partial": Prediction(
                SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
                0.5,
            ),
            "claim-unsupported": Prediction(
                SemanticCitationSupportLevel.UNSUPPORTED,
                0.1,
            ),
            "claim-contradicted": Prediction(
                SemanticCitationSupportLevel.CONTRADICTED,
                0.0,
            ),
        }
    )

    runner = SemanticCitationEvaluationRunner(
        evaluator=evaluator,
        model="test-model",
    )

    result = runner.run(dataset=dataset())

    assert result.case_count == 4
    assert result.correct_count == 4
    assert result.accuracy == pytest.approx(1.0)
    assert result.false_fully_supported_count == 0
    assert result.false_rejected_count == 0
    assert sum(
        entry.count
        for entry in result.confusion
    ) == 4


def test_runner_counts_false_fully_supported() -> None:
    evaluator = FakeSemanticCitationEvaluator(
        {
            "claim-fully": Prediction(
                SemanticCitationSupportLevel.FULLY_SUPPORTED,
                1.0,
            ),
            "claim-partial": Prediction(
                SemanticCitationSupportLevel.FULLY_SUPPORTED,
                0.9,
            ),
            "claim-unsupported": Prediction(
                SemanticCitationSupportLevel.UNSUPPORTED,
                0.1,
            ),
            "claim-contradicted": Prediction(
                SemanticCitationSupportLevel.CONTRADICTED,
                0.0,
            ),
        }
    )

    result = SemanticCitationEvaluationRunner(
        evaluator=evaluator,
        model="test-model",
    ).run(
        dataset=dataset()
    )

    assert result.correct_count == 3
    assert result.accuracy == pytest.approx(0.75)
    assert result.false_fully_supported_count == 1


def test_runner_counts_false_rejected() -> None:
    evaluator = FakeSemanticCitationEvaluator(
        {
            "claim-fully": Prediction(
                SemanticCitationSupportLevel.UNSUPPORTED,
                0.2,
            ),
            "claim-partial": Prediction(
                SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
                0.5,
            ),
            "claim-unsupported": Prediction(
                SemanticCitationSupportLevel.UNSUPPORTED,
                0.1,
            ),
            "claim-contradicted": Prediction(
                SemanticCitationSupportLevel.CONTRADICTED,
                0.0,
            ),
        }
    )

    result = SemanticCitationEvaluationRunner(
        evaluator=evaluator,
        model="test-model",
    ).run(
        dataset=dataset()
    )

    assert result.false_rejected_count == 1
    assert result.correct_count == 3


def test_runner_rejects_blank_model() -> None:
    evaluator = FakeSemanticCitationEvaluator({})

    with pytest.raises(
        ValueError,
        match="model must not be blank",
    ):
        SemanticCitationEvaluationRunner(
            evaluator=evaluator,
            model=" ",
        )
