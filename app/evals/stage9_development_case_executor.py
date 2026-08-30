"""Execute one locked Stage 9 development case through the Stage 7 loop."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.evals.stage9_bounded_development_baseline_runner import (
    Stage9DevelopmentCaseExecutionError,
)
from app.evals.stage9_development_case_artifact_writer import (
    Stage9DevelopmentCaseArtifactError,
    Stage9DevelopmentCaseArtifactWriter,
)
from app.research.bounded_research_planning_loop import (
    BoundedResearchPlanningLoopError,
)
from app.research.stage9_acquisition_aware_research_loop import (
    Stage9AcquisitionAwareResearchLoopError,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
)
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9LockedBaselineExperiment,
)
from app.schemas.stage9_development_baseline_run import (
    STAGE9_DEVELOPMENT_CASE_IDS,
    Stage9DevelopmentCaseRecord,
    Stage9DevelopmentRunRequest,
)
from app.schemas.stage9_evaluation_manifest import Stage9DatasetPartition

CASE_MAXIMUM_ROUNDS = 2
CASE_MAXIMUM_TOOL_CALLS = 2
CASE_MAXIMUM_PROVIDER_CALLS = 4
CASE_MAXIMUM_EXTERNAL_REQUESTS = 6
CASE_MAXIMUM_RECORDED_TOKENS = 30_000
CASE_MAXIMUM_ELAPSED_SECONDS = 720.0


class ResearchAgentLoopProtocol(Protocol):
    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult: ...


class Stage9CaseCostEstimatorProtocol(Protocol):
    def estimate(
        self,
        *,
        loop_result: BoundedResearchAgentLoopResult,
        experiment: Stage9LockedBaselineExperiment,
    ) -> Decimal: ...


class Stage9DevelopmentCaseExecutorAdapter:
    """Bind a disclosed case, bounded loop, cost estimate, and safe writer."""

    def __init__(
        self,
        *,
        experiment: Stage9LockedBaselineExperiment,
        research_loop: ResearchAgentLoopProtocol,
        cost_estimator: Stage9CaseCostEstimatorProtocol,
        artifact_writer: Stage9DevelopmentCaseArtifactWriter,
    ) -> None:
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")
        self._experiment = experiment
        self._research_loop = research_loop
        self._cost_estimator = cost_estimator
        self._artifact_writer = artifact_writer

    def execute(
        self,
        *,
        case_id: str,
        request: Stage9DevelopmentRunRequest,
    ) -> Stage9DevelopmentCaseRecord:
        if not isinstance(request, Stage9DevelopmentRunRequest):
            raise TypeError("request must be a Stage 9 development run request")
        case = self._development_case(case_id)
        if case_id not in request.case_ids:
            raise Stage9DevelopmentCaseExecutionError(
                "case is not present in the development request"
            )

        loop_request = BoundedResearchAgentLoopRequest(
            goal=case.definition.evaluation_input.research_question,
            constraints=[
                *case.prohibited_claims,
                *case.expected_uncertainties,
                "Preserve exact source, document, chunk, and citation provenance.",
            ],
            allowed_tools=["bounded_grounded_answer"],
            budget=BoundedResearchAgentLoopBudget(
                maximum_rounds=CASE_MAXIMUM_ROUNDS,
                maximum_tool_calls=CASE_MAXIMUM_TOOL_CALLS,
                maximum_provider_calls=CASE_MAXIMUM_PROVIDER_CALLS,
                maximum_recorded_tokens=CASE_MAXIMUM_RECORDED_TOKENS,
                maximum_elapsed_seconds=CASE_MAXIMUM_ELAPSED_SECONDS,
                maximum_external_requests=CASE_MAXIMUM_EXTERNAL_REQUESTS,
            ),
        )
        try:
            loop_result = self._research_loop.run(request=loop_request)
        except (
            BoundedResearchPlanningLoopError,
            Stage9AcquisitionAwareResearchLoopError,
        ) as error:
            raise Stage9DevelopmentCaseExecutionError(
                "bounded research loop failed safely"
            ) from error
        if not isinstance(loop_result, BoundedResearchAgentLoopResult):
            raise Stage9DevelopmentCaseExecutionError(
                "research loop returned an invalid result"
            )

        estimated_cost = self._cost_estimator.estimate(
            loop_result=loop_result,
            experiment=self._experiment,
        )
        if not isinstance(estimated_cost, Decimal):
            raise Stage9DevelopmentCaseExecutionError(
                "cost estimator must return Decimal"
            )
        try:
            return self._artifact_writer.write(
                case_id=case_id,
                execution_id=f"{request.run_id}-{case_id}",
                manifest_sha256=request.manifest_sha256,
                review_sha256=request.review_sha256,
                response_model_ids=self._response_model_ids(),
                estimated_cost=estimated_cost,
                loop_result=loop_result,
            )
        except (Stage9DevelopmentCaseArtifactError, OSError, ValueError) as error:
            raise Stage9DevelopmentCaseExecutionError(
                "development case artifact persistence failed safely"
            ) from error

    def _development_case(self, case_id: str):
        if case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            raise Stage9DevelopmentCaseExecutionError(
                "only disclosed development cases may execute"
            )
        for case in self._experiment.plan.manifest.cases:
            if case.definition.case_id == case_id:
                if case.partition is not Stage9DatasetPartition.DEVELOPMENT:
                    raise Stage9DevelopmentCaseExecutionError(
                        "case partition is not development"
                    )
                return case
        raise Stage9DevelopmentCaseExecutionError(
            "development case is absent from the locked manifest"
        )

    def _response_model_ids(self) -> tuple[str, ...]:
        return tuple(
            f"{component.role.value}:{component.provider_name}:"
            f"{component.model_name}:{component.operation}"
            for component in self._experiment.runtime_stack.components
        )
