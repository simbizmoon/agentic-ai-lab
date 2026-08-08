"""Tests for OpenAI semantic answer coverage evaluator."""

from types import SimpleNamespace

import pytest

from app.research.openai_answer_coverage_evaluator import (
    OpenAIAnswerCoverageEvaluator,
)
from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
    AnswerCoverageLevel,
)


class FakeResponses:
    """Minimal fake Responses API."""

    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self._response


class FakeClient:
    """Minimal fake OpenAI client."""

    def __init__(self, response: object) -> None:
        self.responses = FakeResponses(response)


def completed_response() -> object:
    return SimpleNamespace(
        id="response-001",
        status="completed",
        output_parsed=AnswerCoverageJudgment(
            coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            coverage_score=0.7,
            covered_aspects=["tool exposure"],
            missing_aspects=["runtime execution"],
            rationale="Exposure is covered but execution is missing.",
        ),
        output=[],
        usage=None,
        _request_id="request-001",
    )


def test_evaluator_uses_structured_output() -> None:
    client = FakeClient(completed_response())
    evaluator = OpenAIAnswerCoverageEvaluator(
        client=client,
        model="test-model",
    )

    result = evaluator.evaluate(
        question="How are tools used?",
        objective="Explain exposure and runtime execution.",
        claims=["Tools are exposed to the agent."],
    )

    assert (
        result.judgment.coverage_level
        is AnswerCoverageLevel.PARTIALLY_COVERED
    )
    assert result.response_id == "response-001"
    assert client.responses.calls[0]["store"] is False
    assert (
        client.responses.calls[0]["text_format"]
        is AnswerCoverageJudgment
    )


@pytest.mark.parametrize(
    ("question", "objective", "claims", "message"),
    [
        (" ", "objective", ["claim"], "question must not be blank"),
        ("question", " ", ["claim"], "objective must not be blank"),
        ("question", "objective", [], "claims must not be empty"),
        (
            "question",
            "objective",
            [" "],
            "claims must not contain blank values",
        ),
    ],
)
def test_evaluator_validates_inputs(
    question: str,
    objective: str,
    claims: list[str],
    message: str,
) -> None:
    evaluator = OpenAIAnswerCoverageEvaluator(
        client=FakeClient(completed_response()),
        model="test-model",
    )

    with pytest.raises(ValueError, match=message):
        evaluator.evaluate(
            question=question,
            objective=objective,
            claims=claims,
        )


class SequencedResponses:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SequencedClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.responses = SequencedResponses(outcomes)


def invalid_fully_covered_error() -> Exception:
    with pytest.raises(Exception) as captured:
        AnswerCoverageJudgment.model_validate(
            {
                "coverage_level": "fully_covered",
                "coverage_score": 0.9,
                "covered_aspects": ["tool exposure"],
                "missing_aspects": ["runtime detail"],
                "rationale": "Contradictory structured output.",
            }
        )
    return captured.value


def test_evaluator_retries_once_after_schema_validation_failure() -> None:
    client = SequencedClient(
        [invalid_fully_covered_error(), completed_response()]
    )
    evaluator = OpenAIAnswerCoverageEvaluator(
        client=client, model="test-model"
    )
    result = evaluator.evaluate(
        question="How are tools used?",
        objective="Explain exposure and runtime execution.",
        claims=["Tools are exposed to the agent."],
    )
    assert result.attempts == 2
    assert len(client.responses.calls) == 2
    assert "previous structured answer failed" in (
        client.responses.calls[1]["instructions"].casefold()
    )


def test_evaluator_stops_after_one_corrective_retry() -> None:
    from app.exceptions import StructuredResponseValidationError

    client = SequencedClient(
        [invalid_fully_covered_error(), invalid_fully_covered_error()]
    )
    evaluator = OpenAIAnswerCoverageEvaluator(
        client=client, model="test-model"
    )
    with pytest.raises(StructuredResponseValidationError) as captured:
        evaluator.evaluate(
            question="How are tools used?",
            objective="Explain exposure and runtime execution.",
            claims=["Tools are exposed to the agent."],
        )
    assert captured.value.attempts == 2
    assert len(client.responses.calls) == 2
