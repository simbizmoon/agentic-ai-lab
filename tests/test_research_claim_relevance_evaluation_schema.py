"""Tests for production claim relevance evaluation schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)
from app.schemas.research_claim_relevance_evaluation import (
    ResearchClaimRelevanceEvaluation,
)


def evaluation(
    **overrides: object,
) -> ResearchClaimRelevanceEvaluation:
    values: dict[str, object] = {
        "evaluation_id": "claim-relevance-evaluation-1",
        "claim_id": "claim-1",
        "relevance_level": (
            ClaimRelevanceLevel.PARTIALLY_RELEVANT
        ),
        "relevance_score": 0.55,
        "rationale": (
            "The claim supplies a material prerequisite "
            "but not the requested mechanism."
        ),
        "issues": [
            "Does not provide the requested mechanism."
        ],
        "metadata": {
            "response_id": "resp-1",
        },
    }
    values.update(overrides)

    return ResearchClaimRelevanceEvaluation.model_validate(
        values
    )


def test_research_claim_relevance_evaluation_accepts_valid_value(
) -> None:
    value = evaluation()

    assert (
        value.evaluation_id
        == "claim-relevance-evaluation-1"
    )
    assert value.claim_id == "claim-1"
    assert (
        value.relevance_level
        is ClaimRelevanceLevel.PARTIALLY_RELEVANT
    )
    assert value.relevance_score == 0.55
    assert value.metadata["response_id"] == "resp-1"


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("evaluation_id", ""),
        ("evaluation_id", "   "),
        ("claim_id", ""),
        ("claim_id", "   "),
        ("rationale", ""),
        ("rationale", "   "),
    ],
)
def test_research_claim_relevance_evaluation_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    with pytest.raises(ValidationError):
        evaluation(
            **{
                field_name: field_value,
            }
        )


@pytest.mark.parametrize(
    "score",
    [-0.01, 1.01],
)
def test_research_claim_relevance_evaluation_rejects_out_of_range_score(
    score: float,
) -> None:
    with pytest.raises(ValidationError):
        evaluation(relevance_score=score)


def test_research_claim_relevance_evaluation_rejects_blank_issue(
) -> None:
    with pytest.raises(ValidationError):
        evaluation(
            issues=[
                "Useful issue.",
                "   ",
            ]
        )


def test_research_claim_relevance_evaluation_rejects_duplicate_issues(
) -> None:
    with pytest.raises(ValidationError):
        evaluation(
            issues=[
                "Missing mechanism.",
                " missing mechanism. ",
            ]
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"": "value"},
        {"   ": "value"},
        {"key": ""},
        {"key": "   "},
    ],
)
def test_research_claim_relevance_evaluation_rejects_blank_metadata(
    metadata: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        evaluation(metadata=metadata)


def test_research_claim_relevance_evaluation_is_strict(
) -> None:
    with pytest.raises(ValidationError):
        evaluation(relevance_score="0.55")


def test_research_claim_relevance_evaluation_is_frozen(
) -> None:
    value = evaluation()

    with pytest.raises(ValidationError):
        value.claim_id = "claim-2"


def test_research_claim_relevance_evaluation_forbids_extra_fields(
) -> None:
    values = evaluation().model_dump()
    values["unexpected"] = "value"

    with pytest.raises(ValidationError):
        ResearchClaimRelevanceEvaluation.model_validate(
            values
        )
