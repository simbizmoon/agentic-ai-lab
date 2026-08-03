"""Tests for the end-to-end RAG answer evaluation runner."""

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
from app.rag.rag_answer_evaluation_runner import (
    RagAnswerEvaluationRunner,
)
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.schemas.document_embedding import TextEmbedding
from app.schemas.rag_answer_evaluation_dataset import (
    RagAnswerEvaluationCase,
    RagAnswerEvaluationDataset,
)
from app.schemas.retrieval_evaluation_dataset import (
    RetrievalEvaluationDocument,
)


class KeywordEmbeddingProvider(EmbeddingProvider):
    """Create controlled technology and cooking vectors."""

    @property
    def model_name(self) -> str:
        return "answer-evaluation-v1"

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

        if (
            "python" in normalized
            or "programming" in normalized
        ):
            return [1.0, 0.0]

        if (
            "cooking" in normalized
            or "recipe" in normalized
        ):
            return [0.0, 1.0]

        return [1.0, 1.0]


class FakeResponses:
    """Return predefined answer responses."""

    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self._responses = list(responses)

    def create(self, **kwargs: Any) -> object:
        if not self._responses:
            raise RuntimeError("no fake response")

        response = self._responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


class FakeClient:
    """Minimal fake OpenAI client."""

    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self.responses = FakeResponses(responses)


def response(text: str) -> object:
    """Return one fake answer response."""

    return SimpleNamespace(
        id="resp_eval",
        output_text=text,
    )


def dataset() -> RagAnswerEvaluationDataset:
    """Return a controlled end-to-end dataset."""

    return RagAnswerEvaluationDataset(
        dataset_id="answer-evaluation-test",
        documents=[
            RetrievalEvaluationDocument(
                document_id="technology",
                text="Python programming software.",
            ),
            RetrievalEvaluationDocument(
                document_id="cooking",
                text="Cooking food recipe.",
            ),
        ],
        cases=[
            RagAnswerEvaluationCase(
                case_id="technology-case",
                question="How is Python used in programming?",
                expected_document_ids=["technology"],
                top_k=1,
            ),
            RagAnswerEvaluationCase(
                case_id="cooking-case",
                question="What cooking recipe is described?",
                expected_document_ids=["cooking"],
                top_k=1,
            ),
        ],
    )


def make_runner(
    responses: list[object],
) -> RagAnswerEvaluationRunner:
    """Create a controlled answer evaluation runner."""

    retriever = DocumentRetriever(
        embedding_provider=KeywordEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )
    pipeline = RetrievalPipeline(
        retriever=retriever,
    )
    service = RagQuestionAnsweringService(
        client=FakeClient(responses),
        model="test-answer-model",
        retrieval_pipeline=pipeline,
    )

    return RagAnswerEvaluationRunner(
        service=service,
    )


def test_runner_evaluates_successful_answers() -> None:
    runner = make_runner(
        [
            response("Python supports programming [S1]."),
            response("The text describes a recipe [S1]."),
        ]
    )

    result = runner.run(
        dataset=dataset(),
    )

    assert result.indexed_document_count == 2
    assert result.indexed_chunk_count == 2
    assert result.answer_model == "test-answer-model"
    assert result.summary.case_count == 2
    assert result.summary.passed_count == 2
    assert result.summary.pass_rate == 1.0
    assert result.summary.retrieval_pass_rate == 1.0
    assert result.summary.answer_generation_rate == 1.0
    assert result.summary.citation_pass_rate == 1.0
    assert result.summary.mean_citation_precision == 1.0
    assert result.summary.mean_citation_recall == 1.0


def test_runner_records_answer_failure() -> None:
    runner = make_runner(
        [
            response("Answer without a citation."),
            response("Cooking evidence [S1]."),
        ]
    )

    result = runner.run(
        dataset=dataset(),
    )

    first = result.summary.cases[0]

    assert first.answer_generated is False
    assert first.error_code == "missing_citation"
    assert result.summary.answer_generated_count == 1
    assert result.summary.passed_count == 1
    assert result.summary.pass_rate == 0.5


def test_runner_citation_ids_match_expected_document() -> None:
    runner = make_runner(
        [
            response("Python supports programming [S1]."),
            response("Cooking evidence [S1]."),
        ]
    )

    result = runner.run(
        dataset=dataset(),
    )

    assert result.summary.cases[0].expected_citation_ids == [
        "S1"
    ]
    assert result.summary.cases[0].cited_ids == ["S1"]
    assert (
        result.summary.cases[0]
        .citation_evaluation.passed
        is True
    )
