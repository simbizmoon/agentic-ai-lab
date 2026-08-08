from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchStageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    call_count: int = Field(default=0, ge=0)
    recorded_tokens: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0.0, ge=0.0)

class ResearchRunMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    total_elapsed_seconds: float = Field(ge=0.0)
    search_provider_calls: int = Field(default=0, ge=0)
    search_credits_used: float = Field(default=0.0, ge=0.0)
    search_elapsed_seconds: float = Field(default=0.0, ge=0.0)
    round_1_source_read_elapsed_seconds: float = Field(default=0.0, ge=0.0)
    round_1_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)
    round_1_evidence_semantic: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    round_1_claim_generation: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    round_1_citation_verification: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    round_1_claim_relevance: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    round_1_answer_coverage: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    coverage_source_read_elapsed_seconds: float = Field(default=0.0, ge=0.0)
    coverage_evidence_extraction_elapsed_seconds: float = Field(default=0.0, ge=0.0)
    coverage_evidence_semantic: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    coverage_claim_generation: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    coverage_citation_verification: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    coverage_claim_relevance: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)
    coverage_answer_coverage: ResearchStageMetrics = Field(default_factory=ResearchStageMetrics)

    @property
    def llm_call_count(self) -> int:
        stages = (
            self.round_1_evidence_semantic,
            self.round_1_claim_generation, self.round_1_citation_verification,
            self.round_1_claim_relevance, self.round_1_answer_coverage,
            self.coverage_evidence_semantic,
            self.coverage_claim_generation, self.coverage_citation_verification,
            self.coverage_claim_relevance, self.coverage_answer_coverage,
        )
        return sum(x.call_count for x in stages)

    @property
    def recorded_tokens(self) -> int:
        stages = (
            self.round_1_evidence_semantic,
            self.round_1_claim_generation, self.round_1_citation_verification,
            self.round_1_claim_relevance, self.round_1_answer_coverage,
            self.coverage_evidence_semantic,
            self.coverage_claim_generation, self.coverage_citation_verification,
            self.coverage_claim_relevance, self.coverage_answer_coverage,
        )
        return sum(x.recorded_tokens for x in stages)
