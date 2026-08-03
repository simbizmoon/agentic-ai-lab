"""End-to-end retrieval-augmented question answering."""

from __future__ import annotations

import math

from app.rag.grounded_answer_service import (
    GroundedAnswerServiceError,
    OpenAIClientProtocol,
    generate_grounded_answer,
)
from app.rag.retrieval_pipeline import (
    RetrievalPipeline,
    RetrievalPipelineError,
)
from app.schemas.rag_question_answering_result import (
    RagQuestionAnsweringResult,
)


class RagQuestionAnsweringError(RuntimeError):
    """Raised when an end-to-end RAG operation fails."""

    def __init__(
        self,
        *,
        code: str,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class RagQuestionAnsweringService:
    """Retrieve evidence and generate a grounded answer."""

    def __init__(
        self,
        *,
        client: OpenAIClientProtocol,
        model: str,
        retrieval_pipeline: RetrievalPipeline,
    ) -> None:
        if not model.strip():
            raise RagQuestionAnsweringError(
                code="invalid_model",
                safe_message="model name must not be blank",
            )

        self._client = client
        self._model = model
        self._retrieval_pipeline = retrieval_pipeline

    @property
    def model(self) -> str:
        """Return the configured answer model."""

        return self._model

    @property
    def retrieval_pipeline(self) -> RetrievalPipeline:
        """Return the configured retrieval pipeline."""

        return self._retrieval_pipeline

    def answer_question(
        self,
        *,
        question: str,
        top_k: int = 5,
        minimum_score: float | None = None,
    ) -> RagQuestionAnsweringResult:
        """Retrieve evidence and generate one grounded answer."""

        if not question.strip():
            raise RagQuestionAnsweringError(
                code="invalid_question",
                safe_message="question must not be blank",
            )

        if top_k <= 0:
            raise RagQuestionAnsweringError(
                code="invalid_top_k",
                safe_message="top_k must be greater than zero",
            )

        if (
            minimum_score is not None
            and not math.isfinite(minimum_score)
        ):
            raise RagQuestionAnsweringError(
                code="invalid_minimum_score",
                safe_message="minimum_score must be finite",
            )

        normalized_question = question.strip()

        try:
            retrieval = self.retrieval_pipeline.run(
                query=normalized_question,
                top_k=top_k,
                minimum_score=minimum_score,
            )
        except RetrievalPipelineError as exc:
            raise RagQuestionAnsweringError(
                code="retrieval_failed",
                safe_message="document retrieval failed",
            ) from exc

        try:
            answer = generate_grounded_answer(
                client=self._client,
                model=self.model,
                question=normalized_question,
                context=retrieval.context,
            )
        except GroundedAnswerServiceError as exc:
            raise RagQuestionAnsweringError(
                code=exc.code,
                safe_message=exc.safe_message,
            ) from exc

        return RagQuestionAnsweringResult(
            retrieval=retrieval,
            answer=answer,
        )
