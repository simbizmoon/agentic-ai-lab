"""Deterministic retrieval quality evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.rag_evaluation import (
    RetrievalCaseEvaluation,
    RetrievalEvaluationCase,
    RetrievalEvaluationSummary,
)
from app.schemas.retrieval_result import RetrievalResult


def evaluate_retrieval_case(
    *,
    case: RetrievalEvaluationCase,
    results: Sequence[RetrievalResult],
) -> RetrievalCaseEvaluation:
    """Evaluate one ranked retrieval result list."""

    selected_results = list(results[:case.top_k])
    retrieved_document_ids = [
        result.chunk.document_id
        for result in selected_results
    ]

    expected_set = set(case.expected_document_ids)

    matched_document_ids: list[str] = []

    for document_id in retrieved_document_ids:
        if (
            document_id in expected_set
            and document_id not in matched_document_ids
        ):
            matched_document_ids.append(document_id)

    first_relevant_rank: int | None = None

    for rank, document_id in enumerate(
        retrieved_document_ids,
        start=1,
    ):
        if document_id in expected_set:
            first_relevant_rank = rank
            break

    recall_at_k = (
        len(matched_document_ids)
        / len(case.expected_document_ids)
    )

    reciprocal_rank = (
        0.0
        if first_relevant_rank is None
        else 1.0 / first_relevant_rank
    )

    return RetrievalCaseEvaluation(
        case_id=case.case_id,
        query=case.query,
        expected_document_ids=case.expected_document_ids,
        retrieved_document_ids=retrieved_document_ids,
        matched_document_ids=matched_document_ids,
        first_relevant_rank=first_relevant_rank,
        recall_at_k=recall_at_k,
        reciprocal_rank=reciprocal_rank,
        passed=bool(matched_document_ids),
    )


def summarize_retrieval_evaluations(
    cases: Sequence[RetrievalCaseEvaluation],
) -> RetrievalEvaluationSummary:
    """Calculate aggregate retrieval evaluation metrics."""

    case_list = list(cases)
    case_count = len(case_list)

    if case_count == 0:
        return RetrievalEvaluationSummary(
            cases=[],
            case_count=0,
            passed_count=0,
            pass_rate=0.0,
            mean_recall_at_k=0.0,
            mean_reciprocal_rank=0.0,
        )

    passed_count = sum(case.passed for case in case_list)

    return RetrievalEvaluationSummary(
        cases=case_list,
        case_count=case_count,
        passed_count=passed_count,
        pass_rate=passed_count / case_count,
        mean_recall_at_k=(
            sum(
                case.recall_at_k
                for case in case_list
            )
            / case_count
        ),
        mean_reciprocal_rank=(
            sum(
                case.reciprocal_rank
                for case in case_list
            )
            / case_count
        ),
    )
