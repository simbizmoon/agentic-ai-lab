"""Compare single-agent and multi-agent research executions."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchStatus,
    MultiAgentResearchWorkflowResult,
)
from app.research.research_execution_comparison_error import (
    ResearchExecutionComparisonError,
)
from app.research.single_agent_research_execution import (
    SingleAgentResearchExecution,
)
from app.schemas.research_agent_result import (
    ResearchAgentResultStatus,
)


class ResearchExecutionMode(StrEnum):
    """Supported research execution architecture."""

    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"


class ResearchExecutionPreference(StrEnum):
    """Overall comparison preference."""

    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"
    CONTEXT_DEPENDENT = "context_dependent"


class ResearchExecutionMetrics(BaseModel):
    """Normalized metrics for one research execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    mode: ResearchExecutionMode
    completed: bool
    output_available: bool
    execution_step_count: int = Field(ge=1)
    participating_agent_count: int = Field(ge=1)
    tool_call_count: int = Field(ge=0)
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    revision_round_count: int = Field(ge=0)
    traceability_score: float = Field(ge=0, le=1)
    complexity_score: float = Field(ge=0, le=1)

    @property
    def total_token_count(self) -> int:
        """Return total token usage."""

        return (
            self.input_token_count
            + self.output_token_count
        )


