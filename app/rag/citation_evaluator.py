"""Deterministic citation usage evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.rag_evaluation import (
    CitationEvaluationResult,
)


def evaluate_citations(
    *,
    expected_citation_ids: Sequence[str],
    cited_ids: Sequence[str],
) -> CitationEvaluationResult:
    """Evaluate answer citations against expected citation IDs."""

    expected_list = list(
        dict.fromkeys(expected_citation_ids)
    )
    cited_list = list(dict.fromkeys(cited_ids))

    expected_set = set(expected_list)
    cited_set = set(cited_list)

    matched_ids = [
        citation_id
        for citation_id in expected_list
        if citation_id in cited_set
    ]
    missing_ids = [
        citation_id
        for citation_id in expected_list
        if citation_id not in cited_set
    ]
    unexpected_ids = [
        citation_id
        for citation_id in cited_list
        if citation_id not in expected_set
    ]

    if cited_list:
        precision = len(matched_ids) / len(cited_list)
    else:
        precision = 1.0 if not expected_list else 0.0

    if expected_list:
        recall = len(matched_ids) / len(expected_list)
    else:
        recall = 1.0 if not cited_list else 0.0

    passed = (
        not missing_ids
        and not unexpected_ids
    )

    return CitationEvaluationResult(
        expected_citation_ids=expected_list,
        cited_ids=cited_list,
        matched_ids=matched_ids,
        missing_ids=missing_ids,
        unexpected_ids=unexpected_ids,
        precision=precision,
        recall=recall,
        passed=passed,
    )
