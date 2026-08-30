"""Compose the locked Stage 9 packed-evidence planning loop."""

from __future__ import annotations

from app.planning.plan_evaluator import PlanEvaluator
from app.planning.plan_execution_service import PlanExecutionService
from app.planning.plan_factory import PlanFactory
from app.planning.plan_lifecycle_service import PlanLifecycleService
from app.planning.plan_runner import PlanRunner
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import PlanStepExecutor
from app.planning.planner_client import PlannerClient
from app.planning.planner_prompt_composer import PlannerPromptComposer
from app.planning.planning_agent_loop import PlanningAgentLoop
from app.planning.planning_agent_pipeline import PlanningAgentPipeline
from app.planning.planning_service import PlanningService
from app.planning.replan_context_service import ReplanContextService
from app.planning.replanning_service import ReplanningService
from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
    GroundedAnswerWorkflowProtocol,
)
from app.research.bounded_research_planning_loop import BoundedResearchPlanningLoop
from app.research.stage9_locked_packed_grounded_answer_tool import (
    Stage9LockedPackedGroundedAnswerTool,
    create_stage9_locked_workflow_request,
)
from app.research.stage9_planner_usage_accounting import (
    Stage9MeteredPlannerClient,
    Stage9PlannerUsageAccountingLoop,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    ResearchAgentLoopRound,
)
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planning_agent_loop import PlanningAgentLoopRequest
from app.schemas.planning_agent_request import PlanningAgentRequest
from app.schemas.rag_context_packing import RagContextPackingResult
from app.schemas.stage9_baseline_runtime_stack import Stage9LockedBaselineExperiment
from app.schemas.stage9_development_baseline_run import STAGE9_DEVELOPMENT_CASE_IDS
from app.schemas.stage9_evaluation_manifest import Stage9DatasetPartition
from app.tools.planning_tool_registry import ToolRegistry


class _Stage9ResearchPlanningRequestFactory:
    def create(
        self,
        *,
        round_number: int,
        research_request: BoundedResearchAgentLoopRequest,
        previous_rounds: list[ResearchAgentLoopRound],
    ) -> PlanningAgentLoopRequest:
        return PlanningAgentLoopRequest(
            initial=PlanningAgentRequest(
                planning=PlanCreationRequest(
                    goal=research_request.goal,
                    constraints=[
                        *research_request.constraints,
                        "Execute bounded_grounded_answer exactly once.",
                        "Do not invent or replace evidence, citations, or budgets.",
                    ],
                    available_tools=[BOUNDED_GROUNDED_ANSWER_TOOL_NAME],
                    maximum_steps=1,
                    require_tool_for_each_step=True,
                    metadata={
                        "stage9_research_round": round_number,
                        "previous_research_rounds": len(previous_rounds),
                    },
                )
            ),
            maximum_replans=0,
        )


class Stage9PackedResearchLoopFactoryError(RuntimeError):
    """A requested packed loop was outside the locked development partition."""


class Stage9PackedResearchLoopFactory:
    """Build one case-specific loop with immutable evidence and metered planning."""

    def __init__(
        self,
        *,
        experiment: Stage9LockedBaselineExperiment,
        planner_client: PlannerClient,
        planner_meter: Stage9MeteredPlannerClient,
        grounded_workflow: GroundedAnswerWorkflowProtocol,
    ) -> None:
        if not isinstance(experiment, Stage9LockedBaselineExperiment):
            raise TypeError("experiment must be a locked Stage 9 experiment")
        if not isinstance(planner_client, PlannerClient):
            raise TypeError("planner_client must be PlannerClient")
        self._experiment = experiment
        self._planner_client = planner_client
        self._planner_meter = planner_meter
        self._grounded_workflow = grounded_workflow

    def create(
        self,
        *,
        case_id: str,
        packing: RagContextPackingResult,
    ) -> Stage9PlannerUsageAccountingLoop:
        case = self._development_case(case_id)
        workflow_request = create_stage9_locked_workflow_request(
            question=case.definition.evaluation_input.research_question,
            packing=packing,
        )
        registry = ToolRegistry()
        registry.register(
            Stage9LockedPackedGroundedAnswerTool(
                workflow=self._grounded_workflow,
                workflow_request=workflow_request,
            )
        )
        plan_factory = PlanFactory()
        pipeline = PlanningAgentPipeline(
            planning_service=PlanningService(
                prompt_composer=PlannerPromptComposer(),
                planner_client=self._planner_client,
                plan_factory=plan_factory,
            ),
            plan_runner=PlanRunner(
                execution_service=PlanExecutionService(
                    scheduler=PlanScheduler(),
                    lifecycle=PlanLifecycleService(),
                    step_executor=PlanStepExecutor(registry=registry),
                )
            ),
            plan_evaluator=PlanEvaluator(),
        )
        planning_loop = PlanningAgentLoop(
            pipeline=pipeline,
            replan_context_service=ReplanContextService(),
            replanning_service=ReplanningService(
                prompt_composer=PlannerPromptComposer(),
                planner_client=self._planner_client,
                plan_factory=plan_factory,
            ),
        )
        research_loop = BoundedResearchPlanningLoop(
            planning_loop=planning_loop,
            request_factory=_Stage9ResearchPlanningRequestFactory(),
        )
        return Stage9PlannerUsageAccountingLoop(
            loop=research_loop,
            meter=self._planner_meter,
        )

    def _development_case(self, case_id: str):
        if case_id not in STAGE9_DEVELOPMENT_CASE_IDS:
            raise Stage9PackedResearchLoopFactoryError(
                "only disclosed development cases may create packed loops"
            )
        matches = [
            case
            for case in self._experiment.plan.manifest.cases
            if case.definition.case_id == case_id
            and case.partition is Stage9DatasetPartition.DEVELOPMENT
        ]
        if len(matches) != 1:
            raise Stage9PackedResearchLoopFactoryError(
                "case did not identify one locked development record"
            )
        return matches[0]
