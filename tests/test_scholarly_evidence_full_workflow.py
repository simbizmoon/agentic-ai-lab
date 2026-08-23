"""Offline tests for scholarly evidence workflow persistence composition."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.research.bounded_scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflow,
)
from app.research.scholarly_evidence_full_workflow import (
    ScholarlyEvidenceFullWorkflow,
)
from app.research.scholarly_metadata_provider import ScholarlyMetadataProvider
from app.schemas.scholarly_evidence_request import ScholarlyEvidenceRequest
from app.schemas.scholarly_evidence_workflow import (
    BoundedScholarlyEvidenceWorkflowResult,
)
from app.schemas.scholarly_provider import (
    ScholarlyProviderUsage,
    ScholarlySearchRequest,
    ScholarlySearchResult,
    ScholarlySearchStatus,
)


class FixtureProvider(ScholarlyMetadataProvider):
    def __init__(self) -> None:
        self.calls: list[ScholarlySearchRequest] = []

    @property
    def name(self) -> str:
        return "fixture-provider"

    def search(self, request: ScholarlySearchRequest) -> ScholarlySearchResult:
        self.calls.append(request)
        return ScholarlySearchResult(
            request=request,
            provider=self.name,
            status=ScholarlySearchStatus.NO_RESULTS,
            usage=ScholarlyProviderUsage(
                request_count=1,
                records_received=0,
                records_accepted=0,
                records_rejected=0,
                duration_ms=1.0,
            ),
        )


def full_workflow(provider: FixtureProvider) -> ScholarlyEvidenceFullWorkflow:
    return ScholarlyEvidenceFullWorkflow(
        evidence_workflow=BoundedScholarlyEvidenceWorkflow(provider=provider)
    )


def test_full_workflow_runs_once_and_persists_exact_result(tmp_path: Path) -> None:
    provider = FixtureProvider()
    request = ScholarlyEvidenceRequest(query="bounded academic evidence")
    result = full_workflow(provider).execute(
        request,
        request_id="request-001",
        task_id="task-001",
        output_dir=tmp_path,
        execution_id="scholarly-001",
    )
    assert result.request is request
    assert provider.calls == [result.provider_request]
    assert result.provider_request.maximum_provider_requests == 1
    assert result.workflow_result.actual_provider_requests == 1
    assert result.artifact_paths.markdown_path.is_file()
    payload = json.loads(result.artifact_paths.json_path.read_text(encoding="utf-8"))
    assert payload == result.workflow_result.model_dump(mode="json")


def test_full_workflow_rejects_wrong_types_before_provider(tmp_path: Path) -> None:
    provider = FixtureProvider()
    workflow = full_workflow(provider)
    with pytest.raises(TypeError, match="request must be a ScholarlyEvidenceRequest"):
        workflow.execute(
            object(),  # type: ignore[arg-type]
            request_id="request-001",
            task_id="task-001",
            output_dir=tmp_path,
            execution_id="scholarly-001",
        )
    with pytest.raises(TypeError, match="output_dir must be a Path"):
        workflow.execute(
            ScholarlyEvidenceRequest(query="query"),
            request_id="request-001",
            task_id="task-001",
            output_dir="reports",  # type: ignore[arg-type]
            execution_id="scholarly-001",
        )
    assert provider.calls == []


@pytest.mark.parametrize("task_id", ("", " ", "\n"))
def test_full_workflow_rejects_blank_task_before_provider(
    tmp_path: Path, task_id: str
) -> None:
    provider = FixtureProvider()
    with pytest.raises(ValueError, match="task_id must not be blank"):
        full_workflow(provider).execute(
            ScholarlyEvidenceRequest(query="query"),
            request_id="request-001",
            task_id=task_id,
            output_dir=tmp_path,
            execution_id="scholarly-001",
        )
    assert provider.calls == []


class DivergentWorkflow:
    def run(self, request: ScholarlySearchRequest, *, task_id: str):
        different = request.model_copy(update={"request_id": "different"})
        provider = FixtureProvider()
        return BoundedScholarlyEvidenceWorkflow(provider=provider).run(
            different, task_id=task_id
        )


def test_full_workflow_rejects_divergent_nested_request(tmp_path: Path) -> None:
    workflow = ScholarlyEvidenceFullWorkflow(
        evidence_workflow=DivergentWorkflow(),  # type: ignore[arg-type]
    )
    with pytest.raises(
        RuntimeError, match="evidence workflow did not preserve provider request"
    ):
        workflow.execute(
            ScholarlyEvidenceRequest(query="query"),
            request_id="request-001",
            task_id="task-001",
            output_dir=tmp_path,
            execution_id="scholarly-001",
        )
    assert list(tmp_path.iterdir()) == []


def test_result_contract_type_is_preserved(tmp_path: Path) -> None:
    result = full_workflow(FixtureProvider()).execute(
        ScholarlyEvidenceRequest(query="query"),
        request_id="request-001",
        task_id="task-001",
        output_dir=tmp_path,
        execution_id="scholarly-001",
    )
    assert isinstance(result.workflow_result, BoundedScholarlyEvidenceWorkflowResult)
