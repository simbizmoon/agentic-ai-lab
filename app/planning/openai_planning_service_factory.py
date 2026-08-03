"""Factory for the integrated OpenAI planning service."""

from __future__ import annotations

from app.planning.openai_planner_factory import (
    create_openai_planner_client,
)
from app.planning.plan_factory import PlanFactory
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.planning.planning_service import PlanningService
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)
from app.schemas.planner_prompt_config import (
    PlannerPromptConfig,
)


def create_openai_planning_service(
    *,
    client_config: PlannerClientConfig | None = None,
    prompt_config: PlannerPromptConfig | None = None,
) -> PlanningService:
    """Create the default integrated OpenAI planner."""

    return PlanningService(
        prompt_composer=PlannerPromptComposer(
            config=prompt_config
        ),
        planner_client=create_openai_planner_client(
            config=client_config
        ),
        plan_factory=PlanFactory(),
    )
