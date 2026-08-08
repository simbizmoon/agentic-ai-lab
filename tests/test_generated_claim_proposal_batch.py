"""Tests for batched generated claim proposal schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.generated_claim_proposal import (
    GeneratedClaimProposal,
    GeneratedClaimProposalBatch,
    GeneratedClaimProposalBatchItem,
)


def proposal() -> GeneratedClaimProposal:
    return GeneratedClaimProposal(
        text="A bounded factual claim.",
        rationale="It stays within supplied evidence.",
    )


def test_batch_accepts_unique_item_ids() -> None:
    value = GeneratedClaimProposalBatch(
        items=[
            GeneratedClaimProposalBatchItem(
                item_id="item-001",
                proposal=proposal(),
            ),
            GeneratedClaimProposalBatchItem(
                item_id="item-002",
                proposal=proposal(),
            ),
        ]
    )
    assert len(value.items) == 2


def test_batch_rejects_duplicate_ids_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="batch item IDs must be unique"):
        GeneratedClaimProposalBatch(
            items=[
                GeneratedClaimProposalBatchItem(
                    item_id="item-001", proposal=proposal()
                ),
                GeneratedClaimProposalBatchItem(
                    item_id="ITEM-001", proposal=proposal()
                ),
            ]
        )
