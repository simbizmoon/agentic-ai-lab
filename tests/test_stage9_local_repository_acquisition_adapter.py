"""Offline tests for bounded Stage 9 local-repository acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.research.stage9_local_repository_acquisition_adapter import (
    Stage9LocalRepositoryAcquisitionAdapter,
    Stage9LocalRepositoryAcquisitionError,
)
from app.schemas.stage9_development_acquisition import (
    Stage9AcquisitionChannel,
    Stage9AcquisitionStatus,
    Stage9DevelopmentAcquisitionRequestBuilder,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


def _request():
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    case = next(
        item
        for item in experiment.plan.manifest.cases
        if item.definition.case_id == "cross-01"
    )
    return Stage9DevelopmentAcquisitionRequestBuilder().build(
        case=case,
        request_id="stage9-local-cross-01",
    )


def _repository(tmp_path: Path) -> Path:
    (tmp_path / "ROADMAP.md").write_text(
        "# Unrelated\nNo matching material here.\n\n"
        "## Integrated RAG\nThe implemented bounded workflow preserves evidence.\n\n"
        "## Another RAG boundary\nRAG context is bounded before generation.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_selects_bounded_roadmap_sections_from_question_only(tmp_path: Path) -> None:
    result = Stage9LocalRepositoryAcquisitionAdapter(
        repository_root=_repository(tmp_path)
    ).acquire(
        request=_request(),
        channel=Stage9AcquisitionChannel.LOCAL_REPOSITORY,
    )

    assert result.status is Stage9AcquisitionStatus.EVIDENCE_AVAILABLE
    assert result.provider_requests == result.external_requests == 0
    assert 1 <= len(result.evidence_set.evidence) <= 4
    document = result.evidence_set.document_set.documents[0]
    assert "implemented bounded workflow" in document.content
    assert document.candidate.metadata["golden_evidence_supplied"] == "false"
    for evidence in result.evidence_set.evidence:
        assert document.content[evidence.start_character : evidence.end_character] == (
            evidence.excerpt
        )
        assert evidence.metadata["local_filename"] == "ROADMAP.md"


def test_does_not_read_unmentioned_decisions_file(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "DECISIONS.md").write_text(
        "# Secret\nGolden expected answer must never be read.\n", encoding="utf-8"
    )
    result = Stage9LocalRepositoryAcquisitionAdapter(repository_root=root).acquire(
        request=_request(), channel=Stage9AcquisitionChannel.LOCAL_REPOSITORY
    )
    assert (
        "Golden expected answer"
        not in result.evidence_set.document_set.documents[0].content
    )


def test_rejects_symlinked_repository_evidence(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# RAG\nimplemented bounded workflow", encoding="utf-8")
    root = tmp_path / "repository"
    root.mkdir()
    (root / "ROADMAP.md").symlink_to(outside)
    with pytest.raises(Stage9LocalRepositoryAcquisitionError, match="symbolic link"):
        Stage9LocalRepositoryAcquisitionAdapter(repository_root=root).acquire(
            request=_request(), channel=Stage9AcquisitionChannel.LOCAL_REPOSITORY
        )


def test_rejects_file_over_byte_boundary(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    with pytest.raises(Stage9LocalRepositoryAcquisitionError, match="byte boundary"):
        Stage9LocalRepositoryAcquisitionAdapter(
            repository_root=root, maximum_file_bytes=10
        ).acquire(request=_request(), channel=Stage9AcquisitionChannel.LOCAL_REPOSITORY)


def test_rejects_wrong_channel(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="local_repository"):
        Stage9LocalRepositoryAcquisitionAdapter(
            repository_root=_repository(tmp_path)
        ).acquire(
            request=_request(), channel=Stage9AcquisitionChannel.SCHOLARLY_PRIMARY
        )
