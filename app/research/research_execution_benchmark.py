"""Normalized benchmark records for single- vs multi-agent research."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.evals.multi_agent_workflow_evaluator import (
    MultiAgentWorkflowEvaluation,
)
from app.research.multi_agent_research_orchestrator import (
    MultiAgentResearchStatus,
    MultiAgentResearchWorkflowResult,
)
from app.schemas.research_pipeline import SingleResearchPipelineResult


class ResearchArchitectureRunMetrics(BaseModel):
    """Comparable metrics for one research architecture run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    mode: str
    runtime_succeeded: bool
    quality_approved: bool
    terminal_status: str
    wall_elapsed_seconds: float = Field(ge=0.0)
    output_available: bool
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    participating_agent_count: int = Field(ge=1)
    execution_step_count: int = Field(ge=1)
    revision_round_count: int = Field(ge=0)
    tool_call_count: int | None = Field(default=None, ge=0)
    recorded_token_count: int | None = Field(default=None, ge=0)
    semantic_repair_count: int = Field(default=0, ge=0)
    workflow_integrity_passed: bool | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ResearchArchitectureComparison(BaseModel):
    """One normalized Phase-9 architecture comparison."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    single_agent: ResearchArchitectureRunMetrics
    multi_agent: ResearchArchitectureRunMetrics
    comparable_upstream_artifacts: bool
    evaluator_conditions_equal: bool
    decision_ready: bool
    limitations: list[str] = Field(default_factory=list)


class ResearchExecutionBenchmarkNormalizer:
    """Normalize real Single and Multi runtime results without overclaiming."""

    @staticmethod
    def single(
        *,
        result: SingleResearchPipelineResult,
        wall_elapsed_seconds: float,
    ) -> ResearchArchitectureRunMetrics:
        """Normalize one single-agent pipeline result."""

        workspace = result.workspace
        progress = workspace.progress()
        run_metrics = result.run_metrics

        tool_call_count = None
        recorded_token_count = None
        if run_metrics is not None:
            tool_call_count = (
                run_metrics.search_provider_calls
                + run_metrics.llm_call_count
            )
            recorded_token_count = run_metrics.recorded_tokens

        return ResearchArchitectureRunMetrics(
            mode="single_agent",
            runtime_succeeded=True,
            quality_approved=result.quality.passed,
            terminal_status=(
                "quality_passed"
                if result.quality.passed
                else "quality_failed"
            ),
            wall_elapsed_seconds=wall_elapsed_seconds,
            output_available=True,
            source_count=progress.document_count,
            evidence_count=progress.evidence_count,
            claim_count=progress.claim_count,
            citation_count=result.report.citation_count,
            participating_agent_count=1,
            execution_step_count=1,
            revision_round_count=0,
            tool_call_count=tool_call_count,
            recorded_token_count=recorded_token_count,
            semantic_repair_count=0,
            workflow_integrity_passed=None,
            metadata={
                "quality_evaluator": "deterministic-single-pipeline",
                "run_metrics_available": str(
                    run_metrics is not None
                ).casefold(),
            },
        )

    @staticmethod
    def multi(
        *,
        result: MultiAgentResearchWorkflowResult,
        wall_elapsed_seconds: float,
        workflow_evaluation: MultiAgentWorkflowEvaluation,
    ) -> ResearchArchitectureRunMetrics:
        """Normalize one multi-agent workflow result."""

        all_results = [
            stage.result
            for stage in result.stages
        ]

        if result.review_revision_result is not None:
            for loop_round in result.review_revision_result.rounds:
                all_results.append(loop_round.synthesis_result)
                if loop_round.review_result is not None:
                    all_results.append(loop_round.review_result)

        agent_ids = {
            item.agent.agent_id
            for item in all_results
        }

        tool_call_count = sum(
            item.metrics.tool_call_count
            for item in all_results
        )
        recorded_token_count = sum(
            item.metrics.input_token_count
            + item.metrics.output_token_count
            for item in all_results
        )

        source_count = max(
            (item.metrics.source_count for item in all_results),
            default=0,
        )
        evidence_count = max(
            (item.metrics.evidence_count for item in all_results),
            default=0,
        )
        claim_count = max(
            (item.metrics.claim_count for item in all_results),
            default=0,
        )

        citation_count = 0
        synthesis_result = (
            result.review_revision_result.final_synthesis_result
            if result.review_revision_result is not None
            else None
        )
        if synthesis_result is not None:
            report_payload = synthesis_result.payload.get("report")
            if isinstance(report_payload, dict):
                sections = report_payload.get("sections", [])
                if isinstance(sections, list):
                    citation_count = sum(
                        str(section.get("content", "")).count(
                            "Citation:"
                        )
                        for section in sections
                        if isinstance(section, dict)
                    )

        semantic_repair_count = 0
        for item in all_results:
            payload = item.payload
            review = payload.get("review")
            if not isinstance(review, dict):
                continue
            metadata = review.get("metadata")
            if (
                isinstance(metadata, dict)
                and metadata.get("semantic_repair") == "true"
            ):
                semantic_repair_count += 1

        revision_round_count = (
            result.review_revision_result.revision_rounds_used
            if result.review_revision_result is not None
            else 0
        )

        quality_approved = (
            result.status is MultiAgentResearchStatus.COMPLETED
        )
        runtime_succeeded = result.status in {
            MultiAgentResearchStatus.COMPLETED,
            MultiAgentResearchStatus.REPORT_REJECTED,
            MultiAgentResearchStatus.REVISION_LIMIT_REACHED,
        }

        return ResearchArchitectureRunMetrics(
            mode="multi_agent",
            runtime_succeeded=runtime_succeeded,
            quality_approved=quality_approved,
            terminal_status=result.status.value,
            wall_elapsed_seconds=wall_elapsed_seconds,
            output_available=(
                result.final_result.primary_output() is not None
            ),
            source_count=source_count,
            evidence_count=evidence_count,
            claim_count=claim_count,
            citation_count=citation_count,
            participating_agent_count=max(len(agent_ids), 1),
            execution_step_count=max(len(all_results), 1),
            revision_round_count=revision_round_count,
            tool_call_count=tool_call_count,
            recorded_token_count=recorded_token_count,
            semantic_repair_count=semantic_repair_count,
            workflow_integrity_passed=workflow_evaluation.passed,
            metadata={
                "quality_evaluator": "bounded-local-quality-reviewer",
                "workflow_status": result.status.value,
            },
        )

    def compare(
        self,
        *,
        single_result: SingleResearchPipelineResult,
        single_wall_elapsed_seconds: float,
        multi_result: MultiAgentResearchWorkflowResult,
        multi_wall_elapsed_seconds: float,
        workflow_evaluation: MultiAgentWorkflowEvaluation,
        comparable_upstream_artifacts: bool,
        evaluator_conditions_equal: bool,
    ) -> ResearchArchitectureComparison:
        """Build one explicit, limitation-aware architecture comparison."""

        request_id = single_result.workspace.request.request_id
        workspace_id = single_result.workspace.workspace_id

        if multi_result.request_id != request_id:
            raise ValueError(
                "single and multi executions must share request_id"
            )
        if multi_result.workspace_id != workspace_id:
            raise ValueError(
                "single and multi executions must share workspace_id"
            )

        limitations: list[str] = []
        if not comparable_upstream_artifacts:
            limitations.append(
                "Upstream research artifacts were not held equivalent."
            )
        if not evaluator_conditions_equal:
            limitations.append(
                "Final quality evaluator conditions differ between "
                "single- and multi-agent executions."
            )

        decision_ready = (
            comparable_upstream_artifacts
            and evaluator_conditions_equal
        )

        return ResearchArchitectureComparison(
            request_id=request_id,
            workspace_id=workspace_id,
            single_agent=self.single(
                result=single_result,
                wall_elapsed_seconds=single_wall_elapsed_seconds,
            ),
            multi_agent=self.multi(
                result=multi_result,
                wall_elapsed_seconds=multi_wall_elapsed_seconds,
                workflow_evaluation=workflow_evaluation,
            ),
            comparable_upstream_artifacts=comparable_upstream_artifacts,
            evaluator_conditions_equal=evaluator_conditions_equal,
            decision_ready=decision_ready,
            limitations=limitations,
        )


def research_workspace_artifacts_equivalent(
    left: object,
    right: object,
) -> bool:
    """Compare source-through-claim artifacts while ignoring generated IDs."""

    def signature(workspace: object) -> tuple[object, ...]:
        candidate_set = workspace.candidate_set
        document_set = workspace.document_set
        evidence_set = workspace.evidence_set
        claim_set = workspace.claim_set

        candidates = tuple(
            sorted(
                (
                    candidate.url.strip(),
                    candidate.title.strip(),
                    candidate.source_type.value,
                )
                for candidate in (
                    candidate_set.candidates
                    if candidate_set is not None
                    else []
                )
            )
        )
        documents = tuple(
            sorted(
                (
                    document.candidate.url.strip(),
                    document.content.strip(),
                )
                for document in (
                    document_set.documents
                    if document_set is not None
                    else []
                )
            )
        )
        evidence = tuple(
            sorted(
                (
                    item.excerpt.strip(),
                    item.stance.value,
                    item.evidence_type.value,
                )
                for item in (
                    evidence_set.evidence
                    if evidence_set is not None
                    else []
                )
            )
        )
        claims = tuple(
            sorted(
                claim.text.strip()
                for claim in (
                    claim_set.claims
                    if claim_set is not None
                    else []
                )
            )
        )
        return (
            candidates,
            documents,
            evidence,
            claims,
        )

    return signature(left) == signature(right)
