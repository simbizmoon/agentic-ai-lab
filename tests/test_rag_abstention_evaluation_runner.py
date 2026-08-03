"""Tests for the RAG abstention evaluation runner."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

from app.rag.document_retriever import DocumentRetriever
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.rag.question_answering_service import (
    RagQuestionAnsweringService,
)
from app.rag.rag_abstention_evaluation_runner import (
    RagAbstentionEvaluationRunner,
)
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.schemas.document_embedding import TextEmbedding
from app.schemas.rag_abstention_evaluation import (
    RagAbstentionEvaluationCase,
)
from app.schemas.rag_abstention_evaluation_dataset import (
    RagAbstentionEvaluationDataset,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Return document and unknown-query vectors."""

    @property
    def model_name(self) -> str:
        return "abstention-test-v1"

    @property
    def dimensions(self) -> int:
        return 2

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                model_name=self.model_name,
                dimensions=self.dimensions,
                vector=self._vector(text),
            )
            for text in texts
        ]

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.lower()

        if "python" in normalized:
            return [1.0, 0.0]

        if "unknown" in normalized:
            return [0.0, 1.0]

        return [1.0, 0.0]


class FakeResponses:
    """Return predefined Responses API results."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)

    def create(self, **kwargs: Any) -> object:
        answer = self._answers.pop(0)

        return SimpleNamespace(
            id="resp_abstention",
            output_text=answer,
        )


class FakeClient:
    """Minimal fake OpenAI client."""

    def __init__(self, answers: list[str]) -> None:
        self.responses = FakeResponses(answers)


def dataset() -> RagAbstentionEvaluationDataset:
    """Return one controlled abstention dataset."""

    return RagAbstentionEvaluationDataset(
        dataset_id="abstention-test",
        documents=[
            RetrievalEvaluationDocument(
                document_id="technology",
                text="Python programming.",
            )
        ],
        cases=[
            RagAbstentionEvaluationCase(
                case_id="unknown-case",
                question="Unknown astronomy question.",
                top_k=1,
                minimum_score=0.9,
                expected_markers=[
                    "insufficient evidence",
                    "cannot answer",
                ],
            )
        ],
    )


def make_runner(answer: str) -> RagAbstentionEvaluationRunner:
    """Create a controlled abstention runner."""

    retriever = DocumentRetriever(
        embedding_provider=ControlledEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )
    pipeline = RetrievalPipeline(
        retriever=retriever,
    )
    service = RagQuestionAnsweringService(
        client=FakeClient([answer]),
        model="test-answer-model",
        retrieval_pipeline=pipeline,
    )

    return RagAbstentionEvaluationRunner(
        service=service,
    )


def test_runner_passes_explicit_abstention() -> None:
    runner = make_runner(
        "There is insufficient evidence to answer."
    )

    result = runner.run(dataset=dataset())
    case = result.summary.cases[0]

    assert case.retrieved_document_ids == []
    assert case.cited_ids == []
    assert case.no_evidence is True
    assert case.no_citations is True
    assert case.abstention_detected is True
    assert case.passed is True
    assert result.summary.pass_rate == 1.0
    assert result.summary.abstention_rate == 1.0


def test_runner_fails_unsupported_confident_answer() -> None:
    runner = make_runner(
        "The answer is definitely Paris."
    )

    result = runner.run(dataset=dataset())
    case = result.summary.cases[0]

    assert case.no_evidence is True
    assert case.abstention_detected is False
    assert case.passed is False
    assert result.summary.pass_rate == 0.0


def test_runner_records_index_metadata() -> None:
    runner = make_runner(
        "I cannot answer from the provided evidence."
    )

    result = runner.run(dataset=dataset())

    assert result.dataset_id == "abstention-test"
    assert result.indexed_document_count == 1
    assert result.indexed_chunk_count == 1
    assert result.embedding_model == "abstention-test-v1"
    assert result.embedding_dimensions == 2
    assert result.answer_model == "test-answer-model"
