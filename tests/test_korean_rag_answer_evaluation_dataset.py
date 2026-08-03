"""Tests for the Korean RAG answer evaluation dataset."""

from app.rag.korean_rag_answer_evaluation_dataset import (
    build_korean_rag_answer_evaluation_dataset,
)


def test_dataset_contains_expected_cases() -> None:
    dataset = build_korean_rag_answer_evaluation_dataset()

    assert dataset.dataset_id == (
        "korean-rag-answer-smoke-v1"
    )
    assert len(dataset.documents) == 4
    assert len(dataset.cases) == 4


def test_all_cases_use_top_one_retrieval() -> None:
    dataset = build_korean_rag_answer_evaluation_dataset()

    assert all(
        case.top_k == 1
        for case in dataset.cases
    )


def test_case_ids_are_stable() -> None:
    dataset = build_korean_rag_answer_evaluation_dataset()

    assert [
        case.case_id
        for case in dataset.cases
    ] == [
        "seat-alert-answer",
        "kimchi-stew-answer",
        "python-answer",
        "exercise-answer",
    ]
