"""Development dataset for semantic answer coverage evaluation."""

from __future__ import annotations

from app.evals.answer_coverage_evaluation import (
    AnswerCoverageEvaluationCase,
    AnswerCoverageEvaluationDataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def build_answer_coverage_golden_dataset() -> AnswerCoverageEvaluationDataset:
    """Return a small balanced development dataset."""

    return AnswerCoverageEvaluationDataset(
        dataset_id="answer-coverage-golden-v1",
        version="1.0.0",
        cases=[
            AnswerCoverageEvaluationCase(
                case_id="mechanism-full",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "The system records cumulative usage after each operation.",
                    "Before another operation begins, usage is compared with the configured limit.",
                    "When the limit is exhausted, the system prevents additional operations from starting.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="mechanism-partial",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "The system records cumulative usage after each operation.",
                    "Usage statistics are included in the execution trace.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="mechanism-insufficient",
                question="How does a system enforce an execution budget?",
                objective=(
                    "Explain how usage is measured, compared with limits, "
                    "and used to stop later execution."
                ),
                claims=[
                    "Execution traces can be exported as JSON.",
                    "The system supports named execution profiles.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-full",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Keyword retrieval ranks passages using lexical term overlap.",
                    "Embedding retrieval ranks passages using vector-space semantic similarity.",
                    "Keyword matching favors exact wording, while embeddings can recover semantically similar wording that uses different terms.",
                ],
                expected_coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-partial",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Keyword retrieval ranks passages using lexical term overlap.",
                    "Embedding retrieval uses vector representations.",
                ],
                expected_coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            ),
            AnswerCoverageEvaluationCase(
                case_id="comparison-insufficient",
                question="How do keyword retrieval and embedding retrieval differ?",
                objective=(
                    "Compare the matching signal used by each approach "
                    "and explain the practical tradeoff."
                ),
                claims=[
                    "Search results can be cached.",
                    "Documents may contain metadata.",
                ],
                expected_coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            ),
        ],
    )
