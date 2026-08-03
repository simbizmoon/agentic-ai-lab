"""Generate answers grounded in retrieved document evidence."""

from __future__ import annotations

import re
from typing import Any, Protocol

from app.rag.grounded_prompt_builder import (
    build_grounded_answer_prompt,
)
from app.schemas.grounded_answer_result import (
    GroundedAnswerResult,
)
from app.schemas.rag_context import RagContext


class ResponsesAPI(Protocol):
    """Minimal Responses API interface required by the service."""

    def create(self, **kwargs: Any) -> object:
        """Create one model response."""


class OpenAIClientProtocol(Protocol):
    """Minimal OpenAI client interface required by the service."""

    responses: ResponsesAPI


class GroundedAnswerServiceError(RuntimeError):
    """Raised when grounded answer generation fails."""

    def __init__(
        self,
        *,
        code: str,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


_CITATION_PATTERN = re.compile(r"\[([A-Za-z]\d+)\]")


def _extract_output_text(response: object) -> str:
    """Extract nonblank text from a Responses API response."""

    output_text = getattr(response, "output_text", None)

    if not isinstance(output_text, str):
        raise GroundedAnswerServiceError(
            code="invalid_response",
            safe_message=(
                "model response did not contain text"
            ),
        )

    normalized = output_text.strip()

    if not normalized:
        raise GroundedAnswerServiceError(
            code="missing_answer",
            safe_message=(
                "model response contained an empty answer"
            ),
        )

    return normalized


def _extract_response_id(
    response: object,
) -> str | None:
    """Return the response identifier when available."""

    response_id = getattr(response, "id", None)

    if isinstance(response_id, str) and response_id.strip():
        return response_id

    return None


def _extract_cited_ids(answer: str) -> list[str]:
    """Return unique citation IDs in first-appearance order."""

    cited_ids: list[str] = []

    for match in _CITATION_PATTERN.finditer(answer):
        citation_id = match.group(1)

        if citation_id not in cited_ids:
            cited_ids.append(citation_id)

    return cited_ids


def generate_grounded_answer(
    *,
    client: OpenAIClientProtocol,
    model: str,
    question: str,
    context: RagContext,
) -> GroundedAnswerResult:
    """Generate and validate an answer grounded in RAG context."""

    if not model.strip():
        raise GroundedAnswerServiceError(
            code="invalid_model",
            safe_message="model name must not be blank",
        )

    prompt = build_grounded_answer_prompt(
        question=question,
        context=context,
    )

    try:
        response = client.responses.create(
            model=model,
            instructions=prompt.system_instructions,
            input=prompt.user_prompt,
        )
    except Exception as exc:
        raise GroundedAnswerServiceError(
            code="model_request_failed",
            safe_message="grounded answer request failed",
        ) from exc

    answer = _extract_output_text(response)
    cited_ids = _extract_cited_ids(answer)

    if not context.citations and cited_ids:
        raise GroundedAnswerServiceError(
            code="citation_without_evidence",
            safe_message=(
                "model answer cited evidence that was not supplied"
            ),
        )

    available_ids = {
        citation.citation_id
        for citation in context.citations
    }
    unknown_ids = [
        citation_id
        for citation_id in cited_ids
        if citation_id not in available_ids
    ]

    if unknown_ids:
        raise GroundedAnswerServiceError(
            code="unknown_citation",
            safe_message=(
                "model answer referenced an unknown citation"
            ),
        )

    if context.citations and not cited_ids:
        raise GroundedAnswerServiceError(
            code="missing_citation",
            safe_message=(
                "model answer did not cite retrieved evidence"
            ),
        )

    return GroundedAnswerResult(
        question=prompt.question,
        answer=answer,
        citations=context.citations,
        cited_ids=cited_ids,
        response_id=_extract_response_id(response),
        model_name=model,
        evidence_available=bool(context.citations),
    )
