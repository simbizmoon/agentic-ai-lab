"""Tests for OpenAI patent claim-element decomposition."""

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
from app.research.openai_patent_claim_element_decomposer import (
    PATENT_CLAIM_ELEMENT_DECOMPOSITION_INSTRUCTIONS,
    OpenAIPatentClaimElementDecomposer,
    PatentClaimElementProviderError,
)
from app.schemas.patent_claim_decomposition import (
    PatentClaimElement,
    PatentClaimElementSelection,
)
from app.schemas.patent_claims import PatentClaim


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
    id: str = "resp-patent-claim-elements"
    _request_id: str | None = "req-patent-claim-elements"
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


def claim() -> PatentClaim:
    return PatentClaim(
        claim_number=1,
        provider_position=1,
        text=(
            "A system comprising a pressure sensor configured to detect "
            "seat occupancy and a controller configured to generate an alert "
            "when occupancy persists for a threshold duration."
        ),
    )


def selection() -> PatentClaimElementSelection:
    return PatentClaimElementSelection(
        elements=(
            PatentClaimElement(
                element_number=1,
                text="a pressure sensor configured to detect seat occupancy",
            ),
            PatentClaimElement(
                element_number=2,
                text=(
                    "a controller configured to generate an alert when "
                    "occupancy persists for a threshold duration"
                ),
            ),
        )
    )


def decomposer_for(
    response: FakeResponse | None = None,
    *,
    error: Exception | None = None,
) -> tuple[OpenAIPatentClaimElementDecomposer, FakeResponses]:
    responses = FakeResponses(response=response, error=error)
    return (
        OpenAIPatentClaimElementDecomposer(
            client=FakeClient(responses),
            model="test-model",
        ),
        responses,
    )


def test_decomposer_uses_one_structured_request_and_binds_source_claim() -> None:
    decomposer, responses = decomposer_for(FakeResponse(output_parsed=selection()))

    result = decomposer.decompose(claim())

    assert result.decomposition.claim_number == 1
    assert result.decomposition.provider_position == 1
    assert result.decomposition.original_claim_text == claim().text
    assert len(result.decomposition.elements) == 2
    assert result.response_id == "resp-patent-claim-elements"
    assert result.request_id == "req-patent-claim-elements"
    assert len(responses.calls) == 1

    call = responses.calls[0]
    assert call["model"] == "test-model"
    assert call["instructions"] == PATENT_CLAIM_ELEMENT_DECOMPOSITION_INSTRUCTIONS
    assert call["text_format"] is PatentClaimElementSelection
    assert call["store"] is False
    assert '"claim_number": 1' in call["input"]
    assert '"provider_position": 1' in call["input"]
    assert "pressure sensor" in call["input"]


def test_decomposer_preserves_provider_usage() -> None:
    decomposer, _ = decomposer_for(
        FakeResponse(
            output_parsed=selection(),
            usage=FakeUsage(
                input_tokens=20,
                input_tokens_details=FakeInputTokenDetails(cached_tokens=3),
                output_tokens=9,
                output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=2),
                total_tokens=29,
            ),
        )
    )

    result = decomposer.decompose(claim())

    assert result.usage is not None
    assert result.usage.input_tokens == 20
    assert result.usage.cached_input_tokens == 3
    assert result.usage.output_tokens == 9
    assert result.usage.reasoning_tokens == 2
    assert result.usage.total_tokens == 29


def test_decomposer_prompt_enforces_bounded_nonlegal_scope() -> None:
    instructions = PATENT_CLAIM_ELEMENT_DECOMPOSITION_INSTRUCTIONS

    assert "Use only the supplied patent claim text" in instructions
    assert "Do not add technical facts" in instructions
    assert "same logical order" in instructions
    assert "Do not translate" in instructions
    assert "Do not classify the claim as independent or dependent" in instructions
    assert "Do not infer dependency" in instructions
    assert "legal conclusions" in instructions
    assert "Do not identify any element as essential" in instructions


def test_decomposer_accepts_korean_claim_without_translation_contract_change() -> None:
    korean_claim = PatentClaim(
        claim_number=1,
        provider_position=1,
        text=(
            "압력센서와, 상기 압력센서의 신호에 기초하여 "
            "착석 상태를 판정하는 제어부를 포함하는 시스템."
        ),
    )
    korean_selection = PatentClaimElementSelection(
        elements=(
            PatentClaimElement(element_number=1, text="압력센서"),
            PatentClaimElement(
                element_number=2,
                text=("상기 압력센서의 신호에 기초하여 착석 상태를 판정하는 제어부"),
            ),
        )
    )
    decomposer, responses = decomposer_for(FakeResponse(output_parsed=korean_selection))

    result = decomposer.decompose(korean_claim)

    assert result.decomposition.original_claim_text == korean_claim.text
    assert result.decomposition.elements[0].text == "압력센서"
    assert "착석 상태" in result.decomposition.elements[1].text
    assert "압력센서" in responses.calls[0]["input"]


def test_decomposer_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model must not be blank"):
        OpenAIPatentClaimElementDecomposer(
            client=FakeClient(FakeResponses()),
            model=" ",
        )


def test_decomposer_rejects_incomplete_response() -> None:
    decomposer, _ = decomposer_for(
        FakeResponse(output_parsed=selection(), status="incomplete")
    )

    with pytest.raises(StructuredResponseIncompleteError):
        decomposer.decompose(claim())


def test_decomposer_rejects_unexpected_status() -> None:
    decomposer, _ = decomposer_for(
        FakeResponse(output_parsed=selection(), status="queued")
    )

    with pytest.raises(StructuredResponseStatusError):
        decomposer.decompose(claim())


def test_decomposer_rejects_empty_parsed_output() -> None:
    decomposer, _ = decomposer_for(FakeResponse(output_parsed=None))

    with pytest.raises(StructuredResponseParseError, match="was empty"):
        decomposer.decompose(claim())


def test_decomposer_rejects_wrong_parsed_type() -> None:
    decomposer, _ = decomposer_for(
        FakeResponse(output_parsed=SimpleNamespace(elements=[]))
    )

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
        decomposer.decompose(claim())


def test_decomposer_maps_provider_failure() -> None:
    decomposer, _ = decomposer_for(error=RuntimeError("provider down"))

    with pytest.raises(PatentClaimElementProviderError, match="request failed"):
        decomposer.decompose(claim())


def test_decomposer_rejects_refusal() -> None:
    refusal_content = SimpleNamespace(refusal="Cannot comply.")
    message = SimpleNamespace(content=(refusal_content,))
    decomposer, _ = decomposer_for(
        FakeResponse(
            output_parsed=selection(),
            output=(message,),
        )
    )

    with pytest.raises(StructuredResponseRefusalError):
        decomposer.decompose(claim())
