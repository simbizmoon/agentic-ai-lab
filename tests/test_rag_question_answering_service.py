"""Tests for end-to-end RAG question answering."""

from __future__ import annotations

import math
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.document_retriever import DocumentRetriever
from app.rag.embedding_provider import EmbeddingProvider
from app.rag.in_memory_vector_store import (
    InMemoryVectorStore,
)
from app.rag.question_answering_service import (
    RagQuestionAnsweringError,
    RagQuestionAnsweringService,
)
from app.rag.retrieval_pipeline import RetrievalPipeline
from app.schemas.document_embedding import TextEmbedding


class TopicEmbeddingProvider(EmbeddingProvider):
    """Map simple topics to deterministic test vectors."""

    @property
    def model_name(self) -> str:
        return "qa-topic-test-v1"

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

        if technology == cooking == 0:
            return [1.0, 1.0]

        return [
            float(technology),
            float(cooking),
        ]


class FakeResponses:
    """Return predefined model responses."""

    def __init__(
        self,
        responses: list[object],
    ) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)

        if not self._responses:
            raise RuntimeError("no fake response available")

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


def model_response(
    text: str,
    *,
    response_id: str = "resp_qa_test",
) -> object:
    """Return a fake Responses API result."""

    return SimpleNamespace(
        id=response_id,
        output_text=text,
    )


def make_service(
    responses: list[object],
) -> tuple[
    RagQuestionAnsweringService,
    FakeClient,
]:
    """Create a deterministic RAG QA service."""

    client = FakeClient(responses)
    retriever = DocumentRetriever(
        embedding_provider=TopicEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )
    pipeline = RetrievalPipeline(
        retriever=retriever,
    )
    service = RagQuestionAnsweringService(
        client=client,
        model="test-model",
        retrieval_pipeline=pipeline,
    )

    return service, client


def index_documents(
    service: RagQuestionAnsweringService,
) -> None:
    """Index technology and cooking documents."""

    retriever = service.retrieval_pipeline.retriever

    retriever.index_document(
        document_id="technology",
        text="Python is used for software programming.",
        metadata={"source": "technology.txt"},
    )
    retriever.index_document(
        document_id="cooking",
        text="This document contains a cooking recipe.",
        metadata={"source": "cooking.txt"},
    )


def test_service_runs_complete_rag_workflow() -> None:
    service, client = make_service(
        [
            model_response(
                "Python is used for software programming [S1]."
            )
        ]
    )
    index_documents(service)

    result = service.answer_question(
        question="How is Python used in programming?",
        top_k=1,
    )

    assert result.retrieval.results[0].chunk.document_id == (
        "technology"
    )
    assert result.answer.cited_ids == ["S1"]
    assert result.answer.response_id == "resp_qa_test"
    assert result.answer.evidence_available is True
    assert len(client.responses.calls) == 1


def test_service_passes_retrieved_context_to_model() -> None:
    service, client = make_service(
        [
            model_response(
                "Python supports programming [S1]."
            )
        ]
    )
    index_documents(service)

    service.answer_question(
        question="What supports programming?",
        top_k=1,
    )

    call = client.responses.calls[0]

    assert call["model"] == "test-model"
    assert "Python is used for software programming." in (
        call["input"]
    )
    assert "[S1]" in call["input"]


def test_service_can_answer_from_cooking_document() -> None:
    service, _ = make_service(
        [
            model_response(
                "The document contains a cooking recipe [S1]."
            )
        ]
    )
    index_documents(service)

    result = service.answer_question(
        question="Which document contains a cooking recipe?",
        top_k=1,
    )

    assert result.retrieval.results[0].chunk.document_id == (
        "cooking"
    )
    assert result.answer.cited_ids == ["S1"]


def test_service_handles_empty_retrieval_context() -> None:
    service, _ = make_service(
        [
            model_response(
                "The supplied evidence does not contain enough "
                "information to answer the question."
            )
        ]
    )

    result = service.answer_question(
        question="What is Python?",
    )

    assert result.retrieval.results == []
    assert result.retrieval.context.citations == []
    assert result.answer.evidence_available is False
    assert result.answer.cited_ids == []


def test_minimum_score_can_remove_answer_context() -> None:
    service, _ = make_service(
        [
            model_response(
                "The supplied evidence does not contain enough "
                "information to answer the question."
            )
        ]
    )
    index_documents(service)

    result = service.answer_question(
        question="neutral unrelated words",
        top_k=2,
        minimum_score=1.0,
    )

    assert len(result.retrieval.results) == 2
    assert result.retrieval.context.citations == []
    assert result.answer.evidence_available is False


def test_service_propagates_missing_citation_error() -> None:
    service, _ = make_service(
        [
            model_response(
                "Python is used for software programming."
            )
        ]
    )
    index_documents(service)

    with pytest.raises(
        RagQuestionAnsweringError,
        match="did not cite retrieved evidence",
    ) as exc_info:
        service.answer_question(
            question="How is Python used?",
            top_k=1,
        )

    assert exc_info.value.code == "missing_citation"


def test_service_propagates_unknown_citation_error() -> None:
    service, _ = make_service(
        [
            model_response(
                "Python is used for programming [S9]."
            )
        ]
    )
    index_documents(service)

    with pytest.raises(
        RagQuestionAnsweringError,
        match="unknown citation",
    ) as exc_info:
        service.answer_question(
            question="How is Python used?",
            top_k=1,
        )

    assert exc_info.value.code == "unknown_citation"


def test_service_wraps_model_request_failure() -> None:
    service, _ = make_service(
        [
            RuntimeError("API unavailable"),
        ]
    )
    index_documents(service)

    with pytest.raises(
        RagQuestionAnsweringError,
        match="request failed",
    ) as exc_info:
        service.answer_question(
            question="How is Python used?",
            top_k=1,
        )

    assert exc_info.value.code == "model_request_failed"


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_service_rejects_blank_question(
    question: str,
) -> None:
    service, _ = make_service([])

    with pytest.raises(
        RagQuestionAnsweringError,
        match="question must not be blank",
    ) as exc_info:
        service.answer_question(
            question=question,
        )

    assert exc_info.value.code == "invalid_question"


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        -1,
    ],
)
def test_service_rejects_invalid_top_k(
    top_k: int,
) -> None:
    service, _ = make_service([])

    with pytest.raises(
        RagQuestionAnsweringError,
        match="top_k must be greater than zero",
    ) as exc_info:
        service.answer_question(
            question="What is Python?",
            top_k=top_k,
        )

    assert exc_info.value.code == "invalid_top_k"


@pytest.mark.parametrize(
    "minimum_score",
    [
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_service_rejects_nonfinite_minimum_score(
    minimum_score: float,
) -> None:
    service, _ = make_service([])

    with pytest.raises(
        RagQuestionAnsweringError,
        match="minimum_score must be finite",
    ) as exc_info:
        service.answer_question(
            question="What is Python?",
            minimum_score=minimum_score,
        )

    assert exc_info.value.code == "invalid_minimum_score"


@pytest.mark.parametrize(
    "model",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_service_rejects_blank_model(
    model: str,
) -> None:
    client = FakeClient([])
    retriever = DocumentRetriever(
        embedding_provider=TopicEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )
    pipeline = RetrievalPipeline(
        retriever=retriever,
    )

    with pytest.raises(
        RagQuestionAnsweringError,
        match="model name must not be blank",
    ) as exc_info:
        RagQuestionAnsweringService(
            client=client,
            model=model,
            retrieval_pipeline=pipeline,
        )

    assert exc_info.value.code == "invalid_model"
