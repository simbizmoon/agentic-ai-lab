"""Schemas for retrieval evaluation datasets."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_evaluation import (
    RetrievalEvaluationCase,
)


class RetrievalEvaluationDocument(BaseModel):
    """One source document used in retrieval evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    document_id: str = Field(min_length=1)
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_document(
        self,
    ) -> RetrievalEvaluationDocument:
        """Reject blank document identifiers and text."""

        if not self.document_id.strip():
            raise ValueError(
                "evaluation document ID must not be blank"
            )

        if not self.text.strip():
            raise ValueError(
                "evaluation document text must not be blank"
            )

        return self


class RetrievalEvaluationDataset(BaseModel):
    """Documents and queries for one retrieval evaluation run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    dataset_id: str = Field(min_length=1)
    documents: list[RetrievalEvaluationDocument] = Field(
        min_length=1
    )
    cases: list[RetrievalEvaluationCase] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_dataset(
        self,
    ) -> RetrievalEvaluationDataset:
        """Ensure dataset IDs and references are consistent."""

        if not self.dataset_id.strip():
            raise ValueError(
                "retrieval evaluation dataset ID must not be blank"
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
                "retrieval evaluation case IDs must be unique"
            )

        available_document_ids = set(document_ids)

        for case in self.cases:
            unknown_ids = (
                set(case.expected_document_ids)
                - available_document_ids
            )

            if unknown_ids:
                raise ValueError(
                    "evaluation cases must reference dataset documents"
                )

        return self
