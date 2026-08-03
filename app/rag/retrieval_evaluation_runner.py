"""Run retrieval evaluation datasets against a Retriever."""

from __future__ import annotations

from app.rag.document_retriever import DocumentRetriever
from app.rag.retrieval_evaluator import (
    evaluate_retrieval_case,
    summarize_retrieval_evaluations,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDataset,
)
from app.schemas.retrieval_evaluation_run import (
    RetrievalEvaluationRunResult,
)


class RetrievalEvaluationRunnerError(RuntimeError):
    """Raised when a retrieval evaluation run fails."""


class RetrievalEvaluationRunner:
    """Index a dataset and evaluate all retrieval cases."""

    def __init__(
        self,
        *,
        retriever: DocumentRetriever,
    ) -> None:
        self._retriever = retriever

    @property
    def retriever(self) -> DocumentRetriever:
        """Return the configured Retriever."""

        return self._retriever

    def run(
        self,
        *,
        dataset: RetrievalEvaluationDataset,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> RetrievalEvaluationRunResult:
        """Index the dataset and evaluate all queries."""

        if chunk_size <= 0:
            raise RetrievalEvaluationRunnerError(
                "chunk_size must be greater than zero"
            )

        if chunk_overlap < 0:
            raise RetrievalEvaluationRunnerError(
                "chunk_overlap must not be negative"
            )

        if chunk_overlap >= chunk_size:
            raise RetrievalEvaluationRunnerError(
                "chunk_overlap must be smaller than chunk_size"
            )

        self.retriever.clear()

        indexed_chunk_count = 0

        for document in dataset.documents:
            index_result = self.retriever.index_document(
                document_id=document.document_id,
                text=document.text,
                metadata=document.metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            indexed_chunk_count += index_result.chunk_count

        case_evaluations = []

        for case in dataset.cases:
            results = self.retriever.retrieve(
                query=case.query,
                top_k=case.top_k,
            )

            evaluation = evaluate_retrieval_case(
                case=case,
                results=results,
            )
            case_evaluations.append(evaluation)

        summary = summarize_retrieval_evaluations(
            case_evaluations
        )

        return RetrievalEvaluationRunResult(
            dataset_id=dataset.dataset_id,
            indexed_document_count=len(dataset.documents),
            indexed_chunk_count=indexed_chunk_count,
            embedding_model=(
                self.retriever.embedding_provider.model_name
            ),
            embedding_dimensions=(
                self.retriever.embedding_provider.dimensions
            ),
            summary=summary,
        )
