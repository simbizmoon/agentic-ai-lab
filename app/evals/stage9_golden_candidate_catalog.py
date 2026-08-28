"""Human-review candidate catalog for the Stage 9 real-research dataset."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain


class CandidateVerificationStatus(StrEnum):
    SOURCE_IDENTITY_VERIFIED = "source_identity_verified"


class Stage9GoldenCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    candidate_id: str
    domain: Stage9EvaluationDomain
    research_question: str
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    source_urls: tuple[str, ...] = Field(min_length=1, max_length=8)
    prohibited_claims: tuple[str, ...] = Field(min_length=1)
    expected_uncertainties: tuple[str, ...] = Field(min_length=1)
    verification_status: CandidateVerificationStatus
    locked: bool = False

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        text = (
            self.candidate_id,
            self.research_question,
            *self.source_ids,
            *self.source_urls,
            *self.prohibited_claims,
            *self.expected_uncertainties,
        )
        if any(not value.strip() or value != value.strip() for value in text):
            raise ValueError("candidate text must be normalized and nonblank")
        if len(self.source_ids) != len(self.source_urls):
            raise ValueError("source IDs and URLs must align")
        if self.locked:
            raise ValueError(
                "candidate catalog entries cannot be locked before human review"
            )
        return self


class Stage9GoldenCandidateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    catalog_id: str
    version: str
    candidates: tuple[Stage9GoldenCandidate, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        ids = [item.candidate_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique")
        if {item.domain for item in self.candidates} != set(Stage9EvaluationDomain):
            raise ValueError("catalog must cover all Stage 9 domains")
        return self


def build_stage9_golden_candidate_catalog() -> Stage9GoldenCandidateCatalog:
    nist = "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence"
    rag = "https://arxiv.org/abs/2005.11401"
    evidentiality = "https://arxiv.org/abs/2112.08688"
    survey = "https://arxiv.org/abs/2312.10997"
    epo = "https://register.epo.org/help?lng=en&topic=eppubnumber"
    roadmap = "local:/home/moon/Project/agentic-ai-lab/ROADMAP.md"
    decisions = "local:/home/moon/Project/agentic-ai-lab/DECISIONS.md"
    rows = (
        (
            "tech-01",
            Stage9EvaluationDomain.GENERAL_TECHNICAL,
            "Which NIST AI RMF functions and GAI risk actions are relevant to a bounded research agent?",
            ("NIST-AI-600-1",),
            (nist,),
        ),
        (
            "tech-02",
            Stage9EvaluationDomain.GENERAL_TECHNICAL,
            "How should a research agent distinguish measured usage, estimated cost, and billed cost?",
            ("AIRA-DECISIONS",),
            (decisions,),
        ),
        (
            "academic-01",
            Stage9EvaluationDomain.ACADEMIC,
            "What parametric and non-parametric components define the original RAG formulation?",
            ("arXiv:2005.11401",),
            (rag,),
        ),
        (
            "academic-02",
            Stage9EvaluationDomain.ACADEMIC,
            "How does evidentiality-guided generation address irrelevant retrieved passages?",
            ("arXiv:2112.08688",),
            (evidentiality,),
        ),
        (
            "patent-01",
            Stage9EvaluationDomain.PATENT,
            "What exact technical features are present in claim 1 of EP1000000B1?",
            ("EP1000000B1",),
            (epo,),
        ),
        (
            "patent-02",
            Stage9EvaluationDomain.PATENT,
            "Which technical disclosures are shared or differ between EP1000000A1 and EP1000000B1?",
            ("EP1000000A1", "EP1000000B1"),
            (epo, epo),
        ),
        (
            "patent-03",
            Stage9EvaluationDomain.PATENT,
            "Can exact abstract evidence support a technical comparison without ranking or legal conclusions?",
            ("EP1000000A1", "EP1000000B1"),
            (epo, epo),
        ),
        (
            "cross-01",
            Stage9EvaluationDomain.CROSS_SOURCE,
            "How do the original RAG paper and AIRA roadmap differ between a research concept and an implemented bounded workflow?",
            ("arXiv:2005.11401", "AIRA-ROADMAP"),
            (rag, roadmap),
        ),
        (
            "cross-02",
            Stage9EvaluationDomain.CROSS_SOURCE,
            "Which RAG evaluation challenges in the survey are addressed by AIRA and which remain unvalidated?",
            ("arXiv:2312.10997", "AIRA-ROADMAP"),
            (survey, roadmap),
        ),
        (
            "cross-03",
            Stage9EvaluationDomain.CROSS_SOURCE,
            "How should NIST GAI risk guidance constrain AIRA evidence, citation, cost, and human-review boundaries?",
            ("NIST-AI-600-1", "AIRA-DECISIONS"),
            (nist, decisions),
        ),
    )
    return Stage9GoldenCandidateCatalog(
        catalog_id="aira-stage9-golden-candidates-v1",
        version="1.0.0",
        candidates=tuple(
            Stage9GoldenCandidate(
                candidate_id=cid,
                domain=domain,
                research_question=question,
                source_ids=ids,
                source_urls=urls,
                prohibited_claims=(
                    "Do not state unsupported factual, ranking, chronology, or legal conclusions.",
                ),
                expected_uncertainties=(
                    "Disclose evidence, access, recency, and evaluation limitations.",
                ),
                verification_status=CandidateVerificationStatus.SOURCE_IDENTITY_VERIFIED,
            )
            for cid, domain, question, ids, urls in rows
        ),
    )
