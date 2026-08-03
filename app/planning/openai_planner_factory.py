"""Factory helpers for OpenAI structured planner clients."""

from __future__ import annotations

from openai import OpenAI

from app.planning.openai_planner_client import (
    OpenAIPlannerClient,
)
from app.schemas.planner_client_config import (
    PlannerClientConfig,
)


def create_openai_planner_client(
    *,
    config: PlannerClientConfig | None = None,
) -> OpenAIPlannerClient:
    """Create a planner using the environment API key."""

    return OpenAIPlannerClient(
        client=OpenAI(),
        config=config,
    )
