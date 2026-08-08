"""Tests for OpenAI semantic citation entailment evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.exceptions import StructuredResponseParseError
from app.research.openai_semantic_citation_evaluator import (
    SEMANTIC_CITATION_BATCH_INSTRUCTIONS,
    OpenAISemanticCitationEvaluator,
)
from app.research.research_citation_verifier_executor import (
    ResearchCitationDecision,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationBatchItemJudgment,
    SemanticCitationBatchJudgment,
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

def batch_judgment(
    *item_ids: str,
) -> SemanticCitationBatchJudgment:
    return SemanticCitationBatchJudgment(
        items=[
            SemanticCitationBatchItemJudgment(
                item_id=item_id,
                judgment=judgment(0.9),
            )
            for item_id in item_ids
        ]
    )


def test_batch_evaluator_uses_one_structured_request() -> None:
    client = FakeClient(
        FakeResponse(
            output_parsed=batch_judgment(
                "item-001",
                "item-002",
                "item-003",
            )
        )
    )
    value = OpenAISemanticCitationEvaluator(
        client=client,
        model="test-model",
    )

    result = value.evaluate_batch(
        citation_items=[
            ("item-001", "Claim one.", "Evidence one."),
            ("item-002", "Claim two.", "Evidence two."),
            ("item-003", "Claim three.", "Evidence three."),
        ]
    )

    assert len(client.responses.calls) == 1
    assert set(result.judgments) == {
        "item-001",
        "item-002",
        "item-003",
    }
    assert all(
        decision is ResearchCitationDecision.VERIFIED
        for decision in result.decisions.values()
    )

    call = client.responses.calls[0]
    assert (
        call["instructions"]
        == SEMANTIC_CITATION_BATCH_INSTRUCTIONS
    )
    assert call["text_format"] is SemanticCitationBatchJudgment
    model_input = str(call["input"])
    assert '"item_id": "item-001"' in model_input
    assert '"claim": "Claim one."' in model_input
    assert '"evidence": "Evidence one."' in model_input


def test_batch_evaluator_maps_reordered_output_by_item_id() -> None:
    client = FakeClient(
        FakeResponse(
            output_parsed=batch_judgment(
                "item-003",
                "item-001",
                "item-002",
            )
        )
    )
    value = OpenAISemanticCitationEvaluator(
        client=client,
        model="test-model",
    )

    result = value.evaluate_batch(
        citation_items=[
            ("item-001", "Claim one.", "Evidence one."),
            ("item-002", "Claim two.", "Evidence two."),
            ("item-003", "Claim three.", "Evidence three."),
        ]
    )

    assert set(result.judgments) == {
        "item-001",
        "item-002",
        "item-003",
    }


def test_batch_evaluator_rejects_mismatched_item_ids() -> None:
    client = FakeClient(
        FakeResponse(
            output_parsed=batch_judgment(
                "item-001",
                "item-003",
            )
        )
    )
    value = OpenAISemanticCitationEvaluator(
        client=client,
        model="test-model",
    )

    with pytest.raises(
        StructuredResponseParseError,
        match="item IDs did not match",
    ):
        value.evaluate_batch(
            citation_items=[
                ("item-001", "Claim one.", "Evidence one."),
                ("item-002", "Claim two.", "Evidence two."),
            ]
        )
