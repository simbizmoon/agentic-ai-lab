"""Offline tests for the existing grounded-answer provider adapter."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.context_builder import build_rag_context
from app.rag.grounded_answer_service import GroundedAnswerServiceError
from app.research.openai_grounded_answer_generator import (
    OpenAIGroundedAnswerGenerator,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.retrieval_result import RetrievalResult


def _context():
    text = "Exact evidence."
    retrieval = RetrievalResult(
        chunk=DocumentChunk(
            document_id="document-1",
            chunk_id="chunk-1",
            ordinal=0,
            text=text,
            start_char=0,
            end_char=len(text),
            metadata={},
        ),
        score=0.9,
        rank=1,
    )
    return build_rag_context([retrieval])


def _usage():
    return SimpleNamespace(
        input_tokens=5,
        output_tokens=3,
        total_tokens=8,
        input_tokens_details=SimpleNamespace(cached_tokens=1),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


class Responses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Client:
    def __init__(self, response: object) -> None:
        self.responses = Responses(response)


def _response(*, text: str = "Supported. [S1]", usage: object = "default"):
    actual_usage = _usage() if usage == "default" else usage
    return SimpleNamespace(
        id="response-001",
        output_text=text,
        usage=actual_usage,
    )


def test_adapter_reuses_grounded_service_and_preserves_usage() -> None:
    client = Client(_response())
    result = OpenAIGroundedAnswerGenerator(client=client, model="test-model").generate(
        question="What?", context=_context()
    )
    assert result.answer.answer == "Supported. [S1]"
    assert result.answer.cited_ids == ["S1"]
    assert result.answer.response_id == "response-001"
    assert result.usage is not None
    assert result.usage.total_tokens == 8
    assert result.elapsed_seconds >= 0
    assert client.responses.calls[0]["model"] == "test-model"


def test_adapter_allows_missing_provider_usage() -> None:
    result = OpenAIGroundedAnswerGenerator(
        client=Client(_response(usage=None)), model="test-model"
    ).generate(question="What?", context=_context())
    assert result.usage is None


def test_adapter_preserves_existing_grounding_error() -> None:
    with pytest.raises(GroundedAnswerServiceError, match="unknown citation"):
        OpenAIGroundedAnswerGenerator(
            client=Client(_response(text="Unknown. [S9]")), model="test-model"
        ).generate(question="What?", context=_context())


@pytest.mark.parametrize("model", ["", "   "])
def test_adapter_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValueError, match="model must not be blank"):
        OpenAIGroundedAnswerGenerator(client=Client(_response()), model=model)
