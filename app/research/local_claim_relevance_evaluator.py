"""Ollama-backed claim relevance evaluator for local LLM benchmarks."""

from __future__ import annotations

import json
import time

from app.research.openai_claim_relevance_evaluator import (
    CLAIM_RELEVANCE_INSTRUCTIONS,
    ClaimRelevanceEvaluationResult,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
)
from app.services.ollama_client import OllamaClient


class LocalClaimRelevanceEvaluator:
    """Judge claim relevance using Ollama structured output."""

    def __init__(
        self,
        *,
        client: OllamaClient,
        model: str,
        num_predict: int = 256,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        if num_predict < 1:
            raise ValueError("num_predict must be at least 1")
        if temperature < 0:
            raise ValueError("temperature must be nonnegative")

        self._client = client
        self._model = model.strip()
        self._num_predict = num_predict
        self._temperature = temperature
        self._seed = seed

    @property
    def model(self) -> str:
        """Return configured model."""
        return self._model

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult:
        """Evaluate one claim against one research request."""
        cleaned_question = question.strip()
        cleaned_objective = objective.strip()
        cleaned_claim = claim_text.strip()

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not cleaned_claim:
            raise ValueError("claim_text must not be blank")

        prompt = (
            f"{CLAIM_RELEVANCE_INSTRUCTIONS}\n\n"
            "Evaluate this input and return only the structured result.\n\n"
            + json.dumps(
                {
                    "question": cleaned_question,
                    "objective": cleaned_objective,
                    "claim": cleaned_claim,
                },
                ensure_ascii=False,
            )
        )

        started = time.perf_counter()
        generated = self._client.generate(
            model=self._model,
            prompt=prompt,
            think=False,
            stream=False,
            keep_alive="5m",
            num_predict=self._num_predict,
            temperature=self._temperature,
            seed=self._seed,
            response_format=ClaimRelevanceJudgment.model_json_schema(),
        )
        elapsed = max(0.0, time.perf_counter() - started)

        if generated.done_reason == "length":
            raise RuntimeError("claim relevance generation stopped by length")
        if not generated.response.strip():
            raise RuntimeError("claim relevance generation returned empty response")

        judgment = ClaimRelevanceJudgment.model_validate_json(
            generated.response
        )

        return ClaimRelevanceEvaluationResult(
            judgment=judgment,
            response_id="ollama-local",
            request_id=None,
            usage=None,
            elapsed_seconds=elapsed,
        )
