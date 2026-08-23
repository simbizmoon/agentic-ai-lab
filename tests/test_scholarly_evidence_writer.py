"""Tests for private scholarly evidence artifact persistence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_evidence_formatter import (
    DeterministicScholarlyEvidenceFormatter,
)
from app.research.scholarly_evidence_writer import (
    SCHOLARLY_EVIDENCE_DIRECTORY_MODE,
    SCHOLARLY_EVIDENCE_FILE_MODE,
    ScholarlyEvidenceWriteError,
    ScholarlyEvidenceWriter,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_provider import (
    ScholarlyProviderError,
    ScholarlyProviderUsage,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self, result: ScholarlySearchResult) -> None:
        self._result = result

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        assert request == self._result.request
        return self._result


def workflow_result():
    request = ScholarlySearchRequest(
        request_id="request-001",
        query="private scholarly artifacts",
        maximum_results=1,
        maximum_provider_requests=1,
    )
    provider_result = ScholarlySearchResult(
        request=request,
        provider="fixture-provider",
        status=ScholarlySearchStatus.FAILED,
        error=ScholarlyProviderError(
            error_type="FixtureFailure",
            message="Controlled offline fixture failure.",
        ),
        usage=ScholarlyProviderUsage(
            request_count=1,
            records_received=0,
            records_accepted=0,
            records_rejected=0,
            duration_ms=1.0,
        ),
    )
    return BoundedScholarlyEvidenceWorkflow(
        provider=FixtureProvider(provider_result)
    ).run(request, task_id="task-001")


def test_writer_creates_exact_formatter_artifacts(tmp_path: Path) -> None:
    source = workflow_result()
    formatted = DeterministicScholarlyEvidenceFormatter().format(source)
    paths = ScholarlyEvidenceWriter().write(
        source,
        output_dir=tmp_path / "reports",
        execution_id="scholarly-001",
    )
    assert paths.execution_dir == tmp_path / "reports" / "scholarly-001"
    assert paths.markdown_path == paths.execution_dir / "evidence.md"
    assert paths.json_path == paths.execution_dir / "evidence.json"
    assert paths.markdown_path.read_text(encoding="utf-8") == formatted.markdown
    assert paths.json_path.read_text(encoding="utf-8") == formatted.json_text


def test_writer_uses_private_permissions(tmp_path: Path) -> None:
    paths = ScholarlyEvidenceWriter().write(
        workflow_result(), output_dir=tmp_path, execution_id="scholarly-001"
    )
    assert paths.execution_dir.stat().st_mode & 0o777 == (
        SCHOLARLY_EVIDENCE_DIRECTORY_MODE
    )
    assert paths.markdown_path.stat().st_mode & 0o777 == SCHOLARLY_EVIDENCE_FILE_MODE
    assert paths.json_path.stat().st_mode & 0o777 == SCHOLARLY_EVIDENCE_FILE_MODE


@pytest.mark.parametrize(
    "execution_id",
    ("", " ", ".", "..", "../escape", "nested/path", "nested\\path", "/abs"),
)
def test_writer_rejects_unsafe_execution_id(tmp_path: Path, execution_id: str) -> None:
    with pytest.raises(ValueError):
        ScholarlyEvidenceWriter().write(
            workflow_result(), output_dir=tmp_path, execution_id=execution_id
        )
    assert list(tmp_path.iterdir()) == []


def test_writer_rejects_wrong_types(tmp_path: Path) -> None:
    with pytest.raises(
        TypeError, match="result must be a BoundedScholarlyEvidenceWorkflowResult"
    ):
        ScholarlyEvidenceWriter().write(
            object(),
            output_dir=tmp_path,
            execution_id="scholarly-001",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="output_dir must be a Path"):
        ScholarlyEvidenceWriter().write(
            workflow_result(),
            output_dir="reports",  # type: ignore[arg-type]
            execution_id="scholarly-001",
        )
    with pytest.raises(TypeError, match="execution_id must be a string"):
        ScholarlyEvidenceWriter().write(
            workflow_result(),
            output_dir=tmp_path,
            execution_id=123,  # type: ignore[arg-type]
        )


def test_writer_rejects_file_as_output_directory(tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="output path is not a directory"):
        ScholarlyEvidenceWriter().write(
            workflow_result(),
            output_dir=output_file,
            execution_id="scholarly-001",
        )
    assert output_file.read_text(encoding="utf-8") == "existing"


def test_writer_refuses_existing_execution(tmp_path: Path) -> None:
    writer = ScholarlyEvidenceWriter()
    writer.write(workflow_result(), output_dir=tmp_path, execution_id="scholarly-001")
    with pytest.raises(ValueError, match="execution directory already exists"):
        writer.write(
            workflow_result(), output_dir=tmp_path, execution_id="scholarly-001"
        )


def test_writer_rolls_back_second_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    with pytest.raises(
        ScholarlyEvidenceWriteError,
        match="scholarly evidence artifacts could not be written",
    ):
        ScholarlyEvidenceWriter().write(
            workflow_result(), output_dir=tmp_path, execution_id="scholarly-001"
        )
    assert not (tmp_path / "scholarly-001").exists()


def test_writer_converts_directory_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_mkdir = Path.mkdir

    def fail_execution_directory(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if path.name == "scholarly-001":
            raise OSError("controlled mkdir failure")
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fail_execution_directory)
    with pytest.raises(
        ScholarlyEvidenceWriteError,
        match="scholarly evidence execution directory could not be created",
    ):
        ScholarlyEvidenceWriter().write(
            workflow_result(), output_dir=tmp_path, execution_id="scholarly-001"
        )
    assert not (tmp_path / "scholarly-001").exists()


def test_writer_does_not_mutate_source(tmp_path: Path) -> None:
    source = workflow_result()
    before = source.model_dump_json()
    ScholarlyEvidenceWriter().write(
        source, output_dir=tmp_path, execution_id="scholarly-001"
    )
    assert source.model_dump_json() == before
