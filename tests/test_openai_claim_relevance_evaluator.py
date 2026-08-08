"""Tests for OpenAI claim relevance evaluator."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.exceptions import (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
)
from app.research.openai_claim_relevance_evaluator import (
    CLAIM_RELEVANCE_BATCH_INSTRUCTIONS,
    CLAIM_RELEVANCE_INSTRUCTIONS,
    OpenAIClaimRelevanceEvaluator,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceBatchItemJudgment,
    ClaimRelevanceBatchJudgment,
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)


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


def completed_response(
    judgment: ClaimRelevanceJudgment | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="resp-001",
        _request_id="req-001",
        status="completed",
        output_parsed=judgment,
        output=[],
        usage=None,
    )


def evaluator_for(
    response: object,
) -> tuple[OpenAIClaimRelevanceEvaluator, FakeClient]:
    client = FakeClient(response)
    evaluator = OpenAIClaimRelevanceEvaluator(
        client=client,
        model="gpt-5",
    )
    return evaluator, client


def direct_judgment() -> ClaimRelevanceJudgment:
    return ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.96,
        rationale="The claim directly explains a requested mechanism.",
        issues=[],
    )


def test_evaluator_uses_only_request_and_claim_input() -> None:
    evaluator, client = evaluator_for(
        completed_response(direct_judgment())
    )

    result = evaluator.evaluate(
        question="How does the SDK support tool calling?",
        objective="Explain the tool-calling mechanisms.",
        claim_text="Python functions can be exposed as tools.",
    )

    assert (
        result.judgment.relevance_level
        is ClaimRelevanceLevel.DIRECTLY_RELEVANT
    )
    assert result.response_id == "resp-001"
    assert result.request_id == "req-001"

    call = client.responses.calls[0]
    assert call["model"] == "gpt-5"
    assert call["instructions"] == CLAIM_RELEVANCE_INSTRUCTIONS
    assert call["text_format"] is ClaimRelevanceJudgment
    assert call["store"] is False

    model_input = str(call["input"])
    assert '"question"' in model_input
    assert '"objective"' in model_input
    assert '"claim"' in model_input
    assert "evidence" not in model_input.casefold()
    assert "source_id" not in model_input
    assert "citation_id" not in model_input


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
    evaluator, _ = evaluator_for(
        completed_response(direct_judgment())
    )

    kwargs = {
        "question": "What is requested?",
        "objective": "Explain the requested topic.",
        "claim_text": "One relevant claim.",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        evaluator.evaluate(**kwargs)


def test_evaluator_rejects_blank_model() -> None:
    with pytest.raises(ValueError):
        OpenAIClaimRelevanceEvaluator(
            client=FakeClient(
                completed_response(direct_judgment())
            ),
            model=" ",
        )


def test_evaluator_rejects_incomplete_response() -> None:
    evaluator, _ = evaluator_for(
        SimpleNamespace(
            id="resp-001",
            status="incomplete",
            output_parsed=None,
            output=[],
            usage=None,
        )
    )

    with pytest.raises(StructuredResponseIncompleteError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_evaluator_rejects_noncompleted_response() -> None:
    evaluator, _ = evaluator_for(
        SimpleNamespace(
            id="resp-001",
            status="failed",
            output_parsed=None,
            output=[],
            usage=None,
        )
    )

    with pytest.raises(StructuredResponseStatusError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_evaluator_rejects_missing_parsed_result() -> None:
    evaluator, _ = evaluator_for(
        completed_response(None)
    )

    with pytest.raises(StructuredResponseParseError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_evaluator_rejects_wrong_parsed_type() -> None:
    evaluator, _ = evaluator_for(
        completed_response(
            SimpleNamespace(
                relevance_level="directly_relevant"
            )
        )
    )

    with pytest.raises(StructuredResponseParseError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_prompt_separates_relevance_from_truth_and_support() -> None:
    instructions = CLAIM_RELEVANCE_INSTRUCTIONS.casefold()

    assert "do not evaluate whether the claim is factually true" in instructions
    assert "do not evaluate whether evidence supports the claim" in instructions
    assert "same topic, product, entity, or domain alone" in instructions
    assert "category is the policy judgment" in instructions


def test_refusal_is_rejected() -> None:
    response = completed_response(direct_judgment())
    response.output = [
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="refusal",
                    refusal="Cannot evaluate.",
                )
            ]
        )
    ]
    evaluator, _ = evaluator_for(response)

    with pytest.raises(StructuredResponseRefusalError):
        evaluator.evaluate(
            question="Question?",
            objective="Objective.",
            claim_text="Claim.",
        )


def test_prompt_v2_encodes_refined_relevance_policy() -> None:
    instructions = CLAIM_RELEVANCE_INSTRUCTIONS.casefold()

    assert "claim itself contributes to constructing" in instructions
    assert "materially satisfies both" in instructions
    assert "same topic, product, entity, or domain alone" in instructions
    assert "post-hoc auditing" in instructions
    assert "preventive or access-control mechanism" in instructions
    assert "change tracking or version" in instructions
    assert "storage alone is not an evaluation method" in instructions
    assert "prefer partially_relevant rather than directly_relevant" in instructions

def test_prompt_v2_1_refines_partial_boundary() -> None:
    instructions = CLAIM_RELEVANCE_INSTRUCTIONS.casefold()

    assert "comparison baseline" in instructions
    assert "measurement signal" in instructions
    assert "practical prerequisite" in instructions
    assert "meaningful comparison baseline" in instructions
    assert "observability alone is not the control" in instructions
    assert "materially required to implement or evaluate" in instructions

def batch_judgment(
    *item_ids: str,
) -> ClaimRelevanceBatchJudgment:
    return ClaimRelevanceBatchJudgment(
        items=[
            ClaimRelevanceBatchItemJudgment(
                item_id=item_id,
                judgment=direct_judgment(),
            )
            for item_id in item_ids
        ]
    )


def test_batch_evaluator_uses_one_structured_request() -> None:
    evaluator, client = evaluator_for(
        completed_response(
            batch_judgment(
                "item-001",
                "item-002",
                "item-003",
            )
        )
    )

    result = evaluator.evaluate_batch(
        question="Question?",
        objective="Objective.",
        claim_items=[
            ("item-001", "Claim one."),
            ("item-002", "Claim two."),
            ("item-003", "Claim three."),
        ],
    )

    assert len(client.responses.calls) == 1
    assert set(result.judgments) == {
        "item-001",
        "item-002",
        "item-003",
    }
    call = client.responses.calls[0]
    assert (
        call["instructions"]
        == CLAIM_RELEVANCE_BATCH_INSTRUCTIONS
    )
    assert call["text_format"] is ClaimRelevanceBatchJudgment
    model_input = str(call["input"])
    assert '"item_id": "item-001"' in model_input
    assert '"claim": "Claim one."' in model_input
    assert "evidence" not in model_input.casefold()


def test_batch_evaluator_maps_reordered_output_by_item_id() -> None:
    evaluator, _ = evaluator_for(
        completed_response(
            batch_judgment(
                "item-003",
                "item-001",
                "item-002",
            )
        )
    )

    result = evaluator.evaluate_batch(
        question="Question?",
        objective="Objective.",
        claim_items=[
            ("item-001", "Claim one."),
            ("item-002", "Claim two."),
            ("item-003", "Claim three."),
        ],
    )

    assert set(result.judgments) == {
        "item-001",
        "item-002",
        "item-003",
    }


def test_batch_evaluator_rejects_mismatched_item_ids() -> None:
    evaluator, _ = evaluator_for(
        completed_response(
            batch_judgment(
                "item-001",
                "item-003",
            )
        )
    )

    with pytest.raises(
        StructuredResponseParseError,
        match="item IDs did not match",
    ):
        evaluator.evaluate_batch(
            question="Question?",
            objective="Objective.",
            claim_items=[
                ("item-001", "Claim one."),
                ("item-002", "Claim two."),
            ],
        )
