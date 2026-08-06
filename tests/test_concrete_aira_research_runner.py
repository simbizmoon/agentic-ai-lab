"""Tests for the concrete AIRA research runner."""

import json
from pathlib import Path

import pytest

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
from app.research.research_result_writer import (
    ResearchResultWriter,
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


def pipeline_factory(_research_request):
    """Return one deterministic local research pipeline."""

    return build_local_research_pipeline(bundle())


def test_runner_executes_pipeline_and_maps_output() -> None:
    runner = ConcreteAiraResearchRunner(
        pipeline_factory=pipeline_factory
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
    assert output.result["artifact_paths"] == {}
    assert len(output.citation_ids) == 1
    assert output.artifact_ids == []


def test_runner_writes_report_and_result_artifacts(
    tmp_path: Path,
) -> None:
    runner = ConcreteAiraResearchRunner(
        pipeline_factory=pipeline_factory,
        writer=ResearchResultWriter(),
        output_dir=tmp_path / "reports",
        artifact_execution_id_factory=(
            lambda _request: "artifact-execution-001"
        ),
    )

    output = runner.execute(request())

    execution_dir = (
        tmp_path / "reports" / "artifact-execution-001"
    )
    report_path = execution_dir / "report.md"
    result_path = execution_dir / "result.json"

    assert report_path.is_file()
    assert result_path.is_file()
    assert output.artifact_ids == [
        "artifact-execution-001:report",
        "artifact-execution-001:result",
    ]
    assert output.result["artifact_paths"] == {
        "execution_dir": str(execution_dir.resolve()),
        "report": str(report_path.resolve()),
        "result": str(result_path.resolve()),
    }

    payload = json.loads(
        result_path.read_text(encoding="utf-8")
    )
    assert payload["workspace"]["request"]["request_id"] == (
        "research-001"
    )


def test_runner_requires_writer_and_output_dir_together(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="writer and output_dir must be provided together",
    ):
        ConcreteAiraResearchRunner(
            pipeline_factory=pipeline_factory,
            writer=ResearchResultWriter(),
        )

    with pytest.raises(
        ValueError,
        match="writer and output_dir must be provided together",
    ):
        ConcreteAiraResearchRunner(
            pipeline_factory=pipeline_factory,
            output_dir=tmp_path,
        )


def test_runner_rejects_blank_artifact_execution_id(
    tmp_path: Path,
) -> None:
    runner = ConcreteAiraResearchRunner(
        pipeline_factory=pipeline_factory,
        writer=ResearchResultWriter(),
        output_dir=tmp_path,
        artifact_execution_id_factory=lambda _request: " ",
    )

    with pytest.raises(
        RuntimeError,
        match="artifact execution ID factory returned blank",
    ):
        runner.execute(request())


def test_runner_preserves_writer_collision_failure(
    tmp_path: Path,
) -> None:
    runner = ConcreteAiraResearchRunner(
        pipeline_factory=pipeline_factory,
        writer=ResearchResultWriter(),
        output_dir=tmp_path,
        artifact_execution_id_factory=(
            lambda _request: "artifact-execution-001"
        ),
    )

    runner.execute(request())

    with pytest.raises(
        ValueError,
        match="execution directory already exists",
    ):
        runner.execute(request())
