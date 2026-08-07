"""Tests for the live research CLI handler."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from app.research.live_research_handler import (
    LIVE_CLAIM_GENERATION_BUDGET,
    LiveResearchHandler,
)
from app.schemas.tavily_search_config import (
    TavilySearchConfig,
)


class FakeWriter:
    """Marker writer replaced by a fake runner boundary."""


def test_handler_rejects_blank_execution_id() -> None:
    handler = LiveResearchHandler(
        id_factory=lambda: " ",
        config_loader=lambda: TavilySearchConfig(
            api_key=SecretStr("secret")
        ),
    )

    try:
        handler(
            "How does live grounded research work?",
            "Explain live grounded research safely.",
            1,
            1024,
            Path("reports"),
        )
    except RuntimeError as error:
        assert "execution ID factory returned blank" in str(error)
    else:
        raise AssertionError("expected RuntimeError")


def test_live_claim_generation_budget_is_bounded() -> None:
    assert LIVE_CLAIM_GENERATION_BUDGET.max_attempts == 8
    assert (
        LIVE_CLAIM_GENERATION_BUDGET.max_recorded_tokens
        == 8_000
    )
    assert (
        LIVE_CLAIM_GENERATION_BUDGET.max_elapsed_seconds
        == 60.0
    )
