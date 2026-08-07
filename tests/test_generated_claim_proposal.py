"""Tests for generated claim proposal schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.generated_claim_proposal import (
    GeneratedClaimProposal,
)


def test_generated_claim_proposal_accepts_valid_content() -> None:
    value = GeneratedClaimProposal(
        text=(
            "The SDK can expose Python functions "
            "as callable tools."
        ),
        rationale=(
            "The claim preserves the evidence meaning "
            "without adding unsupported scope."
        ),
    )

    assert (
        value.text
        == "The SDK can expose Python functions as callable tools."
    )
    assert (
        value.rationale
        == (
            "The claim preserves the evidence meaning "
            "without adding unsupported scope."
        )
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "text",
        "rationale",
    ],
)
def test_generated_claim_proposal_rejects_blank_text(
    field_name: str,
) -> None:
    values = {
        "text": "A supported factual claim.",
        "rationale": "The evidence directly supports the claim.",
    }
    values[field_name] = "   "

    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        GeneratedClaimProposal.model_validate(values)


def test_generated_claim_proposal_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GeneratedClaimProposal.model_validate(
            {
                "text": "A supported factual claim.",
                "rationale": "Supported by the supplied evidence.",
                "evidence_id": "evidence-001",
            }
        )


def test_generated_claim_proposal_is_frozen() -> None:
    value = GeneratedClaimProposal(
        text="A supported factual claim.",
        rationale="Supported by the supplied evidence.",
    )

    with pytest.raises(ValidationError):
        value.text = "Changed"
