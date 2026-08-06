"""Tests for the concrete AIRA research runner."""

from app.application.research_execution import (
    ApplicationResearchExecutionRequest,
)
from app.research.concrete_aira_research_runner import (
    ConcreteAiraResearchRunner,
)
from app.research.local_document_adapter import (
    LocalDocumentBundle,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentRecord,
)
from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_document import (
    ResearchSourceContentType,
)

CONTENT = (
    "Grounded research connects claims to traceable evidence."
)


def bundle() -> LocalDocumentBundle:
    """Return deterministic records for a runner test."""

    url = "https://local.aira.invalid/source/source-001"

    return LocalDocumentBundle(
        source_records=[
            InMemoryResearchSourceRecord(
                source_id="source-001",
                title="Grounded research evidence",
                url=url,
                source_type=ResearchSourceType.OTHER,
                snippet=CONTENT,
                keywords=[
                    "grounded",
                    "research",
                    "evidence",
                    "traceable",
                ],
            )
        ],
        document_records=[
            InMemoryResearchDocumentRecord(
                source_id="source-001",
                url=url,
                content_type=ResearchSourceContentType.TEXT,
                content=CONTENT,
                language="en",
            )
        ],
    )


def request() -> ApplicationResearchExecutionRequest:
    """Return one application research request."""

    return ApplicationResearchExecutionRequest(
        request_id="research-001",
        workspace_id="workspace-001",
        agent_id="aira-live-001",
        query=(
            "How does grounded research use traceable evidence?"
        ),
        context={
            "objective": (
                "Explain grounded research with traceable evidence."
            ),
            "maximum_sources": 1,
        },
    )


def test_runner_executes_pipeline_and_maps_output() -> None:
    runner = ConcreteAiraResearchRunner(
        pipeline_factory=lambda research_request: (
            build_local_research_pipeline(bundle())
        )
    )

    output = runner.execute(request())

    assert output.summary
    assert output.result["request_id"] == "research-001"
    assert output.result["workspace_id"] == "workspace-001"
    assert output.result["stage"] == "claims_built"
    assert output.result["candidate_count"] == 1
    assert output.result["successful_document_count"] == 1
    assert output.result["failed_document_count"] == 0
    assert output.result["evidence_count"] == 1
    assert output.result["claim_count"] == 1
    assert output.result["citation_count"] == 1
    assert len(output.citation_ids) == 1
    assert output.artifact_ids == []
