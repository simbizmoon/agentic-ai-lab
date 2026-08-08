"""Tests for component usage metric selection."""

from types import SimpleNamespace

from app.budget import BudgetUsage
from app.research.single_research_agent_pipeline import (
    SingleResearchAgentPipeline,
)


def test_component_metrics_prefer_physical_api_usage() -> None:
    component = SimpleNamespace(
        last_usage=BudgetUsage(
            attempts=3,
            recorded_tokens=30,
            elapsed_seconds=3.0,
        ),
        last_api_usage=BudgetUsage(
            attempts=1,
            recorded_tokens=30,
            elapsed_seconds=1.0,
        ),
    )

    metrics = (
        SingleResearchAgentPipeline
        ._component_usage_metrics(component)
    )

    assert metrics.call_count == 1
    assert metrics.recorded_tokens == 30
    assert metrics.elapsed_seconds == 1.0


def test_component_metrics_fall_back_to_last_usage() -> None:
    component = SimpleNamespace(
        last_usage=BudgetUsage(
            attempts=2,
            recorded_tokens=20,
            elapsed_seconds=2.0,
        )
    )

    metrics = (
        SingleResearchAgentPipeline
        ._component_usage_metrics(component)
    )

    assert metrics.call_count == 2
    assert metrics.recorded_tokens == 20
    assert metrics.elapsed_seconds == 2.0
