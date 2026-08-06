"""Tests for application-to-domain research request adaptation."""

import pytest

from app.application.research_execution import (
    ApplicationResearchExecutionRequest,
)
from app.research.application_research_request_adapter import (
    ApplicationResearchRequestAdapter,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
    ResearchSourceType,
)


def request(
    *,
    context: dict | None = None,
) -> ApplicationResearchExecutionRequest:
    """Return one valid application request."""

    return ApplicationResearchExecutionRequest(
        request_id="research-001",
        workspace_id="workspace-001",
        agent_id="aira-live-001",
        query="How does grounded research preserve evidence?",
        context=context or {},
        metadata={"mode": "live"},
    )


def test_adapter_uses_explicit_defaults() -> None:
    value = ApplicationResearchRequestAdapter().adapt(
        request()
    )

    assert value.request_id == "research-001"
    assert value.question.startswith("How does")
    assert value.maximum_sources == 5
    assert value.require_citations is True
    assert value.metadata["mode"] == "live"


def test_adapter_maps_supported_context() -> None:
    value = ApplicationResearchRequestAdapter().adapt(
        request(
            context={
                "objective": "Explain grounded evidence handling.",
                "depth": "quick",
                "output_format": "brief",
                "include_topics": ["citations"],
                "exclude_topics": ["pricing"],
                "preferred_source_types": [
                    "official_documentation"
                ],
                "start_date": "2026-01-01",
                "end_date": "2026-08-06",
                "maximum_sources": 3,
                "require_citations": False,
            }
        )
    )

    assert value.objective == (
        "Explain grounded evidence handling."
    )
    assert value.depth is ResearchDepth.QUICK
    assert value.output_format is ResearchOutputFormat.BRIEF
    assert value.preferred_source_types == [
        ResearchSourceType.OFFICIAL_DOCUMENTATION
    ]
    assert value.maximum_sources == 3
    assert value.require_citations is False


@pytest.mark.parametrize(
    "context",
    [
        {"maximum_sources": True},
        {"maximum_sources": 0},
        {"require_citations": "yes"},
        {"start_date": "not-a-date"},
        {"preferred_source_types": ["unknown"]},
        {"include_topics": "not-a-list"},
    ],
)
def test_adapter_rejects_invalid_context(
    context: dict,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ApplicationResearchRequestAdapter().adapt(
            request(context=context)
        )
