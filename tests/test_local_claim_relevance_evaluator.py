"""Tests for local Ollama-backed claim relevance evaluator."""

import pytest

from app.research.local_claim_relevance_evaluator import (
    LocalClaimRelevanceEvaluator,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)
from app.services.ollama_client import OllamaGenerateResponse


def generated(
    response: str,
    *,
    done_reason: str = "stop",
) -> OllamaGenerateResponse:
    return OllamaGenerateResponse(
        model="qwen3.5:4b",
        response=response,
        thinking="",
        done=True,
        done_reason=done_reason,
        total_duration_ns=1_000_000,
        load_duration_ns=10,
        prompt_eval_count=20,
        prompt_eval_duration_ns=100,
        eval_count=20,
        eval_duration_ns=100,
    )


class FakeClient:
    def __init__(self, result: OllamaGenerateResponse) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> OllamaGenerateResponse:
        self.calls.append(dict(kwargs))
        return self.result


def judgment_json() -> str:
    return ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.9,
        rationale="Directly answers the requested mechanism.",
        issues=[],
    ).model_dump_json()


def test_evaluator_uses_structured_schema_and_think_off() -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalClaimRelevanceEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        question="How is access controlled?",
        objective="Explain a preventive authorization mechanism.",
        claim_text="A policy checks permission before the write runs.",
    )

    assert (
        result.judgment.relevance_level
        is ClaimRelevanceLevel.DIRECTLY_RELEVANT
    )
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["think"] is False
    assert call["temperature"] == 0.0
    assert call["seed"] == 42
    assert call["response_format"] == (
        ClaimRelevanceJudgment.model_json_schema()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", " "),
        ("objective", ""),
        ("claim_text", "   "),
    ],
)
def test_evaluator_rejects_blank_input(
    field: str,
    value: str,
) -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalClaimRelevanceEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    kwargs = {
        "question": "Question?",
        "objective": "Objective.",
        "claim_text": "Claim.",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        evaluator.evaluate(**kwargs)

    assert client.calls == []


def test_evaluator_rejects_length_termination() -> None:
    client = FakeClient(
        generated(
            judgment_json(),
            done_reason="length",
        )
    )
    evaluator = LocalClaimRelevanceEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(RuntimeError, match="stopped by length"):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_evaluator_rejects_invalid_json() -> None:
    client = FakeClient(generated("{bad json"))
    evaluator = LocalClaimRelevanceEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(ValueError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )
