"""Tests for safe Step 4G patent comparison artifact persistence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.research.patent_multi_patent_comparison_formatter import (
    DeterministicPatentMultiPatentComparisonFormatter,
)
from app.research.patent_multi_patent_comparison_writer import (
    PATENT_COMPARISON_DIRECTORY_MODE,
    PATENT_COMPARISON_FILE_MODE,
    PatentMultiPatentComparisonWriteError,
    PatentMultiPatentComparisonWriter,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceJudgment,
    EvidenceRelevanceLevel,
)
from app.schemas.patent_multi_patent_comparison import (
    PatentMultiPatentComparison,
    PatentMultiPatentComparisonClaim,
    PatentMultiPatentComparisonClaimSet,
    PatentMultiPatentComparisonRow,
    PatentPriorArtPublicationComparison,
)
from app.schemas.patent_prior_art_evidence_mapping import (
    PatentPriorArtEvidenceEvaluation,
)


def comparison() -> PatentMultiPatentComparison:
    excerpt = "Exact patent abstract evidence."
    evaluation = PatentPriorArtEvidenceEvaluation(
        publication_number="EP2000000A1",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        excerpt=excerpt,
        start_character=0,
        end_character=len(excerpt),
        judgment=EvidenceRelevanceJudgment(
            relevance_level=EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            relevance_score=0.7,
            rationale="Fixture technical relevance.",
            issues=["Fixture technical gap."],
        ),
    )
    return PatentMultiPatentComparison(
        target_publication_number="EP1000000B1",
        target_publication_docdb="EP.1000000.B1",
        target_source_endpoint="https://ops.epo.org/example/claims",
        prior_art_publications=("EP2000000A1",),
        claim_sets=(
            PatentMultiPatentComparisonClaimSet(
                language="EN",
                claims=(
                    PatentMultiPatentComparisonClaim(
                        claim_number=1,
                        provider_position=1,
                        original_claim_text="English claim one.",
                        rows=(
                            PatentMultiPatentComparisonRow(
                                row_number=1,
                                claim_number=1,
                                provider_position=1,
                                element_number=1,
                                element_text="English element one.",
                                publications=(
                                    PatentPriorArtPublicationComparison(
                                        publication_number="EP2000000A1",
                                        evaluations=(evaluation,),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        scope_notice="Technical comparison only; no legal conclusion.",
    )


def test_writer_creates_exact_formatter_artifacts(tmp_path: Path) -> None:
    source = comparison()
    formatted = DeterministicPatentMultiPatentComparisonFormatter().format(source)

    paths = PatentMultiPatentComparisonWriter().write(
        source,
        output_dir=tmp_path / "reports",
        execution_id="comparison-001",
    )

    assert paths.execution_dir == tmp_path / "reports" / "comparison-001"
    assert paths.markdown_path == paths.execution_dir / "comparison.md"
    assert paths.json_path == paths.execution_dir / "comparison.json"
    assert paths.markdown_path.read_text(encoding="utf-8") == formatted.markdown
    assert paths.json_path.read_text(encoding="utf-8") == formatted.json_text


def test_writer_uses_private_permissions(tmp_path: Path) -> None:
    paths = PatentMultiPatentComparisonWriter().write(
        comparison(),
        output_dir=tmp_path,
        execution_id="comparison-001",
    )

    assert (
        paths.execution_dir.stat().st_mode & 0o777 == PATENT_COMPARISON_DIRECTORY_MODE
    )
    assert paths.markdown_path.stat().st_mode & 0o777 == PATENT_COMPARISON_FILE_MODE
    assert paths.json_path.stat().st_mode & 0o777 == PATENT_COMPARISON_FILE_MODE


@pytest.mark.parametrize(
    "execution_id",
    ("", " ", ".", "..", "../escape", "nested/path", "nested\\path", "/abs"),
)
def test_writer_rejects_unsafe_execution_id(
    tmp_path: Path,
    execution_id: str,
) -> None:
    with pytest.raises(ValueError):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir=tmp_path,
            execution_id=execution_id,
        )

    assert list(tmp_path.iterdir()) == []


def test_writer_rejects_non_string_execution_id(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="execution_id must be a string"):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir=tmp_path,
            execution_id=123,  # type: ignore[arg-type]
        )


def test_writer_rejects_wrong_comparison_type(tmp_path: Path) -> None:
    with pytest.raises(
        TypeError,
        match="comparison must be a PatentMultiPatentComparison",
    ):
        PatentMultiPatentComparisonWriter().write(
            object(),  # type: ignore[arg-type]
            output_dir=tmp_path,
            execution_id="comparison-001",
        )


def test_writer_requires_path_output_dir() -> None:
    with pytest.raises(TypeError, match="output_dir must be a Path"):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir="reports",  # type: ignore[arg-type]
            execution_id="comparison-001",
        )


def test_writer_rejects_file_as_output_directory(tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="output path is not a directory"):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir=output_file,
            execution_id="comparison-001",
        )

    assert output_file.read_text(encoding="utf-8") == "existing"


def test_writer_refuses_to_overwrite_existing_execution(tmp_path: Path) -> None:
    writer = PatentMultiPatentComparisonWriter()
    writer.write(
        comparison(),
        output_dir=tmp_path,
        execution_id="comparison-001",
    )

    with pytest.raises(ValueError, match="execution directory already exists"):
        writer.write(
            comparison(),
            output_dir=tmp_path,
            execution_id="comparison-001",
        )


def test_writer_cleans_up_after_atomic_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_replace = os.replace
    calls = 0

    def fail_second_replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("controlled replace failure")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second_replace)

    execution_dir = tmp_path / "comparison-001"
    with pytest.raises(
        PatentMultiPatentComparisonWriteError,
        match="patent comparison artifacts could not be written",
    ):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir=tmp_path,
            execution_id="comparison-001",
        )

    assert not execution_dir.exists()


def test_writer_converts_directory_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_mkdir = Path.mkdir

    def fail_execution_directory(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if path.name == "comparison-001":
            raise OSError("controlled mkdir failure")
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fail_execution_directory)

    with pytest.raises(
        PatentMultiPatentComparisonWriteError,
        match="execution directory could not be created",
    ):
        PatentMultiPatentComparisonWriter().write(
            comparison(),
            output_dir=tmp_path,
            execution_id="comparison-001",
        )

    assert not (tmp_path / "comparison-001").exists()


def test_writer_does_not_change_source_comparison(tmp_path: Path) -> None:
    source = comparison()
    before = source.model_dump_json()

    PatentMultiPatentComparisonWriter().write(
        source,
        output_dir=tmp_path,
        execution_id="comparison-001",
    )

    assert source.model_dump_json() == before
