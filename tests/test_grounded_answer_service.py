"""Tests for grounded answer generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.grounded_answer_service import (
    GroundedAnswerServiceError,
    generate_grounded_answer,
)
from app.schemas.rag_context import (
    RagCitation,
    RagContext,
)


class FakeResponses:
    """Return predefined responses and record requests."""

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


def grounded_context() -> RagContext:
    """Return context containing two sources."""

    return RagContext(
        context_text=(
            "[S1]\nPython is a programming language.\n\n"
            "[S2]\nPython can automate repeated work."
        ),
        citations=[
            RagCitation(
                citation_id="S1",
                document_id="doc-1",
                chunk_id="doc-1:chunk:0000",
                rank=1,
                score=0.95,
                start_char=0,
                end_char=33,
                source="language.txt",
            ),
            RagCitation(
                citation_id="S2",
                document_id="doc-2",
                chunk_id="doc-2:chunk:0000",
                rank=2,
                score=0.85,
                start_char=0,
                end_char=34,
                source="automation.txt",
            ),
        ],
    )


def empty_context() -> RagContext:
    """Return context without evidence."""

    return RagContext(
        context_text="",
        citations=[],
    )


def response(
    text: str,
    *,
    response_id: str = "resp_test",
) -> object:
    """Return a fake Responses API response."""

    return SimpleNamespace(
        id=response_id,
        output_text=text,
    )


def test_service_creates_grounded_answer() -> None:
    client = FakeClient(
        [
            response(
                "Python is a programming language [S1] and "
                "can automate work [S2]."
            )
        ]
    )

    result = generate_grounded_answer(
        client=client,
        model="test-model",
        question="What is Python useful for?",
        context=grounded_context(),
    )

    assert result.cited_ids == ["S1", "S2"]
    assert result.response_id == "resp_test"
    assert result.model_name == "test-model"
    assert result.evidence_available is True


def test_service_sends_instructions_and_input() -> None:
    client = FakeClient(
        [
            response(
                "Python is a programming language [S1]."
            )
        ]
    )

    generate_grounded_answer(
        client=client,
        model="test-model",
        question="What is Python?",
        context=grounded_context(),
    )

    call = client.responses.calls[0]

    assert call["model"] == "test-model"
    assert "Answer only from the supplied evidence" in (
        call["instructions"]
    )
    assert "What is Python?" in call["input"]
    assert "[S1]" in call["input"]
    assert "[S2]" in call["input"]


def test_service_preserves_citation_order_of_appearance() -> None:
    client = FakeClient(
        [
            response(
                "Automation is supported [S2]. "
                "Python is a language [S1]. "
                "Automation remains supported [S2]."
            )
        ]
    )

    result = generate_grounded_answer(
        client=client,
        model="test-model",
        question="Summarize the evidence.",
        context=grounded_context(),
    )

    assert result.cited_ids == ["S2", "S1"]


def test_service_allows_no_evidence_answer() -> None:
    client = FakeClient(
        [
            response(
                "The supplied evidence does not contain enough "
                "information to answer the question."
            )
        ]
    )

    result = generate_grounded_answer(
        client=client,
        model="test-model",
        question="What is the answer?",
        context=empty_context(),
    )

    assert result.evidence_available is False
    assert result.citations == []
    assert result.cited_ids == []


def test_service_rejects_missing_citation() -> None:
    client = FakeClient(
        [
            response(
                "Python is a programming language."
            )
        ]
    )

    with pytest.raises(
        GroundedAnswerServiceError,
        match="did not cite retrieved evidence",
    ) as exc_info:
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is Python?",
            context=grounded_context(),
        )

    assert exc_info.value.code == "missing_citation"


def test_service_rejects_unknown_citation() -> None:
    client = FakeClient(
        [
            response(
                "Python is a programming language [S9]."
            )
        ]
    )

    with pytest.raises(
        GroundedAnswerServiceError,
        match="unknown citation",
    ) as exc_info:
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is Python?",
            context=grounded_context(),
        )

    assert exc_info.value.code == "unknown_citation"


def test_service_rejects_citation_without_evidence() -> None:
    client = FakeClient(
        [
            response(
                "There is no evidence [S1]."
            )
        ]
    )

    with pytest.raises(
        GroundedAnswerServiceError,
        match="was not supplied",
    ) as exc_info:
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is the answer?",
            context=empty_context(),
        )

    assert (
        exc_info.value.code
        == "citation_without_evidence"
    )


@pytest.mark.parametrize(
    "output_text",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_service_rejects_empty_answer(
    output_text: str,
) -> None:
    client = FakeClient([response(output_text)])

    with pytest.raises(
        GroundedAnswerServiceError,
        match="empty answer",
    ):
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is Python?",
            context=grounded_context(),
        )


def test_service_rejects_missing_output_text() -> None:
    client = FakeClient(
        [
            SimpleNamespace(
                id="resp_missing",
            )
        ]
    )

    with pytest.raises(
        GroundedAnswerServiceError,
        match="did not contain text",
    ):
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is Python?",
            context=grounded_context(),
        )


def test_service_wraps_model_request_failure() -> None:
    client = FakeClient(
        [
            RuntimeError("API unavailable"),
        ]
    )

    with pytest.raises(
        GroundedAnswerServiceError,
        match="request failed",
    ) as exc_info:
        generate_grounded_answer(
            client=client,
            model="test-model",
            question="What is Python?",
            context=grounded_context(),
        )

    assert exc_info.value.code == "model_request_failed"


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

    with pytest.raises(
        GroundedAnswerServiceError,
        match="model name must not be blank",
    ):
        generate_grounded_answer(
            client=client,
            model=model,
            question="What is Python?",
            context=grounded_context(),
        )
