"""Tests for the Korean retrieval evaluation dataset."""

from app.rag.korean_retrieval_evaluation_dataset import (
    build_korean_retrieval_evaluation_dataset,
)


def test_korean_dataset_has_documents_and_cases() -> None:
    dataset = build_korean_retrieval_evaluation_dataset()

    assert dataset.dataset_id == "korean-rag-smoke-v1"
    assert len(dataset.documents) == 4
    assert len(dataset.cases) == 5


def test_every_expected_document_exists() -> None:
    dataset = build_korean_retrieval_evaluation_dataset()

    document_ids = {
        document.document_id
        for document in dataset.documents
    }

    assert all(
        set(case.expected_document_ids).issubset(
            document_ids
        )
        for case in dataset.cases
    )


def test_korean_dataset_case_ids_are_stable() -> None:
    dataset = build_korean_retrieval_evaluation_dataset()

    assert [
        case.case_id
        for case in dataset.cases
    ] == [
        "seat-alert",
        "seat-behavior-change",
        "kimchi-stew",
        "python-automation",
        "health-exercise",
    ]
