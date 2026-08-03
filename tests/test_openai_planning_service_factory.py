"""Tests for integrated OpenAI planning-service construction."""

from app.planning.openai_planning_service_factory import (
    create_openai_planning_service,
)
from app.planning.planning_service import PlanningService
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)
from app.schemas.planner_prompt_config import (
    PlannerPromptConfig,
)


def test_factory_creates_configured_service(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-api-key",
    )

    result = create_openai_planning_service(
        client_config=PlannerClientConfig(
            model="gpt-5-mini",
            reasoning_effort=None,
        ),
        prompt_config=PlannerPromptConfig(
            include_metadata=True
        ),
    )

    assert isinstance(result, PlanningService)
    assert (
        result.planner_client.config.model
        == "gpt-5-mini"
    )
    assert (
        result.prompt_composer.config.include_metadata
        is True
    )
