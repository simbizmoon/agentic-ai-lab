"""Schemas for the single research-agent pipeline."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.research.research_citation_verifier_executor import (
    ResearchCitationVerification,
)
from app.schemas.research_quality import (
    ResearchQualityEvaluation,
)
from app.schemas.research_synthesis import (
    ResearchSynthesisReport,
)
from app.schemas.research_workspace import (
    ResearchWorkspace,
)


class SingleResearchPipelineResult(BaseModel):
    """Final result of one single-agent research run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    workspace: ResearchWorkspace
    report: ResearchSynthesisReport
    quality: ResearchQualityEvaluation
    citation_verifications: list[
        ResearchCitationVerification
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate identity across all pipeline outputs."""

        if (
            self.report.workspace_id
            != self.workspace.workspace_id
        ):
            raise ValueError(
                "report workspace_id must match workspace"
            )

        if (
            self.report.request_id
            != self.workspace.request.request_id
        ):
            raise ValueError(
                "report request_id must match workspace"
            )

        if self.quality.report != self.report:
            raise ValueError(
                "quality report must match pipeline report"
            )

        return self
