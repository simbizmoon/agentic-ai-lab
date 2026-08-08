"""Tests for semantic evidence relevance judgment schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceBatchItemJudgment,
    EvidenceRelevanceBatchJudgment,
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)


def judgment(**overrides: object) -> EvidenceRelevanceJudgment:
    """Create one valid evidence relevance judgment."""

    payload: dict[str, object] = {
        "relevance_level": EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
        "relevance_score": 0.55,
        "rationale": (
            "The passage provides useful supporting context "
            "for the requested answer."
        ),
        "issues": ["Does not itself explain the full mechanism."],
    }
    payload.update(overrides)
    return EvidenceRelevanceJudgment(**payload)


def test_accepts_valid_judgment() -> None:
    value = judgment()

    assert (
        value.relevance_level
        is EvidenceRelevanceLevel.PARTIALLY_RELEVANT
    )
    assert value.relevance_score == 0.55


@pytest.mark.parametrize("level", list(EvidenceRelevanceLevel))
def test_accepts_all_relevance_levels(
    level: EvidenceRelevanceLevel,
) -> None:
    score = (
        0.9
        if level is EvidenceRelevanceLevel.DIRECTLY_RELEVANT
        else 0.5
        if level is EvidenceRelevanceLevel.PARTIALLY_RELEVANT
        else 0.1
    )

    value = judgment(
        relevance_level=level,
        relevance_score=score,
    )

    assert value.relevance_level is level


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_rejects_out_of_range_score(score: float) -> None:
    with pytest.raises(ValidationError):
        judgment(relevance_score=score)


def test_rejects_blank_rationale() -> None:
    with pytest.raises(
        ValidationError,
        match="rationale must not be blank",
    ):
        judgment(rationale="   ")


def test_rejects_blank_issue() -> None:
    with pytest.raises(
        ValidationError,
        match="issues must not contain blank values",
    ):
        judgment(issues=["valid", "   "])


def test_rejects_duplicate_issues_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="issues must be unique",
    ):
        judgment(
            issues=[
                "Missing mechanism detail",
                " missing mechanism detail ",
            ]
        )


def test_directly_relevant_rejects_zero_score() -> None:
    with pytest.raises(
        ValidationError,
        match="directly_relevant must not have zero relevance_score",
    ):
        judgment(
            relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
            relevance_score=0.0,
        )


def test_irrelevant_rejects_maximum_score() -> None:
    with pytest.raises(
        ValidationError,
        match="irrelevant must not have maximum relevance_score",
    ):
        judgment(
            relevance_level=EvidenceRelevanceLevel.IRRELEVANT,
            relevance_score=1.0,
        )


def test_score_remains_diagnostic_not_threshold_policy() -> None:
    low_direct = judgment(
        relevance_level=EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
        relevance_score=0.2,
    )
    high_irrelevant = judgment(
        relevance_level=EvidenceRelevanceLevel.IRRELEVANT,
        relevance_score=0.8,
    )

    assert low_direct.relevance_score == 0.2
    assert high_irrelevant.relevance_score == 0.8


def test_model_is_strict() -> None:
    with pytest.raises(ValidationError):
        EvidenceRelevanceJudgment(
            relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            relevance_score="0.55",
            rationale="Useful context.",
            issues=[],
        )


def test_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceRelevanceJudgment(
            relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            relevance_score=0.55,
            rationale="Useful context.",
            issues=[],
            unexpected="no",
        )


def test_model_is_frozen() -> None:
    value = judgment()

    with pytest.raises(ValidationError):
        value.relevance_score = 0.9



def test_batch_judgment_rejects_blank_item_id() -> None:
    with pytest.raises(
        ValidationError,
        match="item_id must not be blank",
    ):
        EvidenceRelevanceBatchJudgment(
            items=[
                EvidenceRelevanceBatchItemJudgment(
                    item_id=" ",
                    judgment=judgment(),
                )
            ]
        )


def test_batch_judgment_rejects_duplicate_ids_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="batch item IDs must be unique",
    ):
        EvidenceRelevanceBatchJudgment(
            items=[
                EvidenceRelevanceBatchItemJudgment(
                    item_id="item-001",
                    judgment=judgment(),
                ),
                EvidenceRelevanceBatchItemJudgment(
                    item_id="ITEM-001",
                    judgment=judgment(),
                ),
            ]
        )