class ResearchExecutionComparison(BaseModel):
    """Structured comparison of two research executions."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    single_agent: ResearchExecutionMetrics
    multi_agent: ResearchExecutionMetrics
    preferred_mode: ResearchExecutionPreference
    rationale: str
    observations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        """Validate comparison text and observations."""

        for field_name, value in {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "rationale": self.rationale,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if any(
            not observation.strip()
            for observation in self.observations
        ):
            raise ValueError(
                "observations must not contain blank values"
            )

        normalized = [
            observation.strip().casefold()
            for observation in self.observations
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "observations must not contain duplicates"
            )

        return self


class ResearchExecutionComparator:
    """Evaluate single-agent and multi-agent executions."""

    def compare(
        self,
        *,
        single_agent: SingleAgentResearchExecution,
        multi_agent: MultiAgentResearchWorkflowResult,
    ) -> ResearchExecutionComparison:
        """Return one deterministic architectural comparison."""

        self._validate_shared_context(
            single_agent=single_agent,
            multi_agent=multi_agent,
        )

        single_metrics = self._single_metrics(
            single_agent
        )
        multi_metrics = self._multi_metrics(
            multi_agent
        )
        preferred_mode = self._preferred_mode(
            single_metrics=single_metrics,
            multi_metrics=multi_metrics,
        )

        observations = self._observations(
            single_metrics=single_metrics,
            multi_metrics=multi_metrics,
        )

        return ResearchExecutionComparison(
            request_id=single_agent.request_id,
            workspace_id=single_agent.workspace_id,
            single_agent=single_metrics,
            multi_agent=multi_metrics,
            preferred_mode=preferred_mode,
            rationale=self._rationale(
                preferred_mode=preferred_mode,
                single_metrics=single_metrics,
                multi_metrics=multi_metrics,
            ),
            observations=observations,
        )

    @staticmethod
    def _validate_shared_context(
        *,
        single_agent: SingleAgentResearchExecution,
        multi_agent: MultiAgentResearchWorkflowResult,
    ) -> None:
        """Require the executions to describe one request."""

        if (
            single_agent.request_id
            != multi_agent.request_id
        ):
            raise ResearchExecutionComparisonError(
                "executions must share request_id"
            )

        if (
            single_agent.workspace_id
            != multi_agent.workspace_id
        ):
            raise ResearchExecutionComparisonError(
                "executions must share workspace_id"
            )

    @staticmethod
    def _single_metrics(
        execution: SingleAgentResearchExecution,
    ) -> ResearchExecutionMetrics:
        """Normalize single-agent execution metrics."""

        result = execution.result
        output_available = (
            result.primary_output() is not None
        )
        completed = (
            result.status
            is ResearchAgentResultStatus.SUCCEEDED
        )

        traceability_score = (
            ResearchExecutionComparator
            ._traceability_score(
                source_count=(
                    execution.traceable_source_count
                ),
                evidence_count=(
                    execution.traceable_evidence_count
                ),
                claim_count=(
                    execution.traceable_claim_count
                ),
                output_available=output_available,
            )
        )

        return ResearchExecutionMetrics(
            mode=ResearchExecutionMode.SINGLE_AGENT,
            completed=completed,
            output_available=output_available,
            execution_step_count=(
                execution.execution_step_count
            ),
            participating_agent_count=1,
            tool_call_count=(
                result.metrics.tool_call_count
            ),
            input_token_count=(
                result.metrics.input_token_count
            ),
            output_token_count=(
                result.metrics.output_token_count
            ),
            source_count=max(
                result.metrics.source_count,
                execution.traceable_source_count,
            ),
            evidence_count=max(
                result.metrics.evidence_count,
                execution.traceable_evidence_count,
            ),
            claim_count=max(
                result.metrics.claim_count,
                execution.traceable_claim_count,
            ),
            revision_round_count=(
                execution.revision_round_count
            ),
            traceability_score=traceability_score,
            complexity_score=(
                ResearchExecutionComparator
                ._complexity_score(
                    execution_step_count=(
                        execution.execution_step_count
                    ),
                    participating_agent_count=1,
                    revision_round_count=(
                        execution.revision_round_count
                    ),
                )
            ),
        )

    @staticmethod
    def _multi_metrics(
        execution: MultiAgentResearchWorkflowResult,
    ) -> ResearchExecutionMetrics:
        """Normalize multi-agent execution metrics."""

        results = [
            stage.result
            for stage in execution.stages
        ]

        if execution.review_revision_result is not None:
            for loop_round in (
                execution.review_revision_result.rounds
            ):
                results.append(
                    loop_round.synthesis_result
                )

                if loop_round.review_result is not None:
                    results.append(
                        loop_round.review_result
                    )

        agent_ids = {
            result.agent.agent_id
            for result in results
        }

        tool_call_count = sum(
            result.metrics.tool_call_count
            for result in results
        )
        input_token_count = sum(
            result.metrics.input_token_count
            for result in results
        )
        output_token_count = sum(
            result.metrics.output_token_count
            for result in results
        )
        source_count = max(
            (
                result.metrics.source_count
                for result in results
            ),
            default=0,
        )
        evidence_count = max(
            (
                result.metrics.evidence_count
                for result in results
            ),
            default=0,
        )
        claim_count = max(
            (
                result.metrics.claim_count
                for result in results
            ),
            default=0,
        )
        revision_round_count = (
            execution.review_revision_result
            .revision_rounds_used
            if execution.review_revision_result
            is not None
            else 0
        )
        execution_step_count = max(
            len(results),
            1,
        )
        output_available = (
            execution.final_result.primary_output()
            is not None
        )
        completed = (
            execution.status
            is MultiAgentResearchStatus.COMPLETED
        )

        return ResearchExecutionMetrics(
            mode=ResearchExecutionMode.MULTI_AGENT,
            completed=completed,
            output_available=output_available,
            execution_step_count=execution_step_count,
            participating_agent_count=max(
                len(agent_ids),
                1,
            ),
            tool_call_count=tool_call_count,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            source_count=source_count,
            evidence_count=evidence_count,
            claim_count=claim_count,
            revision_round_count=revision_round_count,
            traceability_score=(
                ResearchExecutionComparator
                ._traceability_score(
                    source_count=source_count,
                    evidence_count=evidence_count,
                    claim_count=claim_count,
                    output_available=output_available,
                )
            ),
            complexity_score=(
                ResearchExecutionComparator
                ._complexity_score(
                    execution_step_count=(
                        execution_step_count
                    ),
                    participating_agent_count=max(
                        len(agent_ids),
                        1,
                    ),
                    revision_round_count=(
                        revision_round_count
                    ),
                )
            ),
        )

    @staticmethod
    def _traceability_score(
        *,
        source_count: int,
        evidence_count: int,
        claim_count: int,
        output_available: bool,
    ) -> float:
        """Calculate a simple normalized traceability score."""

        score = 0.0

        if output_available:
            score += 0.25

        if source_count > 0:
            score += 0.25

        if evidence_count > 0:
            score += 0.25

        if claim_count > 0:
            score += 0.25

        return score

    @staticmethod
    def _complexity_score(
        *,
        execution_step_count: int,
        participating_agent_count: int,
        revision_round_count: int,
    ) -> float:
        """Calculate normalized orchestration complexity."""

        raw_score = (
            execution_step_count
            + participating_agent_count
            + revision_round_count
        )

        return min(raw_score / 12, 1.0)

    @staticmethod
    def _preferred_mode(
        *,
        single_metrics: ResearchExecutionMetrics,
        multi_metrics: ResearchExecutionMetrics,
    ) -> ResearchExecutionPreference:
        """Select a deterministic overall preference."""

        if (
            multi_metrics.completed
            and not single_metrics.completed
        ):
            return (
                ResearchExecutionPreference.MULTI_AGENT
            )

        if (
            single_metrics.completed
            and not multi_metrics.completed
        ):
            return (
                ResearchExecutionPreference.SINGLE_AGENT
            )

        traceability_difference = (
            multi_metrics.traceability_score
            - single_metrics.traceability_score
        )
        complexity_difference = (
            multi_metrics.complexity_score
            - single_metrics.complexity_score
        )

        if (
            traceability_difference >= 0.25
            and complexity_difference <= 0.85
        ):
            return (
                ResearchExecutionPreference.MULTI_AGENT
            )

        if (
            traceability_difference <= 0
            and single_metrics.total_token_count
            <= multi_metrics.total_token_count
        ):
            return (
                ResearchExecutionPreference.SINGLE_AGENT
            )

        return (
            ResearchExecutionPreference.CONTEXT_DEPENDENT
        )

    @staticmethod
    def _observations(
        *,
        single_metrics: ResearchExecutionMetrics,
        multi_metrics: ResearchExecutionMetrics,
    ) -> list[str]:
        """Build deterministic comparison observations."""

        observations = [
            (
                "The single-agent execution used "
                f"{single_metrics.execution_step_count} steps "
                "and the multi-agent execution used "
                f"{multi_metrics.execution_step_count} steps."
            ),
            (
                "The single-agent traceability score was "
                f"{single_metrics.traceability_score:.2f}, "
                "while the multi-agent score was "
                f"{multi_metrics.traceability_score:.2f}."
            ),
            (
                "The single-agent execution used "
                f"{single_metrics.total_token_count} tokens, "
                "while the multi-agent execution used "
                f"{multi_metrics.total_token_count} tokens."
            ),
        ]

        if (
            multi_metrics.participating_agent_count
            > single_metrics.participating_agent_count
        ):
            observations.append(
                "The multi-agent workflow separated work "
                "across multiple specialist identities."
            )

        if multi_metrics.revision_round_count > 0:
            observations.append(
                "The multi-agent workflow included an "
                "explicit review and revision cycle."
            )

        return observations

    @staticmethod
    def _rationale(
        *,
        preferred_mode: ResearchExecutionPreference,
        single_metrics: ResearchExecutionMetrics,
        multi_metrics: ResearchExecutionMetrics,
    ) -> str:
        """Return a deterministic preference rationale."""

        if (
            preferred_mode
            is ResearchExecutionPreference.MULTI_AGENT
        ):
            return (
                "The multi-agent execution provides stronger "
                "completion or traceability despite its higher "
                "coordination complexity."
            )

        if (
            preferred_mode
            is ResearchExecutionPreference.SINGLE_AGENT
        ):
            return (
                "The single-agent execution achieves comparable "
                "traceability with lower execution complexity "
                "or token usage."
            )

        return (
            "The preferred architecture depends on whether "
            "traceability and independent review are more "
            "important than execution cost and simplicity. "
            f"Single-agent complexity is "
            f"{single_metrics.complexity_score:.2f}; "
            f"multi-agent complexity is "
            f"{multi_metrics.complexity_score:.2f}."
        )
