"""Tests for the final AIRA result guardrail."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.research.research_result_guardrail import (
    ResearchResultGuardrail,
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
            "# Traceable Evidence\n\n"
            "A grounded claim is connected to evidence "
            "and a source citation."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)

    return pipeline.run(
        ResearchRequest(
            request_id="guardrail-001",
            question=(
                "How is a grounded claim connected to evidence?"
            ),
            objective=(
                "Explain the traceable relationship among "
                "claims, evidence, and citations."
            ),
            preferred_source_types=[
                ResearchSourceType.OTHER,
            ],
            maximum_sources=1,
        )
    )


def test_guardrail_accepts_complete_result(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)

    ResearchResultGuardrail().validate(
        result,
        execution_id="guardrail-001",
    )


def test_guardrail_rejects_execution_id_mismatch(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)

    with pytest.raises(
        ValueError,
        match="request_id must match execution_id",
    ):
        ResearchResultGuardrail().validate(
            result,
            execution_id="different-execution",
        )


def test_guardrail_rejects_missing_claims(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)
    empty_claim_set = (
        result.workspace.claim_set.model_copy(
            update={"claims": []}
        )
    )
    workspace = result.workspace.model_copy(
        update={"claim_set": empty_claim_set}
    )
    invalid = result.model_copy(
        update={"workspace": workspace}
    )

    with pytest.raises(
        ValueError,
        match="at least one claim",
    ):
        ResearchResultGuardrail().validate(
            invalid,
            execution_id="guardrail-001",
        )


def test_guardrail_rejects_missing_citations(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)
    report = result.report.model_copy(
        update={
            "citations": [],
            "citation_count": 0,
        }
    )
    quality = result.quality.model_copy(
        update={"report": report}
    )
    invalid = result.model_copy(
        update={
            "report": report,
            "quality": quality,
        }
    )

    with pytest.raises(
        ValueError,
        match="at least one citation",
    ):
        ResearchResultGuardrail().validate(
            invalid,
            execution_id="guardrail-001",
        )
