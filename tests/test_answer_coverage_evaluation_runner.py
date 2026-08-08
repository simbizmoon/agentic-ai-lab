"""Tests for semantic answer coverage evaluation runner."""


from app.evals.answer_coverage_evaluation import (
    AnswerCoverageEvaluationCase,
    AnswerCoverageEvaluationDataset,
)
from app.evals.answer_coverage_evaluation_runner import (
    AnswerCoverageEvaluationRunner,
)
from app.research.openai_answer_coverage_evaluator import (
    AnswerCoverageEvaluationResult,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
    AnswerCoverageLevel,
)


class FakeEvaluator:
    """Return configured answer coverage levels."""

    def __init__(self, levels: list[AnswerCoverageLevel]) -> None:
        self._levels = iter(levels)

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claims: list[str],
    ) -> AnswerCoverageEvaluationResult:
        level = next(self._levels)

        return AnswerCoverageEvaluationResult(
            judgment=AnswerCoverageJudgment(
                coverage_level=level,
                coverage_score=0.8,
                covered_aspects=["aspect"],
                missing_aspects=(
                    []
                    if level is AnswerCoverageLevel.FULLY_COVERED
                    else ["missing"]
                ),
                rationale="Synthetic judgment.",
            ),
            response_id="response-001",
            request_id=None,
            usage=None,
            elapsed_seconds=0.01,
        )


def test_runner_counts_directional_errors() -> None:
    dataset = AnswerCoverageEvaluationDataset(
        dataset_id="dataset",
        version="1",
        cases=[
            AnswerCoverageEvaluationCase(
                case_id="a",
                question="Q",
                objective="O",
                claims=["C"],
                expected_coverage_level=(
                    AnswerCoverageLevel.PARTIALLY_COVERED
                ),
            ),
            AnswerCoverageEvaluationCase(
                case_id="b",
                question="Q",
                objective="O",
                claims=["C"],
                expected_coverage_level=(
                    AnswerCoverageLevel.FULLY_COVERED
                ),
            ),
        ],
    )

    runner = AnswerCoverageEvaluationRunner(
        evaluator=FakeEvaluator(
            [
                AnswerCoverageLevel.FULLY_COVERED,
                AnswerCoverageLevel.INSUFFICIENT,
            ]
        ),
        model="test-model",
    )

    result = runner.run(dataset=dataset)

    assert result.case_count == 2
    assert result.correct_count == 0
    assert result.false_fully_covered_count == 1
    assert result.false_insufficient_count == 1
