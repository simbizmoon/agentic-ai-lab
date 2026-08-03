"""Schemas for end-to-end RAG answer evaluation datasets."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


class RagAnswerEvaluationCase(BaseModel):
    """One end-to-end RAG answer evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    question: str
    expected_document_ids: list[str] = Field(min_length=1)
    top_k: int = Field(ge=1)
    minimum_score: float | None = None

    @model_validator(mode="after")
    def validate_case(self) -> RagAnswerEvaluationCase:
        """Validate one answer evaluation case."""

        if not self.case_id.strip():
            raise ValueError(
                "RAG answer evaluation case ID must not be blank"
            )

        if not self.question.strip():
            raise ValueError(
                "RAG answer evaluation question must not be blank"
            )

        if len(self.expected_document_ids) != len(
            set(self.expected_document_ids)
        ):
            raise ValueError(
                "expected document IDs must be unique"
            )

        if any(
            not document_id.strip()
            for document_id in self.expected_document_ids
        ):
            raise ValueError(
                "expected document IDs must not be blank"
            )

        return self


class RagAnswerEvaluationDataset(BaseModel):
    """Documents and questions for end-to-end RAG evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    dataset_id: str = Field(min_length=1)
    documents: list[RetrievalEvaluationDocument] = Field(
        min_length=1
    )
    cases: list[RagAnswerEvaluationCase] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_dataset(
        self,
    ) -> RagAnswerEvaluationDataset:
        """Validate document and case references."""

        if not self.dataset_id.strip():
            raise ValueError(
                "RAG answer evaluation dataset ID must not be blank"
            )

        document_ids = [
            document.document_id
            for document in self.documents
        ]

        if len(document_ids) != len(set(document_ids)):
            raise ValueError(
                "evaluation document IDs must be unique"
            )

        case_ids = [
            case.case_id
            for case in self.cases
        ]

        if len(case_ids) != len(set(case_ids)):
            raise ValueError(
                "RAG answer evaluation case IDs must be unique"
            )

        available_ids = set(document_ids)

        for case in self.cases:
            unknown_ids = (
                set(case.expected_document_ids)
                - available_ids
            )

            if unknown_ids:
                raise ValueError(
                    "answer evaluation cases must reference "
                    "dataset documents"
                )

        return self
