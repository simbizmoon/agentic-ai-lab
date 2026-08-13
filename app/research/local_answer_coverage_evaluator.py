"""Ollama-backed answer coverage evaluator for local LLM benchmarks."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.research.openai_answer_coverage_evaluator import (
    ANSWER_COVERAGE_INSTRUCTIONS,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
)
from app.services.ollama_client import OllamaClient


@dataclass(frozen=True)
class LocalAnswerCoverageEvaluationResult:
    """Minimal result required by AnswerCoverageEvaluationRunner."""

    judgment: AnswerCoverageJudgment
    elapsed_seconds: float


class LocalAnswerCoverageEvaluator:
    """Judge semantic answer coverage using Ollama structured output."""

    def __init__(
        self,
        *,
        client: OllamaClient,
        model: str,
        num_predict: int = 384,
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
        claims: list[str],
    ) -> LocalAnswerCoverageEvaluationResult:
        """Evaluate semantic coverage for one complete claim set."""
        cleaned_question = question.strip()
        cleaned_objective = objective.strip()
        cleaned_claims = [claim.strip() for claim in claims]

        if not cleaned_question:
            raise ValueError("question must not be blank")
        if not cleaned_objective:
            raise ValueError("objective must not be blank")
        if not cleaned_claims:
            raise ValueError("claims must not be empty")
        if any(not claim for claim in cleaned_claims):
            raise ValueError("claims must not contain blank values")

        prompt = (
            f"{ANSWER_COVERAGE_INSTRUCTIONS}\n\n"
            "Evaluate this input and return only the structured result.\n\n"
            + json.dumps(
                {
                    "question": cleaned_question,
                    "objective": cleaned_objective,
                    "claims": cleaned_claims,
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
            response_format=AnswerCoverageJudgment.model_json_schema(),
        )
        elapsed = max(0.0, time.perf_counter() - started)

        if generated.done_reason == "length":
            raise RuntimeError(
                "answer coverage generation stopped by length"
            )
        if not generated.response.strip():
            raise RuntimeError(
                "answer coverage generation returned empty response"
            )

        judgment = AnswerCoverageJudgment.model_validate_json(
            generated.response
        )

        return LocalAnswerCoverageEvaluationResult(
            judgment=judgment,
            elapsed_seconds=elapsed,
        )
