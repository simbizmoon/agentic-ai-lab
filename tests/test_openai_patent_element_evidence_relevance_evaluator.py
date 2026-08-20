"""Tests for OpenAI patent element/evidence technical relevance."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
)
from app.research.openai_patent_element_evidence_relevance_evaluator import (
    PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS,
    OpenAIPatentElementEvidenceRelevanceEvaluator,
    PatentElementEvidenceProviderError,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)


@dataclass(frozen=True)
class FakeInputTokenDetails:
    cached_tokens: int


@dataclass(frozen=True)
class FakeOutputTokenDetails:
    reasoning_tokens: int


@dataclass(frozen=True)
class FakeUsage:
    input_tokens: int
    input_tokens_details: FakeInputTokenDetails
    output_tokens: int
    output_tokens_details: FakeOutputTokenDetails
    total_tokens: int


@dataclass
class FakeResponse:
    output_parsed: object | None
    status: str = "completed"
    id: str = "resp-patent-element-evidence"
    _request_id: str | None = "req-patent-element-evidence"
    usage: object | None = None
    output: tuple[object, ...] = ()


class FakeResponses:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def direct_judgment() -> EvidenceRelevanceJudgment:
    return EvidenceRelevanceJudgment(
        relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.94,
        rationale=(
            "The excerpt describes a pressure sensor used to determine "
            "seat occupancy, matching the element's technical function."
        ),
        issues=[],
    )


def evaluator_for(
    response: FakeResponse | None = None,
    *,
    error: Exception | None = None,
) -> tuple[OpenAIPatentElementEvidenceRelevanceEvaluator, FakeResponses]:
    responses = FakeResponses(response=response, error=error)
    return (
        OpenAIPatentElementEvidenceRelevanceEvaluator(
            client=FakeClient(responses),
            model="test-model",
        ),
        responses,
    )


def test_evaluator_uses_one_structured_element_evidence_request() -> None:
    evaluator, responses = evaluator_for(FakeResponse(output_parsed=direct_judgment()))

    result = evaluator.evaluate(
        element_text=(
            "a pressure sensor configured to determine whether a seat is occupied"
        ),
        evidence_excerpt=(
            "A pressure sensor determines whether a person occupies the seat."
        ),
    )

    assert result.judgment.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    assert result.response_id == "resp-patent-element-evidence"
    assert result.request_id == "req-patent-element-evidence"
    assert len(responses.calls) == 1

    call = responses.calls[0]
    assert call["model"] == "test-model"
    assert call["instructions"] == PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS
    assert call["text_format"] is EvidenceRelevanceJudgment
    assert call["store"] is False
    model_input = str(call["input"])
    assert '"claim_element"' in model_input
    assert '"prior_art_evidence"' in model_input
    assert "pressure sensor" in model_input
    assert "question" not in model_input.casefold()
    assert "objective" not in model_input.casefold()
    assert "source_id" not in model_input
    assert "document_id" not in model_input
    assert "publication_number" not in model_input


def test_evaluator_preserves_provider_usage() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(
            output_parsed=direct_judgment(),
            usage=FakeUsage(
                input_tokens=30,
                input_tokens_details=FakeInputTokenDetails(cached_tokens=4),
                output_tokens=12,
                output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=3),
                total_tokens=42,
            ),
        )
    )

    result = evaluator.evaluate(
        element_text="a pressure sensor configured to detect seat occupancy",
        evidence_excerpt="A pressure sensor detects whether a seat is occupied.",
    )

    assert result.usage is not None
    assert result.usage.input_tokens == 30
    assert result.usage.cached_input_tokens == 4
    assert result.usage.output_tokens == 12
    assert result.usage.reasoning_tokens == 3
    assert result.usage.total_tokens == 42


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("element_text", " "),
        ("evidence_excerpt", ""),
    ],
)
def test_evaluator_rejects_blank_input(
    field_name: str,
    value: str,
) -> None:
    evaluator, responses = evaluator_for(FakeResponse(output_parsed=direct_judgment()))
    kwargs = {
        "element_text": "a pressure sensor",
        "evidence_excerpt": "A pressure sensor is disclosed.",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError):
        evaluator.evaluate(**kwargs)

    assert responses.calls == []


def test_evaluator_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model must not be blank"):
        OpenAIPatentElementEvidenceRelevanceEvaluator(
            client=FakeClient(FakeResponses()),
            model=" ",
        )


def test_prompt_enforces_technical_nonlegal_scope() -> None:
    instructions = PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "technical relevance mapping only" in instructions
    assert "compare technical meaning, not keyword overlap" in instructions
    assert "do not infer missing structure" in instructions
    assert "do not evaluate the remainder of the patent claim" in instructions
    assert (
        "do not determine whether the evidence fully covers a patent claim"
        in instructions
    )
    assert "novelty" in instructions
    assert "anticipation" in instructions
    assert "obviousness" in instructions
    assert "invalidity" in instructions
    assert "infringement" in instructions
    assert "freedom-to-operate" in instructions
    assert "directly_relevant" in instructions
    assert "technical mapping label only" in instructions


def test_prompt_distinguishes_component_mention_from_required_relationship() -> None:
    instructions = PATENT_ELEMENT_EVIDENCE_RELEVANCE_INSTRUCTIONS.casefold()

    assert "broad component mention" in instructions
    assert "specific function, condition, relationship, or" in instructions
    assert "combination" in instructions
    assert "shared vocabulary" in instructions


def test_evaluator_accepts_korean_without_translation() -> None:
    evaluator, responses = evaluator_for(FakeResponse(output_parsed=direct_judgment()))

    evaluator.evaluate(
        element_text="압력센서의 신호에 기초하여 착석 상태를 판정하는 제어부",
        evidence_excerpt="압력센서의 출력값을 이용하여 사용자의 착석 여부를 판단한다.",
    )

    model_input = str(responses.calls[0]["input"])
    assert "압력센서" in model_input
    assert "착석" in model_input


def test_evaluator_rejects_incomplete_response() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(output_parsed=direct_judgment(), status="incomplete")
    )

    with pytest.raises(StructuredResponseIncompleteError):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_evaluator_rejects_unexpected_status() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(output_parsed=direct_judgment(), status="queued")
    )

    with pytest.raises(StructuredResponseStatusError):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_evaluator_rejects_refusal() -> None:
    refusal_content = SimpleNamespace(refusal="Cannot comply.")
    message = SimpleNamespace(content=(refusal_content,))
    evaluator, _ = evaluator_for(
        FakeResponse(
            output_parsed=direct_judgment(),
            output=(message,),
        )
    )

    with pytest.raises(StructuredResponseRefusalError):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_evaluator_rejects_empty_parsed_output() -> None:
    evaluator, _ = evaluator_for(FakeResponse(output_parsed=None))

    with pytest.raises(StructuredResponseParseError, match="was empty"):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_evaluator_rejects_wrong_parsed_type() -> None:
    evaluator, _ = evaluator_for(
        FakeResponse(output_parsed=SimpleNamespace(relevance_score=0.9))
    )

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_evaluator_maps_provider_failure() -> None:
    evaluator, _ = evaluator_for(error=RuntimeError("provider down"))

    with pytest.raises(
        PatentElementEvidenceProviderError,
        match="request failed",
    ):
        evaluator.evaluate(
            element_text="a pressure sensor",
            evidence_excerpt="A pressure sensor is disclosed.",
        )


def test_directly_relevant_result_is_not_a_legal_conclusion() -> None:
    result = direct_judgment()

    assert result.relevance_level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
    assert "novel" not in result.rationale.casefold()
    assert "invalid" not in result.rationale.casefold()
