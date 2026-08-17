"""Tests for OpenAI grounded patent technical-concept selection."""

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
    StructuredResponseValidationError,
)
from app.research.openai_patent_technical_concept_generator import (
    PATENT_TECHNICAL_CONCEPT_INSTRUCTIONS,
    OpenAIPatentTechnicalConceptGenerator,
    PatentTechnicalConceptProviderError,
)
from app.schemas.patent_research_request import PatentResearchRequest
from app.schemas.patent_technical_concept import (
    PatentTechnicalConcept,
    PatentTechnicalConceptRole,
    PatentTechnicalConceptSelection,
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
    id: str = "resp-patent-concept"
    _request_id: str | None = "req-patent-concept"
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


def request() -> PatentResearchRequest:
    return PatentResearchRequest(
        question=("How can pressure sensors detect seat occupancy without user input?"),
        objective=(
            "Identify pressure sensors and automatic state detection "
            "for seat occupancy."
        ),
    )


def selection(
    *concepts: PatentTechnicalConcept,
) -> PatentTechnicalConceptSelection:
    return PatentTechnicalConceptSelection(concepts=concepts)


def primary(*terms: str) -> PatentTechnicalConcept:
    return PatentTechnicalConcept(
        role=PatentTechnicalConceptRole.PRIMARY,
        terms=terms,
    )


def alternate(*terms: str) -> PatentTechnicalConcept:
    return PatentTechnicalConcept(
        role=PatentTechnicalConceptRole.ALTERNATE,
        terms=terms,
    )


def generator_for(
    response: FakeResponse | None = None,
    *,
    error: Exception | None = None,
) -> tuple[OpenAIPatentTechnicalConceptGenerator, FakeResponses]:
    responses = FakeResponses(response=response, error=error)
    return (
        OpenAIPatentTechnicalConceptGenerator(
            client=FakeClient(responses),
            model="test-model",
        ),
        responses,
    )


def test_generator_uses_one_structured_request_and_binds_plan() -> None:
    generator, responses = generator_for(
        FakeResponse(
            output_parsed=selection(
                primary("pressure sensors", "seat occupancy"),
                alternate("automatic state detection"),
            )
        )
    )

    result = generator.generate(request())

    assert result.plan.request == request()
    assert len(result.plan.concepts) == 2
    assert result.response_id == "resp-patent-concept"
    assert result.request_id == "req-patent-concept"
    assert len(responses.calls) == 1

    call = responses.calls[0]
    assert call["model"] == "test-model"
    assert call["instructions"] == PATENT_TECHNICAL_CONCEPT_INSTRUCTIONS
    assert call["text_format"] is PatentTechnicalConceptSelection
    assert call["store"] is False
    assert "pressure sensors" in str(call["input"])
    assert "seat occupancy" in str(call["input"])


def test_generator_preserves_provider_usage() -> None:
    generator, _ = generator_for(
        FakeResponse(
            output_parsed=selection(primary("pressure sensors")),
            usage=FakeUsage(
                input_tokens=8,
                input_tokens_details=FakeInputTokenDetails(cached_tokens=2),
                output_tokens=5,
                output_tokens_details=FakeOutputTokenDetails(reasoning_tokens=1),
                total_tokens=13,
            ),
        )
    )

    result = generator.generate(request())

    assert result.usage is not None
    assert result.usage.input_tokens == 8
    assert result.usage.cached_input_tokens == 2
    assert result.usage.output_tokens == 5
    assert result.usage.reasoning_tokens == 1
    assert result.usage.total_tokens == 13


def test_generator_prompt_forbids_unbounded_patent_expansion() -> None:
    instructions = PATENT_TECHNICAL_CONCEPT_INSTRUCTIONS

    assert "Do not invent terminology" in instructions
    assert "Do not generate synonyms" in instructions
    assert "Do not translate terms" in instructions
    assert "Do not generate EPO CQL" in instructions
    assert "Do not generate IPC/CPC" in instructions
    assert "Do not invent patent numbers" in instructions
    assert "legal conclusions" in instructions


def test_generator_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model must not be blank"):
        OpenAIPatentTechnicalConceptGenerator(
            client=FakeClient(FakeResponses()),
            model=" ",
        )


def test_generator_rejects_ungrounded_model_term() -> None:
    generator, _ = generator_for(
        FakeResponse(output_parsed=selection(primary("capacitive sensor")))
    )

    with pytest.raises(
        StructuredResponseValidationError,
        match="was not grounded",
    ):
        generator.generate(request())


def test_generator_rejects_incomplete_response() -> None:
    generator, _ = generator_for(
        FakeResponse(
            output_parsed=selection(primary("pressure sensors")),
            status="incomplete",
        )
    )

    with pytest.raises(StructuredResponseIncompleteError):
        generator.generate(request())


def test_generator_rejects_unexpected_status() -> None:
    generator, _ = generator_for(
        FakeResponse(
            output_parsed=selection(primary("pressure sensors")),
            status="queued",
        )
    )

    with pytest.raises(StructuredResponseStatusError):
        generator.generate(request())


def test_generator_rejects_empty_parsed_output() -> None:
    generator, _ = generator_for(FakeResponse(output_parsed=None))

    with pytest.raises(StructuredResponseParseError, match="was empty"):
        generator.generate(request())


def test_generator_rejects_wrong_parsed_type() -> None:
    generator, _ = generator_for(
        FakeResponse(output_parsed=SimpleNamespace(concepts=[]))
    )

    with pytest.raises(StructuredResponseParseError, match="invalid type"):
        generator.generate(request())


def test_generator_maps_provider_failure() -> None:
    generator, _ = generator_for(error=RuntimeError("provider down"))

    with pytest.raises(
        PatentTechnicalConceptProviderError,
        match="request failed",
    ):
        generator.generate(request())


def test_generator_rejects_refusal() -> None:
    refusal_content = SimpleNamespace(refusal="Cannot comply.")
    message = SimpleNamespace(
        content=(refusal_content,),
    )
    generator, _ = generator_for(
        FakeResponse(
            output_parsed=selection(primary("pressure sensors")),
            output=(message,),
        )
    )

    with pytest.raises(StructuredResponseRefusalError):
        generator.generate(request())
