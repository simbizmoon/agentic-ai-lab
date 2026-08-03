"""Tests for RAG answer evaluation dataset schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_answer_evaluation_dataset import (
    RagAnswerEvaluationCase,
    RagAnswerEvaluationDataset,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


def document(
    document_id: str = "doc-1",
) -> RetrievalEvaluationDocument:
    """Return one evaluation document."""

    return RetrievalEvaluationDocument(
        document_id=document_id,
        text="Document evidence.",
    )


def case(
    *,
    case_id: str = "case-1",
    expected_document_ids: list[str] | None = None,
) -> RagAnswerEvaluationCase:
    """Return one answer evaluation case."""

    return RagAnswerEvaluationCase(
        case_id=case_id,
        question="What does the document say?",
        expected_document_ids=(
            expected_document_ids or ["doc-1"]
        ),
        top_k=1,
    )


def test_dataset_accepts_valid_data() -> None:
    dataset = RagAnswerEvaluationDataset(
        dataset_id="dataset-1",
        documents=[document()],
        cases=[case()],
    )

    assert dataset.dataset_id == "dataset-1"
    assert len(dataset.cases) == 1


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_case_rejects_blank_question(
    question: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="question must not be blank",
    ):
        RagAnswerEvaluationCase(
            case_id="case-1",
            question=question,
            expected_document_ids=["doc-1"],
            top_k=1,
        )


def test_case_rejects_duplicate_expected_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="must be unique",
    ):
        RagAnswerEvaluationCase(
            case_id="case-1",
            question="Question?",
            expected_document_ids=[
                "doc-1",
                "doc-1",
            ],
            top_k=1,
        )


def test_dataset_rejects_unknown_document_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference dataset documents",
    ):
        RagAnswerEvaluationDataset(
            dataset_id="dataset-1",
            documents=[document()],
            cases=[
                case(
                    expected_document_ids=[
                        "missing-document"
                    ]
                )
            ],
        )


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="case IDs must be unique",
    ):
        RagAnswerEvaluationDataset(
            dataset_id="dataset-1",
            documents=[document()],
            cases=[
                case(case_id="case-1"),
                case(case_id="case-1"),
            ],
        )
