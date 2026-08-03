"""Tests for Korean RAG abstention evaluation data."""

from app.rag.korean_rag_abstention_evaluation_dataset import (
    build_korean_rag_abstention_evaluation_dataset,
)


def test_dataset_has_expected_size() -> None:
    dataset = (
        build_korean_rag_abstention_evaluation_dataset()
    )

    assert dataset.dataset_id == (
        "korean-rag-abstention-smoke-v1"
    )
    assert len(dataset.documents) == 3
    assert len(dataset.cases) == 3


def test_all_cases_require_high_minimum_score() -> None:
    dataset = (
        build_korean_rag_abstention_evaluation_dataset()
    )

    assert all(
        case.minimum_score == 0.8
        for case in dataset.cases
    )


def test_case_ids_are_stable() -> None:
    dataset = (
        build_korean_rag_abstention_evaluation_dataset()
    )

    assert [
        case.case_id
        for case in dataset.cases
    ] == [
        "capital-of-france",
        "moon-distance",
        "company-ceo",
    ]
