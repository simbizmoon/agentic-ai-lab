"""Prepare the exact Stage 9 OpenAI runtime without making provider calls."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.grounded_answer_service import OpenAIClientProtocol
from app.research.bounded_grounded_answer_factory import (
    create_bounded_grounded_answer_orchestrator,
)
from app.research.bounded_grounded_answer_orchestrator import (
    BoundedGroundedAnswerOrchestrator,
)
from app.research.openai_semantic_citation_evaluator import (
    OpenAISemanticCitationEvaluator,
    SemanticCitationOpenAIClient,
)
from app.schemas.planner_client_config import PlannerClientConfig
from app.schemas.stage9_baseline_runtime_stack import (
    Stage9BaselineRuntimeStack,
    Stage9RuntimeComponentRole,
)

OPENAI_PROVIDER_NAME = "OpenAI"
PLANNER_OPERATION = "responses.create"
GENERATOR_OPERATION = "responses.create"
CITATION_EVALUATOR_OPERATION = "responses.parse"


@dataclass(frozen=True)
class Stage9PreparedRuntime:
    """Resolved configuration and composed workflow; no request has been sent."""

    planner_config: PlannerClientConfig
    generator_model: str
    citation_evaluator_model: str
    grounded_answer_orchestrator: BoundedGroundedAnswerOrchestrator


class Stage9BaselineRuntimePreflight:
    """Bind a locked component stack to the existing production adapters."""

    def prepare(
        self,
        *,
        runtime_stack: Stage9BaselineRuntimeStack,
        generation_client: OpenAIClientProtocol,
        citation_client: SemanticCitationOpenAIClient,
    ) -> Stage9PreparedRuntime:
        if not isinstance(runtime_stack, Stage9BaselineRuntimeStack):
            raise TypeError("runtime_stack must be Stage9BaselineRuntimeStack")

        planner = runtime_stack.component(Stage9RuntimeComponentRole.PLANNER)
        generator = runtime_stack.component(
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR
        )
        evaluator = runtime_stack.component(
            Stage9RuntimeComponentRole.CITATION_EVALUATOR
        )
        self._validate_adapter_boundary(
            planner=planner,
            generator=generator,
            evaluator=evaluator,
        )

        planner_config = PlannerClientConfig(
            model=planner.model_name,
            reasoning_effort=planner.reasoning_effort,
            store=False,
        )
        citation_evaluator = OpenAISemanticCitationEvaluator(
            client=citation_client,
            model=evaluator.model_name,
        )
        orchestrator = create_bounded_grounded_answer_orchestrator(
            client=generation_client,
            model=generator.model_name,
            citation_evaluator=citation_evaluator,
        )
        return Stage9PreparedRuntime(
            planner_config=planner_config,
            generator_model=generator.model_name,
            citation_evaluator_model=evaluator.model_name,
            grounded_answer_orchestrator=orchestrator,
        )

    @staticmethod
    def _validate_adapter_boundary(*, planner, generator, evaluator) -> None:
        for component in (planner, generator, evaluator):
            if component.provider_name.casefold() != OPENAI_PROVIDER_NAME.casefold():
                raise ValueError("current Stage 9 adapters require the OpenAI provider")
        expected_operations = {
            Stage9RuntimeComponentRole.PLANNER: PLANNER_OPERATION,
            Stage9RuntimeComponentRole.GROUNDED_ANSWER_GENERATOR: GENERATOR_OPERATION,
            Stage9RuntimeComponentRole.CITATION_EVALUATOR: CITATION_EVALUATOR_OPERATION,
        }
        for component in (planner, generator, evaluator):
            if component.operation != expected_operations[component.role]:
                raise ValueError(
                    "runtime operation does not match the existing adapter"
                )
        if (
            generator.reasoning_effort is not None
            or evaluator.reasoning_effort is not None
        ):
            raise ValueError(
                "generator and evaluator adapters do not expose reasoning effort"
            )
