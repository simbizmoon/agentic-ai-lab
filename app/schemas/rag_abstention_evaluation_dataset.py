"""Dataset schema for RAG abstention evaluation."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_abstention_evaluation import (
    RagAbstentionEvaluationCase,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


class RagAbstentionEvaluationDataset(BaseModel):
    """Documents and out-of-scope questions for abstention evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    dataset_id: str = Field(min_length=1)
    documents: list[RetrievalEvaluationDocument] = Field(
        min_length=1
    )
    cases: list[RagAbstentionEvaluationCase] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_dataset(
        self,
    ) -> RagAbstentionEvaluationDataset:
        """Validate unique dataset identifiers."""

        if not self.dataset_id.strip():
            raise ValueError(
                "abstention dataset ID must not be blank"
            )

        document_ids = [
            document.document_id
            for document in self.documents
        ]

        if len(document_ids) != len(set(document_ids)):
            raise ValueError(
                "abstention document IDs must be unique"
            )

        case_ids = [
            case.case_id
            for case in self.cases
        ]

        if len(case_ids) != len(set(case_ids)):
            raise ValueError(
                "abstention case IDs must be unique"
            )

        return self
