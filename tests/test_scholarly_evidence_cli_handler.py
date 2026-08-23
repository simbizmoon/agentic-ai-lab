"""Tests for the bounded scholarly evidence CLI adapter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research.scholarly_evidence_cli_handler import ScholarlyEvidenceCliHandler
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest


class FakeRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, str, str, Path, str]] = []

    def execute(
        self,
        request: ScholarlyEvidenceRequest,
        *,
        request_id: str,
        task_id: str,
        output_dir: Path,
        execution_id: str,
    ) -> object:
        self.calls.append((request, request_id, task_id, output_dir, execution_id))
        return self.result


def result(tmp_path: Path) -> object:
    workflow = SimpleNamespace(
        actual_provider_requests=1,
        records_received=3,
        works_accepted=2,
        records_rejected=1,
        abstract_documents_created=1,
        works_omitted_without_abstract=1,
        whole_abstract_evidence_created=1,
    )
    paths = SimpleNamespace(
        markdown_path=tmp_path / "scholarly-001" / "evidence.md",
        json_path=tmp_path / "scholarly-001" / "evidence.json",
    )
    return SimpleNamespace(workflow_result=workflow, artifact_paths=paths)


def test_handler_prints_budget_counts_paths_and_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request = ScholarlyEvidenceRequest(
        query="bounded evidence", maximum_results=3, require_abstract=False
    )
    runtime = FakeRuntime(result(tmp_path))
    value = ScholarlyEvidenceCliHandler(
        runtime_factory=lambda _request: runtime,  # type: ignore[arg-type]
        request_id_factory=lambda: "request-001",
        execution_id_factory=lambda: "scholarly-001",
    )(request, tmp_path)
    assert value == 0
    assert runtime.calls == [
        (
            request,
            "request-001",
            "scholarly-exact-abstract-evidence",
            tmp_path,
            "scholarly-001",
        )
    ]
    output = capsys.readouterr().out
    for expected in (
        "provider=OpenAlex",
        "maximum_results=3",
        "planned_maximum_provider_requests=1",
        "openai_requests=0",
        "pdf_downloads=0",
        "actual_provider_requests=1",
        "records_rejected=1",
        "works_omitted_without_abstract=1",
        f"scholarly_evidence_markdown_path={tmp_path}/scholarly-001/evidence.md",
        f"scholarly_evidence_json_path={tmp_path}/scholarly-001/evidence.json",
        "does not assess semantic relevance",
    ):
        assert expected in output


@pytest.mark.parametrize(
    ("request_id", "execution_id", "message"),
    ((" ", "scholarly-001", "request_id"), ("request-001", "", "execution_id")),
)
def test_handler_rejects_blank_generated_identity_before_factory(
    tmp_path: Path,
    request_id: str,
    execution_id: str,
    message: str,
) -> None:
    factory_calls: list[object] = []
    with pytest.raises(ValueError, match=message):
        ScholarlyEvidenceCliHandler(
            runtime_factory=lambda value: factory_calls.append(value),  # type: ignore[arg-type,return-value]
            request_id_factory=lambda: request_id,
            execution_id_factory=lambda: execution_id,
        )(ScholarlyEvidenceRequest(query="query"), tmp_path)
    assert factory_calls == []
