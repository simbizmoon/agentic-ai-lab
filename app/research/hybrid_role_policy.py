"""Typed provider routing policy for heterogeneous research execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ResearchExecutionProvider(StrEnum):
    """Execution backend assigned to one research role."""

    DETERMINISTIC = "deterministic"
    OPENAI = "openai"
    LOCAL = "local"


class HybridResearchRole(StrEnum):
    """Research roles that may have distinct execution providers."""

    TASK_DECOMPOSITION = "task_decomposition"
    QUERY_PLANNING = "query_planning"
    SOURCE_QUALITY = "source_quality"
    DOCUMENT_SELECTION = "document_selection"
    EVIDENCE_RELEVANCE = "evidence_relevance"
    CLAIM_GENERATION = "claim_generation"
    SEMANTIC_CITATION = "semantic_citation"
    CLAIM_RELEVANCE = "claim_relevance"
    ANSWER_COVERAGE = "answer_coverage"
    SYNTHESIS = "synthesis"
    FINAL_QUALITY_REVIEW = "final_quality_review"


class HybridResearchRolePolicy(BaseModel):
    """Explicit provider assignment for heterogeneous research roles."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    task_decomposition: ResearchExecutionProvider
    query_planning: ResearchExecutionProvider
    source_quality: ResearchExecutionProvider
    document_selection: ResearchExecutionProvider
    evidence_relevance: ResearchExecutionProvider
    claim_generation: ResearchExecutionProvider
    semantic_citation: ResearchExecutionProvider
    claim_relevance: ResearchExecutionProvider
    answer_coverage: ResearchExecutionProvider
    synthesis: ResearchExecutionProvider
    final_quality_review: ResearchExecutionProvider

    @classmethod
    def phase10_default(cls) -> HybridResearchRolePolicy:
        """Return the evidence-backed initial Phase-10 hybrid policy."""

        return cls(
            task_decomposition=ResearchExecutionProvider.DETERMINISTIC,
            query_planning=ResearchExecutionProvider.DETERMINISTIC,
            source_quality=ResearchExecutionProvider.DETERMINISTIC,
            document_selection=ResearchExecutionProvider.DETERMINISTIC,
            evidence_relevance=ResearchExecutionProvider.OPENAI,
            claim_generation=ResearchExecutionProvider.OPENAI,
            semantic_citation=ResearchExecutionProvider.LOCAL,
            claim_relevance=ResearchExecutionProvider.LOCAL,
            answer_coverage=ResearchExecutionProvider.LOCAL,
            synthesis=ResearchExecutionProvider.DETERMINISTIC,
            final_quality_review=ResearchExecutionProvider.OPENAI,
        )

    @model_validator(mode="after")
    def validate_safety_boundaries(self) -> HybridResearchRolePolicy:
        """Prevent unsupported local authority in the initial hybrid policy."""

        if (
            self.final_quality_review
            is ResearchExecutionProvider.LOCAL
        ):
            raise ValueError(
                "final_quality_review must not use local provider "
                "without an explicit authoritative-local validation phase"
            )

        return self

    def provider_for(
        self,
        role: HybridResearchRole,
    ) -> ResearchExecutionProvider:
        """Return the configured provider for one role."""

        return ResearchExecutionProvider(
            getattr(self, role.value)
        )

    def as_role_map(
        self,
    ) -> dict[HybridResearchRole, ResearchExecutionProvider]:
        """Return every role assignment as an explicit mapping."""

        return {
            role: self.provider_for(role)
            for role in HybridResearchRole
        }

    def roles_for(
        self,
        provider: ResearchExecutionProvider,
    ) -> tuple[HybridResearchRole, ...]:
        """Return all roles assigned to one provider."""

        return tuple(
            role
            for role in HybridResearchRole
            if self.provider_for(role) is provider
        )
