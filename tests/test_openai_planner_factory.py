"""Tests for OpenAI planner client construction."""

from app.planning.openai_planner_client import (
    OpenAIPlannerClient,
)
from app.planning.openai_planner_factory import (
    create_openai_planner_client,
)
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)


def test_factory_creates_configured_planner(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-api-key",
    )

    result = create_openai_planner_client(
        config=PlannerClientConfig(
            model="gpt-5-mini",
            reasoning_effort=None,
        )
    )

    assert isinstance(result, OpenAIPlannerClient)
    assert result.config.model == "gpt-5-mini"
