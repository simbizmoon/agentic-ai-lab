"""Tests for the local-document AIRA runtime."""

from __future__ import annotations

from pathlib import Path

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.schemas.research_request import (
    ResearchRequest,
    ResearchSourceType,
)


def test_local_runtime_runs_end_to_end(
    tmp_path: Path,
) -> None:
    source = tmp_path / "grounded-research.md"
    source.write_text(
        (
            "# Grounded Research Evidence\n\n"
            "Grounded research connects claims to "
            "traceable evidence and citations."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)
    request = ResearchRequest(
        request_id="local-runtime-001",
        question=(
            "How does grounded research use traceable evidence?"
        ),
        objective=(
            "Explain how grounded research connects claims "
            "to evidence and citations."
        ),
        include_topics=["grounded research evidence"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    assert result.workspace.progress().candidate_count == 1
    assert result.workspace.progress().document_count == 1
    assert result.workspace.progress().evidence_count == 1
    assert result.workspace.progress().claim_count == 1
    assert result.report.claim_count == 1
    assert result.report.citation_count == 1
    assert result.quality.passed is True


def test_local_runtime_supports_korean_search(
    tmp_path: Path,
) -> None:
    source = tmp_path / "근거기반연구.md"
    source.write_text(
        (
            "# 근거 기반 연구\n\n"
            "근거 기반 연구는 주장과 출처 및 증거를 "
            "추적 가능하게 연결한다."
        ),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)
    request = ResearchRequest(
        request_id="local-runtime-ko-001",
        question=(
            "근거 기반 연구는 주장과 증거를 어떻게 연결하는가?"
        ),
        objective=(
            "출처와 증거의 추적 가능성을 바탕으로 "
            "근거 기반 연구를 설명한다."
        ),
        include_topics=["근거 기반 연구"],
        preferred_source_types=[ResearchSourceType.OTHER],
        maximum_sources=4,
    )

    result = pipeline.run(request)

    assert result.workspace.progress().candidate_count == 1
    assert result.workspace.progress().claim_count == 1
