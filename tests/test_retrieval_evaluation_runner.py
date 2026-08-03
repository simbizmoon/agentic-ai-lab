"""Tests for the retrieval evaluation runner."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.rag.document_retriever import DocumentRetriever
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.rag.retrieval_evaluation_runner import (
    RetrievalEvaluationRunner,
    RetrievalEvaluationRunnerError,
)
from app.schemas.document_embedding import TextEmbedding
from app.schemas.rag_evaluation import (
    RetrievalEvaluationCase,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDataset,
    RetrievalEvaluationDocument,
)


class TopicEmbeddingProvider(EmbeddingProvider):
    """Map evaluation topics to controlled vectors."""

    @property
    def model_name(self) -> str:
        return "evaluation-topic-v1"

    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=self._vector_for_text(text),
            )
            for text in texts
        ]

    def _vector_for_text(
        self,
        text: str,
    ) -> list[float]:
        normalized = text.lower()

        technology = sum(
            normalized.count(keyword)
            for keyword in (
                "python",
                "software",
                "programming",
            )
        )
        cooking = sum(
            normalized.count(keyword)
            for keyword in (
                "cooking",
                "recipe",
                "food",
            )
        )
        health = sum(
            normalized.count(keyword)
            for keyword in (
                "health",
                "exercise",
                "fitness",
            )
        )

        if technology == cooking == health == 0:
            return [1.0, 1.0, 1.0]

        return [
            float(technology),
            float(cooking),
            float(health),
        ]


def dataset() -> RetrievalEvaluationDataset:
    """Return a controlled retrieval evaluation dataset."""

    return RetrievalEvaluationDataset(
        dataset_id="test-dataset",
        documents=[
            RetrievalEvaluationDocument(
                document_id="technology",
                text="Python software programming.",
            ),
            RetrievalEvaluationDocument(
                document_id="cooking",
                text="Cooking food recipe.",
            ),
            RetrievalEvaluationDocument(
                document_id="health",
                text="Health exercise fitness.",
            ),
        ],
        cases=[
            RetrievalEvaluationCase(
                case_id="technology-case",
                query="Python programming software",
                expected_document_ids=["technology"],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="cooking-case",
                query="food cooking recipe",
                expected_document_ids=["cooking"],
                top_k=2,
            ),
            RetrievalEvaluationCase(
                case_id="health-case",
                query="exercise health fitness",
                expected_document_ids=["health"],
                top_k=2,
            ),
        ],
    )


def make_runner() -> RetrievalEvaluationRunner:
    """Create a deterministic evaluation runner."""

    retriever = DocumentRetriever(
        embedding_provider=TopicEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )

    return RetrievalEvaluationRunner(
        retriever=retriever,
    )


def test_runner_indexes_documents_and_evaluates_cases() -> None:
    result = make_runner().run(
        dataset=dataset(),
    )

    assert result.dataset_id == "test-dataset"
    assert result.indexed_document_count == 3
    assert result.indexed_chunk_count == 3
    assert result.embedding_model == "evaluation-topic-v1"
    assert result.embedding_dimensions == 3
    assert result.summary.case_count == 3


def test_runner_produces_perfect_controlled_metrics() -> None:
    result = make_runner().run(
        dataset=dataset(),
    )

    assert result.summary.passed_count == 3
    assert result.summary.pass_rate == 1.0
    assert result.summary.mean_recall_at_k == 1.0
    assert result.summary.mean_reciprocal_rank == 1.0


def test_runner_clears_existing_store_before_run() -> None:
    runner = make_runner()

    runner.retriever.index_document(
        document_id="old-document",
        text="Old unrelated document.",
    )

    result = runner.run(
        dataset=dataset(),
    )

    assert result.indexed_document_count == 3
    assert runner.retriever.indexed_chunk_count() == 3


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [
        (0, 0),
        (-1, 0),
        (10, -1),
        (10, 10),
        (10, 11),
    ],
)
def test_runner_rejects_invalid_chunk_configuration(
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    runner = make_runner()

    with pytest.raises(RetrievalEvaluationRunnerError):
        runner.run(
            dataset=dataset(),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
