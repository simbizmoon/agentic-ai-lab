"""Tests for local Ollama-backed answer coverage evaluator."""

import pytest

from app.research.local_answer_coverage_evaluator import (
    LocalAnswerCoverageEvaluator,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
    AnswerCoverageLevel,
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
    return AnswerCoverageJudgment(
        coverage_level=AnswerCoverageLevel.FULLY_COVERED,
        coverage_score=0.95,
        covered_aspects=[
            "usage measurement",
            "limit comparison",
            "execution stopping",
        ],
        missing_aspects=[],
        rationale="All required mechanism stages are covered.",
    ).model_dump_json()


def test_evaluator_uses_structured_schema_and_think_off() -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    result = evaluator.evaluate(
        question="How does a system enforce an execution budget?",
        objective=(
            "Explain usage measurement, limit comparison, and stopping."
        ),
        claims=[
            "Usage is measured.",
            "Usage is compared with a limit.",
            "Execution stops when the limit is exhausted.",
        ],
    )

    assert (
        result.judgment.coverage_level
        is AnswerCoverageLevel.FULLY_COVERED
    )
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["think"] is False
    assert call["temperature"] == 0.0
    assert call["seed"] == 42
    assert call["response_format"] == (
        AnswerCoverageJudgment.model_json_schema()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", " "),
        ("objective", ""),
    ],
)
def test_evaluator_rejects_blank_text_input(
    field: str,
    value: str,
) -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    kwargs = {
        "question": "Question?",
        "objective": "Objective.",
        "claims": ["Claim."],
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        evaluator.evaluate(**kwargs)

    assert client.calls == []


def test_evaluator_rejects_empty_claims() -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(ValueError, match="claims must not be empty"):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claims=[],
        )

    assert client.calls == []


def test_evaluator_rejects_blank_claim() -> None:
    client = FakeClient(generated(judgment_json()))
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(
        ValueError,
        match="claims must not contain blank values",
    ):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claims=["Claim.", " "],
        )

    assert client.calls == []


def test_evaluator_rejects_length_termination() -> None:
    client = FakeClient(
        generated(
            judgment_json(),
            done_reason="length",
        )
    )
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(RuntimeError, match="stopped by length"):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claims=["Claim."],
        )


def test_evaluator_rejects_invalid_json() -> None:
    client = FakeClient(generated("{bad json"))
    evaluator = LocalAnswerCoverageEvaluator(
        client=client,
        model="qwen3.5:4b",
    )

    with pytest.raises(ValueError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claims=["Claim."],
        )
