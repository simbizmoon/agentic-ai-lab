"""Adapter from the existing grounded-answer service to Step 9 generation."""

from __future__ import annotations

import time
from typing import Any

from app.rag.grounded_answer_service import (
    OpenAIClientProtocol,
    ResponsesAPI,
    generate_grounded_answer,
)
from app.research.bounded_grounded_answer_orchestrator import (
    GroundedAnswerGenerationAttempt,
)
from app.schemas.rag_context import RagContext
from app.services.text_generation import extract_token_usage, validate_token_usage


class _UsageCapturingResponses:
    def __init__(self, responses: ResponsesAPI) -> None:
        self._responses = responses
        self.usage = None

    def create(self, **kwargs: Any) -> object:
        response = self._responses.create(**kwargs)
        self.usage = extract_token_usage(response)  # type: ignore[arg-type]
        if self.usage is not None:
            validate_token_usage(self.usage)
        return response


class _UsageCapturingClient:
    def __init__(self, client: OpenAIClientProtocol) -> None:
        self.responses = _UsageCapturingResponses(client.responses)


class OpenAIGroundedAnswerGenerator:
    """Reuse grounded prompt/output validation and retain provider usage."""

    def __init__(self, *, client: OpenAIClientProtocol, model: str) -> None:
        if not model.strip():
            raise ValueError("grounded answer generator model must not be blank")
        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self, *, question: str, context: RagContext
    ) -> GroundedAnswerGenerationAttempt:
        capturing_client = _UsageCapturingClient(self._client)
        started = time.perf_counter()
        answer = generate_grounded_answer(
            client=capturing_client,
            model=self.model,
            question=question,
            context=context,
        )
        return GroundedAnswerGenerationAttempt(
            answer=answer,
            usage=capturing_client.responses.usage,
            elapsed_seconds=max(0.0, time.perf_counter() - started),
        )
