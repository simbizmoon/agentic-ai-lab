"""Ollama-backed semantic citation evaluator for local LLM benchmarks."""

from __future__ import annotations

import json
import time

from app.research.openai_semantic_citation_evaluator import (
    SEMANTIC_CITATION_INSTRUCTIONS,
    OpenAISemanticCitationEvaluator,
    SemanticCitationEvaluationResult,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
)
from app.services.ollama_client import OllamaClient
from app.services.text_generation import TokenUsage


class LocalSemanticCitationEvaluator:
    """Judge claim-to-evidence support using Ollama structured output."""

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
        claim_text: str,
        evidence_excerpt: str,
    ) -> SemanticCitationEvaluationResult:
        """Evaluate semantic support for one claim/evidence pair."""
        cleaned_claim = claim_text.strip()
        cleaned_evidence = evidence_excerpt.strip()

        if not cleaned_claim:
            raise ValueError("claim_text must not be blank")
        if not cleaned_evidence:
            raise ValueError("evidence_excerpt must not be blank")

        prompt = (
            f"{SEMANTIC_CITATION_INSTRUCTIONS}\n\n"
            "Evaluate this input and return only the structured result.\n\n"
            + json.dumps(
                {
                    "claim": cleaned_claim,
                    "evidence": cleaned_evidence,
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
            response_format=SemanticCitationJudgment.model_json_schema(),
        )
        elapsed = max(0.0, time.perf_counter() - started)

        if generated.done_reason == "length":
            raise RuntimeError(
                "semantic citation generation stopped by length"
            )
        if not generated.response.strip():
            raise RuntimeError(
                "semantic citation generation returned empty response"
            )

        judgment = SemanticCitationJudgment.model_validate_json(
            generated.response
        )

        return SemanticCitationEvaluationResult(
            judgment=judgment,
            decision=(
                OpenAISemanticCitationEvaluator.decision_for_judgment(
                    judgment
                )
            ),
            response_id="ollama-local",
            request_id=None,
            usage=TokenUsage(
                input_tokens=generated.prompt_eval_count,
                cached_input_tokens=0,
                output_tokens=generated.eval_count,
                reasoning_tokens=0,
                total_tokens=(
                    generated.prompt_eval_count
                    + generated.eval_count
                ),
            ),
            elapsed_seconds=elapsed,
        )
