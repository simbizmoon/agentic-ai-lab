"""Tests for OpenAI evidence relevance evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
)
from app.research.openai_evidence_relevance_evaluator import (
    EVIDENCE_RELEVANCE_INSTRUCTIONS,
    OpenAIEvidenceRelevanceEvaluator,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)


@dataclass(frozen=True)
class FakeInputTokenDetails:
    cached_tokens: int = 2


@dataclass(frozen=True)
class FakeOutputTokenDetails:
    reasoning_tokens: int = 3


@dataclass(frozen=True)
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 5
    total_tokens: int = 15
    input_tokens_details: FakeInputTokenDetails = (
        FakeInputTokenDetails()
    )
    output_tokens_details: FakeOutputTokenDetails = (
        FakeOutputTokenDetails()
    )


@dataclass(frozen=True)
class FakeResponse:
    output_parsed: object
    status: str = "completed"
    id: str = "resp-evidence-001"
    _request_id: str | None = "req-evidence-001"
    usage: FakeUsage | None = field(default_factory=FakeUsage)
    output: list[object] = field(default_factory=list)


class FakeResponses:
    """Return one controlled structured response."""

    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self._response


class FakeClient:
    """Expose the fake responses resource."""

    def __init__(self, response: object) -> None:
        self.responses = FakeResponses(response)


def direct_judgment() -> EvidenceRelevanceJudgment:
    return EvidenceRelevanceJudgment(
        relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.95,
        rationale=(
            "The passage directly explains how functions are "
            "exposed and used as tools."
        ),
        issues=[],
    )


def evaluator_for(
    response: object,
) -> tuple[OpenAIEvidenceRelevanceEvaluator, FakeClient]:
    client = FakeClient(response)
    value = OpenAIEvidenceRelevanceEvaluator(
        client=client,
        model="gpt-5",
    )
    return value, client


def test_evaluator_uses_only_request_and_evidence_input() -> None:
    evaluator, client = evaluator_for(
        FakeResponse(output_parsed=direct_judgment())
    )

    result = evaluator.evaluate(
        question="How does the SDK support tool calling?",
        objective="Explain the concrete tool-calling mechanism.",
        evidence_excerpt=(
            "Python functions can be exposed as tools to an agent."
        ),
    )

    assert (
        result.judgment.relevance_level
        is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    )
    assert result.response_id == "resp-evidence-001"
    assert result.request_id == "req-evidence-001"
    assert result.usage is not None
    assert result.usage.total_tokens == 15

    call = client.responses.calls[0]
    assert call["model"] == "gpt-5"
    assert (
        call["instructions"]
        == EVIDENCE_RELEVANCE_INSTRUCTIONS
    )
    assert call["text_format"] is EvidenceRelevanceJudgment
    assert call["store"] is False

    model_input = str(call["input"])
    assert '"question"' in model_input
    assert '"objective"' in model_input
    assert '"evidence"' in model_input
    assert "claim" not in model_input.casefold()
    assert "source_id" not in model_input
    assert "document_id" not in model_input


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", " "),
        ("objective", ""),
        ("evidence_excerpt", "   "),
    ],
)
def test_evaluator_rejects_blank_input(
    field: str,
    value: str,
) -> None:
    evaluator, client = evaluator_for(
        FakeResponse(output_parsed=direct_judgment())
    )

    kwargs = {
        "question": "What is requested?",
        "objective": "Explain the requested mechanism.",
        "evidence_excerpt": "Relevant source passage.",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        evaluator.evaluate(**kwargs)

    assert client.responses.calls == []


def test_evaluator_rejects_blank_model() -> None:
    with pytest.raises(ValueError):
        OpenAIEvidenceRelevanceEvaluator(
            client=FakeClient(
                FakeResponse(
                    output_parsed=direct_judgment(),
                )
            ),
            model=" ",
        )


def test_evaluator_rejects_incomplete_response() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(
            status="incomplete",
            output_parsed=None,
        )
    )

    with pytest.raises(StructuredResponseIncompleteError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            evidence_excerpt="Evidence.",
        )


def test_evaluator_rejects_noncompleted_response() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(
            status="failed",
            output_parsed=None,
        )
    )

    with pytest.raises(StructuredResponseStatusError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            evidence_excerpt="Evidence.",
        )


def test_evaluator_rejects_missing_parsed_result() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(output_parsed=None)
    )

    with pytest.raises(StructuredResponseParseError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            evidence_excerpt="Evidence.",
        )


def test_evaluator_rejects_wrong_parsed_type() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(
            output_parsed=SimpleNamespace(
                relevance_level="directly_relevant",
            )
        )
    )

    with pytest.raises(StructuredResponseParseError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            evidence_excerpt="Evidence.",
        )


def test_refusal_is_rejected() -> None:
    response = FakeResponse(
        output_parsed=direct_judgment(),
        output=[
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="refusal",
                        refusal="Cannot evaluate.",
                    )
                ]
            )
        ],
    )
    evaluator, _ = evaluator_for(response)

    with pytest.raises(StructuredResponseRefusalError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            evidence_excerpt="Evidence.",
        )


def test_prompt_separates_evidence_relevance_from_truth() -> None:
    instructions = EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "do not evaluate whether the passage is factually true" in instructions
    assert "do not evaluate source authority or credibility" in instructions
    assert "same topic, product, entity, or domain alone" in instructions
    assert "category is the policy judgment" in instructions


def test_prompt_requires_semantic_not_keyword_relevance() -> None:
    instructions = EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "terminology does not need to match exactly" in instructions
    assert "semantically equivalent wording" in instructions
    assert "do not promote a passage merely because" in instructions
    assert "many query keywords" in instructions


def test_prompt_encodes_requested_answer_type_distinctions() -> None:
    instructions = EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "high-level product positioning alone" in instructions
    assert "post-hoc auditing" in instructions
    assert "storage or change tracking" in instructions
    assert "observability alone is not the control" in instructions


def test_prompt_v1_1_separates_control_inputs_from_enforcement() -> None:
    instructions = EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "distinguish inputs and measurements from enforcement" in instructions
    assert "threshold comparisons" in instructions
    assert "not by themselves a" in instructions
    assert "directly_relevant control" in instructions
    assert "allow, deny, block, stop, restrict" in instructions
    assert "necessary mechanism step is not automatically" in instructions
