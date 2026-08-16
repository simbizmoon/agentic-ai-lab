"""Tests for AIRA research result writing."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.research.local_document_adapter import (
    LocalDocumentAdapter,
)
from app.research.local_runtime import (
    build_local_research_pipeline,
)
from app.research.research_result_writer import (
    ResearchResultWriteError,
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
        ("# Grounded Evidence\n\nGrounded research connects claims to evidence."),
        encoding="utf-8",
    )
    bundle = LocalDocumentAdapter().load((source,))
    pipeline = build_local_research_pipeline(bundle)

    return pipeline.run(
        ResearchRequest(
            request_id="writer-001",
            question=("How does grounded research connect claims to evidence?"),
            objective=(
                "Explain the traceable relationship between claims and evidence."
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

    markdown = paths.report_path.read_text(encoding="utf-8")
    payload = json.loads(paths.result_path.read_text(encoding="utf-8"))

    assert f"# {result.report.title}" in markdown
    assert "## Executive Summary" in markdown
    assert "## Sources" in markdown
    assert "## Quality" in markdown
    assert payload["report"]["report_id"] == (result.report.report_id)
    assert payload["quality"]["overall_score"] == (result.quality.overall_score)
    assert payload["quality"]["passed"] is True


def test_writer_serializes_failed_quality_decision(
    tmp_path: Path,
) -> None:
    result = completed_result(tmp_path)
    failed_quality = result.quality.model_copy(
        update={
            "issues": [
                ResearchQualityIssue(
                    code=(ResearchQualityIssueCode.LOW_SOURCE_DIVERSITY),
                    severity=(ResearchQualityIssueSeverity.ERROR),
                    message=(
                        "Independent evidence sources are below the required minimum."
                    ),
                )
            ]
        }
    )
    failed_result = result.model_copy(update={"quality": failed_quality})

    paths = ResearchResultWriter().write(
        failed_result,
        output_dir=tmp_path / "failed-reports",
        execution_id="writer-failed-001",
    )

    payload = json.loads(paths.result_path.read_text(encoding="utf-8"))

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


@pytest.mark.parametrize("permissive_umask", [0o000, 0o002])
def test_writer_creates_private_artifacts_without_changing_output_root(
    tmp_path: Path,
    permissive_umask: int,
) -> None:
    result = completed_result(tmp_path)
    output_dir = tmp_path / "shared-reports"
    output_dir.mkdir()
    output_dir.chmod(0o775)
    previous_umask = os.umask(permissive_umask)
    try:
        paths = ResearchResultWriter().write(
            result,
            output_dir=output_dir,
            execution_id="aira-0123456789abcdef",
        )
    finally:
        os.umask(previous_umask)

    assert output_dir.stat().st_mode & 0o777 == 0o775
    assert paths.execution_dir.stat().st_mode & 0o777 == 0o700
    assert paths.report_path.stat().st_mode & 0o777 == 0o600
    assert paths.result_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "execution_id",
    ["", "   ", ".", "..", "nested/run", r"nested\run", "/tmp/absolute"],
)
def test_writer_rejects_unsafe_execution_id(
    tmp_path: Path,
    execution_id: str,
) -> None:
    result = completed_result(tmp_path)

    with pytest.raises(ValueError):
        ResearchResultWriter().write(
            result,
            output_dir=tmp_path / "reports",
            execution_id=execution_id,
        )

    assert not (tmp_path / "reports").exists()


def test_writer_rejects_execution_directory_symlink(tmp_path: Path) -> None:
    result = completed_result(tmp_path)
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    target = tmp_path / "other"
    target.mkdir()
    execution_dir = output_dir / "writer-001"
    try:
        execution_dir.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(ValueError, match="execution directory already exists"):
        ResearchResultWriter().write(
            result,
            output_dir=output_dir,
            execution_id="writer-001",
        )

    assert execution_dir.is_symlink()


def test_writer_uses_private_same_directory_temps_replace_and_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = completed_result(tmp_path)
    original_replace = os.replace
    original_fsync = os.fsync
    replacements: list[tuple[Path, Path, int]] = []
    fsync_calls: list[int] = []

    def recording_replace(source: Path, target: Path) -> None:
        replacements.append(
            (Path(source), Path(target), Path(source).stat().st_mode & 0o777)
        )
        original_replace(source, target)

    def recording_fsync(file_descriptor: int) -> None:
        fsync_calls.append(file_descriptor)
        original_fsync(file_descriptor)

    monkeypatch.setattr(
        "app.research.research_result_writer.os.replace",
        recording_replace,
    )
    monkeypatch.setattr(
        "app.research.research_result_writer.os.fsync",
        recording_fsync,
    )

    paths = ResearchResultWriter().write(
        result,
        output_dir=tmp_path / "reports",
        execution_id="writer-atomic-001",
    )

    assert [target for _source, target, _mode in replacements] == [
        paths.report_path,
        paths.result_path,
    ]
    assert all(source.parent == paths.execution_dir for source, _, _ in replacements)
    assert all(mode == 0o600 for _, _, mode in replacements)
    assert len(fsync_calls) == 3
    assert list(paths.execution_dir.glob("*.tmp")) == []


def test_writer_rejects_final_target_symlink_without_following_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = completed_result(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("unchanged", encoding="utf-8")
    original_prepare = ResearchResultWriter._prepare_temp_file

    def prepare_and_inject_symlink(
        *, execution_dir: Path, target: Path, text: str
    ) -> Path:
        temp_path = original_prepare(
            execution_dir=execution_dir,
            target=target,
            text=text,
        )
        if target.name == "result.json":
            try:
                (execution_dir / "report.md").symlink_to(outside)
            except OSError as error:
                pytest.skip(f"symlink creation unavailable: {error}")
        return temp_path

    monkeypatch.setattr(
        ResearchResultWriter,
        "_prepare_temp_file",
        staticmethod(prepare_and_inject_symlink),
    )

    with pytest.raises(ResearchResultWriteError, match="target is unsafe"):
        ResearchResultWriter().write(
            result,
            output_dir=tmp_path / "reports",
            execution_id="writer-symlink-001",
        )

    execution_dir = tmp_path / "reports" / "writer-symlink-001"
    assert outside.read_text(encoding="utf-8") == "unchanged"
    assert not (execution_dir / "result.json").exists()
    assert list(execution_dir.glob("*.tmp")) == []


def test_writer_cleans_temps_and_execution_directory_on_temp_fsync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = completed_result(tmp_path)

    def fail_fsync(file_descriptor: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(
        "app.research.research_result_writer.os.fsync",
        fail_fsync,
    )

    with pytest.raises(ResearchResultWriteError, match="could not be written"):
        ResearchResultWriter().write(
            result,
            output_dir=tmp_path / "reports",
            execution_id="writer-fsync-temp-001",
        )

    assert not (tmp_path / "reports" / "writer-fsync-temp-001").exists()


def test_writer_rolls_back_first_install_when_second_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = completed_result(tmp_path)
    original_replace = os.replace
    replace_count = 0

    def fail_second_replace(source: Path, target: Path) -> None:
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("replace failed")
        original_replace(source, target)

    monkeypatch.setattr(
        "app.research.research_result_writer.os.replace",
        fail_second_replace,
    )

    with pytest.raises(ResearchResultWriteError, match="could not be written") as error:
        ResearchResultWriter().write(
            result,
            output_dir=tmp_path / "reports",
            execution_id="writer-replace-001",
        )

    assert isinstance(error.value.__cause__, OSError)
    assert not (tmp_path / "reports" / "writer-replace-001").exists()


def test_writer_rolls_back_installed_files_when_directory_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = completed_result(tmp_path)
    original_fsync = os.fsync
    fsync_count = 0

    def fail_directory_fsync(file_descriptor: int) -> None:
        nonlocal fsync_count
        fsync_count += 1
        if fsync_count == 3:
            raise OSError("directory fsync failed")
        original_fsync(file_descriptor)

    monkeypatch.setattr(
        "app.research.research_result_writer.os.fsync",
        fail_directory_fsync,
    )

    with pytest.raises(ResearchResultWriteError, match="could not be written") as error:
        ResearchResultWriter().write(
            result,
            output_dir=tmp_path / "reports",
            execution_id="writer-fsync-directory-001",
        )

    assert isinstance(error.value.__cause__, OSError)
    assert not (tmp_path / "reports" / "writer-fsync-directory-001").exists()
