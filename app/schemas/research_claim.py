"""Schemas for research claims and traceable citations."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceSet,
    ResearchEvidenceStance,
)


class ResearchClaimType(StrEnum):
    """Semantic type of one research claim."""

    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    INTERPRETIVE = "interpretive"
    RECOMMENDATION = "recommendation"
    LIMITATION = "limitation"
    UNCERTAINTY = "uncertainty"
    OTHER = "other"


class ResearchClaimStatus(StrEnum):
    """Review state of one research claim."""

    DRAFT = "draft"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REJECTED = "rejected"


class ResearchCitation(BaseModel):
    """One citation linking a claim to an evidence item."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    citation_id: str
    evidence_id: str
    source_id: str
    document_id: str
    excerpt: str
    start_character: int = Field(ge=0)
    end_character: int = Field(ge=1)
    label: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        """Validate citation identity and range."""

        required_text = {
            "citation_id": self.citation_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "excerpt": self.excerpt,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if self.end_character <= self.start_character:
            raise ValueError(
                "end_character must be greater than "
                "start_character"
            )

        if (
            self.label is not None
            and not self.label.strip()
        ):
            raise ValueError(
                "label must not be blank when provided"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self


class ResearchClaim(BaseModel):
    """One research claim supported by traceable citations."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    claim_id: str
    request_id: str
    task_id: str
    text: str
    claim_type: ResearchClaimType
    status: ResearchClaimStatus = (
        ResearchClaimStatus.DRAFT
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    citations: list[ResearchCitation] = Field(
        min_length=1
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list
    )
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list
    )
    rationale: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate claim identity and citation relationships."""

        required_text = {
            "claim_id": self.claim_id,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "text": self.text,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if (
            self.rationale is not None
            and not self.rationale.strip()
        ):
            raise ValueError(
                "rationale must not be blank when provided"
            )

        citation_ids = [
            citation.citation_id.strip().casefold()
            for citation in self.citations
        ]

        if len(set(citation_ids)) != len(citation_ids):
            raise ValueError(
                "citation IDs must be unique within a claim"
            )

        citation_evidence_ids = [
            citation.evidence_id.strip().casefold()
            for citation in self.citations
        ]

        if len(set(citation_evidence_ids)) != len(
            citation_evidence_ids
        ):
            raise ValueError(
                "citation evidence IDs must be unique "
                "within a claim"
            )

        supporting = self._normalized_ids(
            self.supporting_evidence_ids,
            field_name="supporting_evidence_ids",
        )
        contradicting = self._normalized_ids(
            self.contradicting_evidence_ids,
            field_name="contradicting_evidence_ids",
        )

        if supporting & contradicting:
            raise ValueError(
                "supporting and contradicting evidence "
                "must not overlap"
            )

        cited = set(citation_evidence_ids)

        if not supporting.issubset(cited):
            raise ValueError(
                "supporting evidence IDs must reference "
                "claim citations"
            )

        if not contradicting.issubset(cited):
            raise ValueError(
                "contradicting evidence IDs must reference "
                "claim citations"
            )

        if (
            self.status is ResearchClaimStatus.SUPPORTED
            and not supporting
        ):
            raise ValueError(
                "supported claim must contain "
                "supporting evidence"
            )

        if (
            self.status is ResearchClaimStatus.CONTESTED
            and not contradicting
        ):
            raise ValueError(
                "contested claim must contain "
                "contradicting evidence"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self

    @staticmethod
    def _normalized_ids(
        values: list[str],
        *,
        field_name: str,
    ) -> set[str]:
        """Validate and normalize an evidence ID list."""

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = {
            value.strip().casefold()
            for value in values
        }

        if len(normalized) != len(values):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

        return normalized

    def ordered_citations(
        self,
    ) -> list[ResearchCitation]:
        """Return citations in their stable insertion order."""

        return list(self.citations)


class ResearchClaimSet(BaseModel):
    """Validated claims linked to an evidence set."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    evidence_set: ResearchEvidenceSet
    claims: list[ResearchClaim] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_claim_set(self) -> Self:
        """Validate claims and citations against evidence."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        if self.evidence_set.request_id != self.request_id:
            raise ValueError(
                "evidence set request_id must match "
                "claim set request_id"
            )

        claim_ids = [
            claim.claim_id.strip().casefold()
            for claim in self.claims
        ]

        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError(
                "claim IDs must be unique"
            )

        evidence_by_id = {
            item.evidence_id.strip().casefold(): item
            for item in self.evidence_set.evidence
        }

        for claim in self.claims:
            if claim.request_id != self.request_id:
                raise ValueError(
                    "all claim request IDs must match "
                    "the claim set request_id"
                )

            self._validate_claim_citations(
                claim=claim,
                evidence_by_id=evidence_by_id,
            )

        return self

    @staticmethod
    def _validate_claim_citations(
        *,
        claim: ResearchClaim,
        evidence_by_id: dict[str, ResearchEvidence],
    ) -> None:
        """Validate one claim's citations against evidence."""

        for citation in claim.citations:
            evidence = evidence_by_id.get(
                citation.evidence_id.strip().casefold()
            )

            if evidence is None:
                raise ValueError(
                    "all citations must reference "
                    "existing evidence"
                )

            if evidence.task_id != claim.task_id:
                raise ValueError(
                    "citation evidence task_id must match "
                    "the claim task_id"
                )

            if citation.source_id != evidence.source_id:
                raise ValueError(
                    "citation source_id must match "
                    "the evidence source_id"
                )

            if citation.document_id != evidence.document_id:
                raise ValueError(
                    "citation document_id must match "
                    "the evidence document_id"
                )

            if citation.excerpt != evidence.excerpt:
                raise ValueError(
                    "citation excerpt must match "
                    "the evidence excerpt"
                )

            if (
                citation.start_character
                != evidence.start_character
                or citation.end_character
                != evidence.end_character
            ):
                raise ValueError(
                    "citation character range must match "
                    "the evidence range"
                )

        supporting_ids = {
            value.strip().casefold()
            for value in claim.supporting_evidence_ids
        }
        contradicting_ids = {
            value.strip().casefold()
            for value in claim.contradicting_evidence_ids
        }

        for evidence_id in supporting_ids:
            evidence = evidence_by_id[evidence_id]

            if (
                evidence.stance
                is ResearchEvidenceStance.CONTRADICTS
            ):
                raise ValueError(
                    "supporting evidence must not have "
                    "a contradicting stance"
                )

        for evidence_id in contradicting_ids:
            evidence = evidence_by_id[evidence_id]

            if (
                evidence.stance
                is not ResearchEvidenceStance.CONTRADICTS
            ):
                raise ValueError(
                    "contradicting evidence must have "
                    "a contradicting stance"
                )

    def claims_for_task(
        self,
        task_id: str,
    ) -> list[ResearchClaim]:
        """Return claims belonging to one task."""

        if not task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        normalized_task_id = task_id.strip().casefold()

        return [
            claim
            for claim in self.claims
            if claim.task_id.strip().casefold()
            == normalized_task_id
        ]

    def supported_claims(
        self,
    ) -> list[ResearchClaim]:
        """Return claims classified as supported."""

        return [
            claim
            for claim in self.claims
            if claim.status
            is ResearchClaimStatus.SUPPORTED
        ]

    def contested_claims(
        self,
    ) -> list[ResearchClaim]:
        """Return claims classified as contested."""

        return [
            claim
            for claim in self.claims
            if claim.status
            is ResearchClaimStatus.CONTESTED
        ]
