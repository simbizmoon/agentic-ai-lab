"""Tests for OpenAI semantic citation entailment evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.research.openai_semantic_citation_evaluator import (
    OpenAISemanticCitationEvaluator,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
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
    input_tokens_details: FakeInputTokenDetails = (
        FakeInputTokenDetails()
    )
    output_tokens: int = 8
    output_tokens_details: FakeOutputTokenDetails = (
        FakeOutputTokenDetails()
    )
    total_tokens: int = 18


@dataclass(frozen=True)
class FakeResponse:
    output_parsed: object
    status: str = "completed"
    id: str = "resp-semantic-001"
    _request_id: str | None = "req-semantic-001"
    usage: FakeUsage | None = field(
        default_factory=FakeUsage
    )
    output: list[object] = field(
        default_factory=list
    )


@dataclass
class FakeResponses:
    response: FakeResponse
    calls: list[dict[str, object]] = field(
        default_factory=list
    )

    def parse(
        self,
        **kwargs: object,
    ) -> FakeResponse:
        self.calls.append(kwargs)
        return self.response


@dataclass
class FakeClient:
    response: FakeResponse

    def __post_init__(self) -> None:
        self.responses = FakeResponses(
            self.response
        )


def judgment(
    score: float,
    support_level: SemanticCitationSupportLevel = (
        SemanticCitationSupportLevel.FULLY_SUPPORTED
    ),
) -> SemanticCitationJudgment:
    return SemanticCitationJudgment(
        support_level=support_level,
        entailment_score=score,
        rationale="Evidence support was evaluated.",
        issues=[],
    )


def evaluator(
    score: float,
) -> tuple[
    OpenAISemanticCitationEvaluator,
    FakeClient,
]:
    client = FakeClient(
        FakeResponse(
            output_parsed=judgment(score)
        )
    )

    return (
        OpenAISemanticCitationEvaluator(
            client=client,
            model="test-model",
        ),
        client,
    )


@pytest.mark.parametrize(
    ("support_level", "expected"),
    [
        (
            SemanticCitationSupportLevel.FULLY_SUPPORTED,
            ResearchCitationDecision.VERIFIED,
        ),
        (
            SemanticCitationSupportLevel.PARTIALLY_SUPPORTED,
            ResearchCitationDecision.NEEDS_REVISION,
        ),
        (
            SemanticCitationSupportLevel.UNSUPPORTED,
            ResearchCitationDecision.REJECTED,
        ),
        (
            SemanticCitationSupportLevel.CONTRADICTED,
            ResearchCitationDecision.REJECTED,
        ),
    ],
)
def test_support_level_maps_to_deterministic_decision(
    support_level: SemanticCitationSupportLevel,
    expected: ResearchCitationDecision,
) -> None:
    client = FakeClient(
        FakeResponse(
            output_parsed=judgment(
                0.5,
                support_level,
            )
        )
    )

    value = OpenAISemanticCitationEvaluator(
        client=client,
        model="test-model",
    )

    result = value.evaluate(
        claim_text="The runner invokes tools.",
        evidence_excerpt=(
            "The runner invokes tools when needed."
        ),
    )

    assert result.decision is expected


def test_evaluator_uses_structured_response() -> None:
    value, client = evaluator(0.9)

    value.evaluate(
        claim_text="The runner invokes tools.",
        evidence_excerpt=(
            "The runner invokes tools when needed."
        ),
    )

    assert len(client.responses.calls) == 1

    call = client.responses.calls[0]

    assert call["model"] == "test-model"
    assert (
        call["text_format"]
        is SemanticCitationJudgment
    )
    assert call["store"] is False
    assert isinstance(call["instructions"], str)
    assert call["instructions"]


def test_evaluator_returns_usage_and_ids() -> None:
    value, _ = evaluator(0.9)

    result = value.evaluate(
        claim_text="The runner invokes tools.",
        evidence_excerpt=(
            "The runner invokes tools when needed."
        ),
    )

    assert result.response_id == "resp-semantic-001"
    assert result.request_id == "req-semantic-001"
    assert result.usage is not None
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 8
    assert result.usage.total_tokens == 18


@pytest.mark.parametrize(
    ("claim_text", "evidence_excerpt"),
    [
        (" ", "Evidence."),
        ("Claim.", " "),
    ],
)
def test_blank_input_is_rejected_before_api_call(
    claim_text: str,
    evidence_excerpt: str,
) -> None:
    value, client = evaluator(0.9)

    with pytest.raises(
        ValueError,
        match="must not be blank",
    ):
        value.evaluate(
            claim_text=claim_text,
            evidence_excerpt=evidence_excerpt,
        )

    assert client.responses.calls == []
