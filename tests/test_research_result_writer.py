"""Tests for AIRA research result writing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.research.research_result_writer import (
    ResearchResultWriter,
)
from app.schemas.research_quality import (
    ResearchQualityIssue,
    ResearchQualityIssueCode,
    ResearchQualityIssueSeverity,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)


def completed_result(tmp_path: Path):
    """Return one completed local research result."""

    source = tmp_path / "source.md"
    source.write_text(
        (
            "# Grounded Evidence\n\n"
            "Grounded research connects claims to evidence."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)

    return pipeline.run(
        ResearchRequest(
            request_id="writer-001",
            question=(
                "How does grounded research connect claims "
                "to evidence?"
            ),
            objective=(
                "Explain the traceable relationship between "
                "claims and evidence."
            ),
            preferred_source_types=[
                ResearchSourceType.OTHER,
            ],
            maximum_sources=1,
        )
    )


def test_writer_creates_markdown_and_json(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)

    paths = ResearchResultWriter().write(
        result,
        output_dir=tmp_path / "reports",
        execution_id="writer-001",
    )

    assert paths.report_path.is_file()
    assert paths.result_path.is_file()

    markdown = paths.report_path.read_text(
        encoding="utf-8"
    )
    payload = json.loads(
        paths.result_path.read_text(encoding="utf-8")
    )

    assert f"# {result.report.title}" in markdown
    assert "## Executive Summary" in markdown
    assert "## Sources" in markdown
    assert "## Quality" in markdown
    assert payload["report"]["report_id"] == (
        result.report.report_id
    )
    assert payload["quality"]["overall_score"] == (
        result.quality.overall_score
    )
    assert payload["quality"]["passed"] is True


def test_writer_serializes_failed_quality_decision(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)
    failed_quality = result.quality.model_copy(
        update={
            "issues": [
                ResearchQualityIssue(
                    code=(
                        ResearchQualityIssueCode
                        .LOW_SOURCE_DIVERSITY
                    ),
                    severity=(
                        ResearchQualityIssueSeverity.ERROR
                    ),
                    message=(
                        "Independent evidence sources are "
                        "below the required minimum."
                    ),
                )
            ]
        }
    )
    failed_result = result.model_copy(
        update={"quality": failed_quality}
    )

    paths = ResearchResultWriter().write(
        failed_result,
        output_dir=tmp_path / "failed-reports",
        execution_id="writer-failed-001",
    )

    payload = json.loads(
        paths.result_path.read_text(encoding="utf-8")
    )

    assert failed_result.quality.passed is False
    assert payload["quality"]["passed"] is False


def test_writer_refuses_to_overwrite_execution(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)
    writer = ResearchResultWriter()
    output_dir = tmp_path / "reports"

    writer.write(
        result,
        output_dir=output_dir,
        execution_id="writer-001",
    )

    with pytest.raises(
        ValueError,
        match="execution directory already exists",
    ):
        writer.write(
            result,
            output_dir=output_dir,
            execution_id="writer-001",
        )
