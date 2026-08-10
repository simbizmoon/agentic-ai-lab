"""Tests for local Ollama-backed semantic citation evaluator."""

import pytest

from app.research.local_semantic_citation_evaluator import (
    LocalSemanticCitationEvaluator,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
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
    return SemanticCitationJudgment(
        support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
        entailment_score=0.95,
        rationale="Evidence directly supports the claim.",
        issues=[],
    ).model_dump_json()


def test_evaluator_uses_structured_schema_and_think_off() -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalSemanticCitationEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        claim_text="The SDK supports function tools.",
        evidence_excerpt="The SDK supports function tools.",
    )

    assert (
        result.judgment.support_level
        is SemanticCitationSupportLevel.FULLY_SUPPORTED
    )
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["think"] is False
    assert call["temperature"] == 0.0
    assert call["seed"] == 42
    assert call["response_format"] == (
        SemanticCitationJudgment.model_json_schema()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_text", " "),
        ("evidence_excerpt", ""),
    ],
)
def test_evaluator_rejects_blank_input(
    field: str,
    value: str,
) -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalSemanticCitationEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    kwargs = {
        "claim_text": "Claim.",
        "evidence_excerpt": "Evidence.",
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
    evaluator = LocalSemanticCitationEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(RuntimeError, match="stopped by length"):
        evaluator.evaluate(
            claim_text="Claim.",
            evidence_excerpt="Evidence.",
        )


def test_evaluator_rejects_invalid_json() -> None:
    client = FakeClient(generated("{bad json"))
    evaluator = LocalSemanticCitationEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(ValueError):
        evaluator.evaluate(
            claim_text="Claim.",
            evidence_excerpt="Evidence.",
        )
