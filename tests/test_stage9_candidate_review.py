"""Offline tests for Stage 9 human-review gates."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.evals.stage9_candidate_review import (
    CandidateReviewDecision,
    CandidateSourceReview,
    Stage9CandidateHumanReview,
    format_candidate_review_sheet,
)
from app.evals.stage9_golden_candidate_catalog import (
    build_stage9_golden_candidate_catalog,
)


def _candidate():
    return build_stage9_golden_candidate_catalog().candidates[0]


def _source_reviews(*, complete: bool):
    return tuple(
        CandidateSourceReview(
            source_id=sid,
            source_url=url,
            identity_verified=complete,
            original_content_accessed=complete,
            evidence_excerpt="Verified excerpt." if complete else None,
            evidence_location="Section 1" if complete else None,
        )
        for sid, url in zip(
            _candidate().source_ids, _candidate().source_urls, strict=True
        )
    )


def test_complete_human_review_can_lock_candidate() -> None:
    value = Stage9CandidateHumanReview(
        review_id="review-tech-01",
        candidate=_candidate(),
        reviewer_id="human-reviewer-01",
        reviewed_at=datetime(2026, 8, 28, tzinfo=UTC),
        question_is_useful=True,
        prohibited_claims_are_adequate=True,
        uncertainties_are_adequate=True,
        source_reviews=_source_reviews(complete=True),
        decision=CandidateReviewDecision.LOCKED,
        decision_reason="Original source and exact evidence were reviewed.",
    )
    assert value.decision is CandidateReviewDecision.LOCKED


def test_incomplete_source_review_cannot_lock_candidate() -> None:
    with pytest.raises(ValidationError, match="complete"):
        Stage9CandidateHumanReview(
            review_id="review-tech-01",
            candidate=_candidate(),
            reviewer_id="human-reviewer-01",
            reviewed_at=datetime(2026, 8, 28, tzinfo=UTC),
            question_is_useful=True,
            prohibited_claims_are_adequate=True,
            uncertainties_are_adequate=True,
            source_reviews=_source_reviews(complete=False),
            decision=CandidateReviewDecision.LOCKED,
            decision_reason="Unsafe premature lock.",
        )


def test_development_decision_preserves_incomplete_review() -> None:
    value = Stage9CandidateHumanReview(
        review_id="review-tech-01",
        candidate=_candidate(),
        reviewer_id="human-reviewer-01",
        reviewed_at=datetime(2026, 8, 28, tzinfo=UTC),
        question_is_useful=True,
        prohibited_claims_are_adequate=True,
        uncertainties_are_adequate=False,
        source_reviews=_source_reviews(complete=False),
        unresolved_issues=("Evidence review pending.",),
        decision=CandidateReviewDecision.DEVELOPMENT,
        decision_reason="Keep for further review.",
    )
    assert value.unresolved_issues


def test_review_sheet_is_blank_and_contains_every_source() -> None:
    sheet = format_candidate_review_sheet(_candidate())
    assert "- [ ] LOCKED" in sheet
    assert "human-reviewer-01" not in sheet
    assert all(source_id in sheet for source_id in _candidate().source_ids)
