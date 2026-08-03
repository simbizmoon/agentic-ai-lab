"""Tests for retrieval evaluation dataset schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.rag_evaluation import (
    RetrievalEvaluationCase,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDataset,
    RetrievalEvaluationDocument,
)


def document(
    document_id: str = "doc-1",
) -> RetrievalEvaluationDocument:
    """Return one evaluation document."""

    return RetrievalEvaluationDocument(
        document_id=document_id,
        text="Evaluation document text.",
        metadata={"source": "sample.txt"},
    )


def case(
    *,
    case_id: str = "case-1",
    expected_document_ids: list[str] | None = None,
) -> RetrievalEvaluationCase:
    """Return one evaluation case."""

    return RetrievalEvaluationCase(
        case_id=case_id,
        query="Find the document.",
        expected_document_ids=(
            expected_document_ids or ["doc-1"]
        ),
        top_k=2,
    )


def test_dataset_accepts_valid_data() -> None:
    dataset = RetrievalEvaluationDataset(
        dataset_id="dataset-1",
        documents=[document()],
        cases=[case()],
    )

    assert dataset.dataset_id == "dataset-1"
    assert len(dataset.documents) == 1
    assert len(dataset.cases) == 1


@pytest.mark.parametrize(
    ("document_id", "text"),
    [
        ("", "Document text."),
        ("   ", "Document text."),
        ("doc-1", ""),
        ("doc-1", "   "),
    ],
)
def test_document_rejects_blank_values(
    document_id: str,
    text: str,
) -> None:
    with pytest.raises(ValidationError):
        RetrievalEvaluationDocument(
            document_id=document_id,
            text=text,
        )


def test_dataset_rejects_duplicate_document_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="document IDs must be unique",
    ):
        RetrievalEvaluationDataset(
            dataset_id="dataset-1",
            documents=[
                document("doc-1"),
                document("doc-1"),
            ],
            cases=[case()],
        )


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="case IDs must be unique",
    ):
        RetrievalEvaluationDataset(
            dataset_id="dataset-1",
            documents=[document()],
            cases=[
                case(case_id="case-1"),
                case(case_id="case-1"),
            ],
        )


def test_dataset_rejects_unknown_expected_document() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference dataset documents",
    ):
        RetrievalEvaluationDataset(
            dataset_id="dataset-1",
            documents=[document()],
            cases=[
                case(
                    expected_document_ids=[
                        "missing-doc"
                    ]
                )
            ],
        )


def test_dataset_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        RetrievalEvaluationDataset(
            dataset_id="dataset-1",
            documents=[document()],
            cases=[case()],
            unknown_field="not allowed",
        )
