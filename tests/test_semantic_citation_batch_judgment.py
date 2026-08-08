"""Tests for batched semantic citation judgment schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.semantic_citation_judgment import (
    SemanticCitationBatchItemJudgment,
    SemanticCitationBatchJudgment,
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)


def judgment() -> SemanticCitationJudgment:
    return SemanticCitationJudgment(
        support_level=SemanticCitationSupportLevel.FULLY_SUPPORTED,
        entailment_score=0.9,
        rationale="Evidence supports the claim.",
        issues=[],
    )


def test_batch_accepts_unique_item_ids() -> None:
    value = SemanticCitationBatchJudgment(
        items=[
            SemanticCitationBatchItemJudgment(
                item_id="item-001",
                judgment=judgment(),
            ),
            SemanticCitationBatchItemJudgment(
                item_id="item-002",
                judgment=judgment(),
            ),
        ]
    )

    assert len(value.items) == 2


def test_batch_rejects_blank_item_id() -> None:
    with pytest.raises(
        ValidationError,
        match="item_id must not be blank",
    ):
        SemanticCitationBatchJudgment(
            items=[
                SemanticCitationBatchItemJudgment(
                    item_id=" ",
                    judgment=judgment(),
                )
            ]
        )


def test_batch_rejects_duplicate_ids_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="batch item IDs must be unique",
    ):
        SemanticCitationBatchJudgment(
            items=[
                SemanticCitationBatchItemJudgment(
                    item_id="item-001",
                    judgment=judgment(),
                ),
                SemanticCitationBatchItemJudgment(
                    item_id="ITEM-001",
                    judgment=judgment(),
                ),
            ]
        )
