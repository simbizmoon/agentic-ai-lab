"""Human review contracts and deterministic sheet formatting for Stage 9."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evals.stage9_golden_candidate_catalog import Stage9GoldenCandidate


class CandidateReviewDecision(StrEnum):
    DEVELOPMENT = "development"
    LOCKED = "locked"
    REJECTED = "rejected"


class CandidateSourceReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_id: str
    source_url: str
    identity_verified: bool
    original_content_accessed: bool
    evidence_excerpt: str | None = None
    evidence_location: str | None = None

    @model_validator(mode="after")
    def validate_evidence_pair(self) -> Self:
        if (self.evidence_excerpt is None) != (self.evidence_location is None):
            raise ValueError("evidence excerpt and location must appear together")
        for value in (
            self.source_id,
            self.source_url,
            self.evidence_excerpt,
            self.evidence_location,
        ):
            if value is not None and (not value.strip() or value != value.strip()):
                raise ValueError("source review text must be normalized")
        return self


class Stage9CandidateHumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    review_id: str
    candidate: Stage9GoldenCandidate
    reviewer_id: str
    reviewed_at: datetime
    question_is_useful: bool
    prohibited_claims_are_adequate: bool
    uncertainties_are_adequate: bool
    source_reviews: tuple[CandidateSourceReview, ...] = Field(min_length=1)
    unresolved_issues: tuple[str, ...] = ()
    decision: CandidateReviewDecision
    decision_reason: str

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        for value in (
            self.review_id,
            self.reviewer_id,
            self.decision_reason,
            *self.unresolved_issues,
        ):
            if not value.strip() or value != value.strip():
                raise ValueError("review text must be normalized and nonblank")
        if (
            tuple(item.source_id for item in self.source_reviews)
            != self.candidate.source_ids
        ):
            raise ValueError("source reviews must exactly match candidate source order")
        if (
            tuple(item.source_url for item in self.source_reviews)
            != self.candidate.source_urls
        ):
            raise ValueError("source review URLs must exactly match the candidate")
        if self.decision is CandidateReviewDecision.LOCKED:
            checks = (
                self.question_is_useful,
                self.prohibited_claims_are_adequate,
                self.uncertainties_are_adequate,
                not self.unresolved_issues,
                all(item.identity_verified for item in self.source_reviews),
                all(item.original_content_accessed for item in self.source_reviews),
                all(item.evidence_excerpt is not None for item in self.source_reviews),
            )
            if not all(checks):
                raise ValueError(
                    "locked review requires complete human and source evidence checks"
                )
        return self


def format_candidate_review_sheet(candidate: Stage9GoldenCandidate) -> str:
    """Render a blank, auditable human-review sheet without making a decision."""

    sources = "\n".join(
        f"- `{source_id}` — {url}\n  - identity verified: [ ]\n  - original accessed: [ ]\n  - exact excerpt:\n  - location:"
        for source_id, url in zip(
            candidate.source_ids, candidate.source_urls, strict=True
        )
    )
    return (
        f"# Stage 9 Candidate Review — {candidate.candidate_id}\n\n"
        f"Domain: `{candidate.domain.value}`\n\nQuestion: {candidate.research_question}\n\n"
        f"## Sources\n\n{sources}\n\n"
        "## Human checks\n\n- useful research question: [ ]\n"
        "- prohibited claims adequate: [ ]\n- uncertainty boundary adequate: [ ]\n\n"
        "## Decision\n\n- [ ] DEVELOPMENT\n- [ ] LOCKED\n- [ ] REJECTED\n"
        "- reviewer ID:\n- reviewed at (timezone required):\n- reason:\n- unresolved issues:\n"
    )
