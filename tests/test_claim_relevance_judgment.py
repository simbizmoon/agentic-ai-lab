"""Tests for claim relevance judgment schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceBatchItemJudgment,
    ClaimRelevanceBatchJudgment,
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)


def test_claim_relevance_levels_are_stable() -> None:
    assert (
        ClaimRelevanceLevel.DIRECTLY_RELEVANT.value
        == "directly_relevant"
    )
    assert (
        ClaimRelevanceLevel.PARTIALLY_RELEVANT.value
        == "partially_relevant"
    )
    assert (
        ClaimRelevanceLevel.IRRELEVANT.value
        == "irrelevant"
    )


def test_judgment_accepts_direct_relevance() -> None:
    judgment = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.95,
        rationale="The claim directly answers the requested mechanism.",
        issues=[],
    )

    assert (
        judgment.relevance_level
        is ClaimRelevanceLevel.DIRECTLY_RELEVANT
    )
    assert judgment.relevance_score == 0.95


def test_judgment_accepts_partial_relevance() -> None:
    judgment = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.PARTIALLY_RELEVANT,
        relevance_score=0.55,
        rationale=(
            "The claim is on-topic but does not directly answer "
            "the main mechanism."
        ),
        issues=["Does not address the requested mechanism directly."],
    )

    assert judgment.issues


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("relevance_score", -0.1),
        ("relevance_score", 1.1),
        ("rationale", " "),
        ("issues", [""]),
    ],
)
def test_judgment_rejects_invalid_values(
    field: str,
    value: object,
) -> None:
    payload: dict[str, object] = {
        "relevance_level": ClaimRelevanceLevel.PARTIALLY_RELEVANT,
        "relevance_score": 0.5,
        "rationale": "Relevant only in part.",
        "issues": [],
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ClaimRelevanceJudgment.model_validate(payload)


def test_judgment_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ClaimRelevanceJudgment.model_validate(
            {
                "relevance_level": "directly_relevant",
                "relevance_score": 0.9,
                "rationale": "Directly answers the question.",
                "issues": [],
                "claim_id": "model-must-not-return-this",
            }
        )


def test_score_does_not_define_category_thresholds() -> None:
    low_direct = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.2,
        rationale="Category remains the policy signal.",
        issues=[],
    )
    high_irrelevant = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.IRRELEVANT,
        relevance_score=0.8,
        rationale="Score remains diagnostic rather than policy.",
        issues=["Does not answer the requested research question."],
    )

    assert low_direct.relevance_score == 0.2
    assert high_irrelevant.relevance_score == 0.8


@pytest.mark.parametrize(
    ("level", "score"),
    [
        (ClaimRelevanceLevel.DIRECTLY_RELEVANT, 0.0),
        (ClaimRelevanceLevel.IRRELEVANT, 1.0),
    ],
)
def test_judgment_rejects_impossible_score_extremes(
    level: ClaimRelevanceLevel,
    score: float,
) -> None:
    with pytest.raises(ValidationError):
        ClaimRelevanceJudgment(
            relevance_level=level,
            relevance_score=score,
            rationale="Extreme score contradicts the category.",
            issues=[],
        )

def test_batch_judgment_rejects_blank_item_id() -> None:
    judgment = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.PARTIALLY_RELEVANT,
        relevance_score=0.5,
        rationale="Useful context.",
        issues=[],
    )
    with pytest.raises(
        ValidationError,
        match="item_id must not be blank",
    ):
        ClaimRelevanceBatchJudgment(
            items=[
                ClaimRelevanceBatchItemJudgment(
                    item_id=" ",
                    judgment=judgment,
                )
            ]
        )


def test_batch_judgment_rejects_duplicate_ids_case_insensitively(
) -> None:
    judgment = ClaimRelevanceJudgment(
        relevance_level=ClaimRelevanceLevel.PARTIALLY_RELEVANT,
        relevance_score=0.5,
        rationale="Useful context.",
        issues=[],
    )
    with pytest.raises(
        ValidationError,
        match="batch item IDs must be unique",
    ):
        ClaimRelevanceBatchJudgment(
            items=[
                ClaimRelevanceBatchItemJudgment(
                    item_id="item-001",
                    judgment=judgment,
                ),
                ClaimRelevanceBatchItemJudgment(
                    item_id="ITEM-001",
                    judgment=judgment,
                ),
            ]
        )
